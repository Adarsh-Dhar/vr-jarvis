"""
Runtime Trace Runner
Python subprocess profiler using sys.setprofile to capture actual execution events.

This is a standalone script that instruments a target Python application
and records function calls, returns, and exceptions with timing information.

Technical Corrections Applied:
- Canonical event schema with timestamp_ns (long), elapsed_ms, duration_ms, thread_id (long)
- Exception handling: record original only, not propagation, disable line events
- Call stack: synchronous main thread, frame identity, unique IDs for recursion
- Timeout: process group, bounded logs, graceful termination, SIGTERM handler
- Unsupported types: generators, coroutines, background threads, C-extensions
- Timing: duration_ms is wall-clock time (not CPU time)
"""

import sys
import os
import time
import uuid
import argparse
import threading
import json
import signal
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from collections import defaultdict
from types import FrameType, CodeType


class RuntimeTracer:
    """Captures runtime execution events using sys.setprofile."""

    def __init__(self, worktree: Path, max_events: int = 5000, max_duration: int = 30):
        self.worktree = worktree.resolve()
        self.max_events = max_events
        self.max_duration = max_duration
        self.events: List[Dict[str, Any]] = []
        self.call_stacks: Dict[int, List[str]] = defaultdict(list)  # thread_id -> call_id stack
        self.frame_call_ids: Dict[int, str] = {}  # frame object id -> call_id mapping
        self.call_counter = 0
        self.start_time_ns = time.perf_counter_ns()
        self.start_time = time.time()
        self.truncated = False
        self.lock = threading.Lock()
        self.exception_count = 0
        self.exception_instances: Dict[int, Any] = {}  # Retain exception objects to prevent ID reuse
        self.unsupported_detected = False
        self.unsupported_reasons: List[str] = []
        self.interrupted = False  # Track if execution was interrupted by SIGTERM

    def _is_in_worktree(self, filepath: str) -> bool:
        """Check if a file is inside the authorized worktree (resolves symlinks)."""
        if not filepath:
            return False

        # Reject pseudo-files (like <frozen runpy>, <string>, etc.)
        if filepath.startswith("<") and filepath.endswith(">"):
            return False

        try:
            path = Path(filepath).resolve()

            # Reject if not a regular file
            if not path.is_file():
                return False

            # Check if the path is inside the worktree
            path.relative_to(self.worktree)
            return True
        except (ValueError, OSError):
            return False

    def _should_record(self, filepath: str) -> bool:
        """Determine if an event should be recorded."""
        # Check if we've hit the event limit
        if len(self.events) >= self.max_events:
            self.truncated = True
            return False

        # Exclude the runner file itself
        if 'runtime_trace_runner.py' in filepath:
            return False

        # Only record files inside the worktree
        if not self._is_in_worktree(filepath):
            return False

        # Skip standard library and site-packages
        if 'site-packages' in filepath or 'lib/python' in filepath:
            return False

        return True

    def _detect_unsupported_execution(self, frame: FrameType) -> Optional[str]:
        """Detect unsupported execution types (generators, coroutines, etc.)."""
        code = frame.f_code

        # Check for generator functions
        if code.co_flags & 0x20:  # CO_GENERATOR
            return "generator_function"

        # Check for coroutine functions
        if code.co_flags & 0x80:  # CO_COROUTINE
            return "coroutine_function"

        # Check for async generator
        if code.co_flags & 0x200:  # CO_ASYNC_GENERATOR
            return "async_generator"

        return None

    def _profile_callback(self, frame: FrameType, event: str, arg):
        """sys.setprofile callback for function call/return events."""
        with self.lock:
            # Check duration limit
            if time.time() - self.start_time > self.max_duration:
                self.truncated = True
                return

            filepath = frame.f_code.co_filename
            if not self._should_record(filepath):
                return

            thread_id = threading.get_ident()

            # Mark worker threads as unsupported
            if thread_id != threading.main_thread().ident:
                if "background_thread_execution" not in self.unsupported_reasons:
                    self.unsupported_reasons.append("background_thread_execution")
                    self.unsupported_detected = True
                return

            call_id = None

            if event == 'call':
                # Detect unsupported execution types
                unsupported = self._detect_unsupported_execution(frame)
                if unsupported and unsupported not in self.unsupported_reasons:
                    self.unsupported_reasons.append(unsupported)
                    self.unsupported_detected = True
                    return

                # Generate unique call ID (supports recursion)
                self.call_counter += 1
                call_id = f"call_{self.call_counter:06d}"

                # Map frame object to call ID for return handling
                self.frame_call_ids[id(frame)] = call_id

                # Get parent call ID from stack (using frame identity)
                parent_call_id = self.call_stacks[thread_id][-1] if self.call_stacks[thread_id] else None

                # Push this call onto the stack
                self.call_stacks[thread_id].append(call_id)

                # Record the call event with canonical schema
                event_data = {
                    "event_type": "function_call",
                    "call_id": call_id,
                    "parent_call_id": parent_call_id,
                    "function_name": frame.f_code.co_name,
                    "qualified_name": frame.f_code.co_name,  # Could be enhanced with qualname
                    "file": filepath,
                    "line": frame.f_lineno,  # Function definition line
                    "timestamp_ns": time.perf_counter_ns() - self.start_time_ns,
                    "elapsed_ms": (time.perf_counter_ns() - self.start_time_ns) / 1_000_000.0,
                    "duration_ms": 0.0,  # Will be filled on return
                    "thread_id": thread_id,
                    "depth": len(self.call_stacks[thread_id]) - 1
                }
                self.events.append(event_data)

            elif event == 'return':
                # Use frame identity to get the original call ID
                call_id = self.frame_call_ids.pop(id(frame), None)

                if call_id:
                    # Remove from call stack if present
                    if self.call_stacks[thread_id] and self.call_stacks[thread_id][-1] == call_id:
                        self.call_stacks[thread_id].pop()

                    # Calculate duration (wall-clock time, not CPU time)
                    current_ns = time.perf_counter_ns() - self.start_time_ns
                    current_ms = current_ns / 1_000_000.0

                    # Find the matching call event to get its timestamp
                    call_event = None
                    for e in reversed(self.events):
                        if e["event_type"] == "function_call" and e["call_id"] == call_id:
                            call_event = e
                            break

                    duration_ms = 0.0
                    if call_event:
                        duration_ms = current_ms - call_event["elapsed_ms"]
                        # Update the call event with duration
                        call_event["duration_ms"] = duration_ms

                    # Record the return event
                    event_data = {
                        "event_type": "function_return",
                        "call_id": call_id,
                        "timestamp_ns": current_ns,
                        "elapsed_ms": current_ms,
                        "duration_ms": duration_ms,
                        "thread_id": thread_id
                    }
                    self.events.append(event_data)

    def _trace_callback(self, frame: FrameType, event: str, arg):
        """sys.settrace callback for exception events (line events disabled)."""
        # Disable line event collection to avoid full debugger overhead
        frame.f_trace_lines = False

        if event == 'exception':
            with self.lock:
                filepath = frame.f_code.co_filename
                if not self._should_record(filepath):
                    return self._trace_callback

                thread_id = threading.get_ident()
                exc_type, exc_value, exc_tb = arg

                # Use exception instance identity with object retention
                exc_id = id(exc_value)

                # Check if this is a new exception instance (not propagation)
                if self.exception_instances.get(exc_id) is not exc_value:
                    self.exception_instances[exc_id] = exc_value
                    self.exception_count += 1

                    event_data = {
                        "event_type": "exception",
                        "exception_type": str(exc_type.__name__) if exc_type else "Unknown",
                        "exception_id": str(exc_id),  # Expose as string in event
                        "file": filepath,
                        "line": frame.f_lineno,
                        "function_name": frame.f_code.co_name,
                        "timestamp_ns": time.perf_counter_ns() - self.start_time_ns,
                        "elapsed_ms": (time.perf_counter_ns() - self.start_time_ns) / 1_000_000.0,
                        "thread_id": thread_id
                    }
                    self.events.append(event_data)

        return self._trace_callback

    def start(self):
        """Start profiling."""
        sys.setprofile(self._profile_callback)
        # Also set trace for exception events (line events disabled in callback)
        sys.settrace(self._trace_callback)
        # Install thread profiler to detect worker threads
        threading.setprofile(self._profile_callback)

    def stop(self):
        """Stop profiling and clear retained references."""
        sys.setprofile(None)
        sys.settrace(None)
        threading.setprofile(None)
        self.exception_instances.clear()  # Clear retained exception objects

    def get_trace(self, application_id: str, exit_code: int) -> Dict[str, Any]:
        """Generate the final trace structure."""
        end_time = time.time()
        duration_ms = (end_time - self.start_time) * 1000

        # Determine status
        if self.interrupted:
            status = "partial"
        elif self.unsupported_detected:
            status = "partial"
        elif self.truncated:
            status = "partial"
        elif exit_code != 0:
            status = "failed"
        else:
            status = "completed"

        # Build limitations list
        limitations = []
        if self.interrupted:
            limitations.append("Execution interrupted by SIGTERM")
        if self.unsupported_detected:
            limitations.extend(self.unsupported_reasons)
        if self.truncated:
            limitations.append(f"Trace truncated at {self.max_events} events")
        if duration_ms / 1000 > self.max_duration * 0.9:
            limitations.append(f"Execution near {self.max_duration}s timeout limit")

        return {
            "schema_version": 1,
            "trace_id": str(uuid.uuid4()),
            "application_id": application_id,
            "language": "python",
            "provenance": "runtime_observed",
            "status": status,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.start_time)),
            "ended_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(end_time)),
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "events": self.events,
            "truncated": self.truncated,
            "limitations": limitations,
            "statistics": {
                "function_calls": sum(1 for e in self.events if e["event_type"] == "function_call"),
                "function_returns": sum(1 for e in self.events if e["event_type"] == "function_return"),
                "exceptions": self.exception_count,
                "total_events": len(self.events)
            }
        }


# Global tracer instance for signal handler
_tracer_instance: Optional[RuntimeTracer] = None


def signal_handler(signum, frame):
    """SIGTERM handler to finalize trace before termination."""
    global _tracer_instance
    if _tracer_instance:
        _tracer_instance.interrupted = True
        _tracer_instance.stop()
        # Write partial trace if possible
        print("Received termination signal, finalizing trace...", file=sys.stderr)
    sys.exit(130)  # 128 + SIGTERM


def main():
    """Main entry point for the trace runner."""
    global _tracer_instance

    # Split arguments at -- separator (exclude sys.argv[0] - the runner's own filename)
    argv = sys.argv[1:]

    if "--" in argv:
        separator_index = argv.index("--")
        runner_args = argv[:separator_index]
        target_args = argv[separator_index + 1:]
    else:
        runner_args = argv
        target_args = []

    parser = argparse.ArgumentParser(description="Python runtime trace runner")
    parser.add_argument("--target", required=True, help="Path to target Python application")
    parser.add_argument("--trace-out", required=True, help="Path to output trace JSON file")
    parser.add_argument("--max-events", type=int, default=5000, help="Maximum events to record")
    parser.add_argument("--max-duration", type=int, default=30, help="Maximum execution duration in seconds")
    parser.add_argument("--worktree", required=True, help="Authorized worktree path")
    parser.add_argument("--trace-id", required=True, help="Trace ID to use")
    parser.add_argument("--application-id", required=True, help="Application ID to use")

    args = parser.parse_args(runner_args)

    target_path = Path(args.target).resolve()
    trace_out_path = Path(args.trace_out).resolve()
    worktree = Path(args.worktree).resolve()
    trace_id = args.trace_id
    application_id = args.application_id

    # Validate inputs (resolve symlinks)
    if not target_path.exists():
        print(f"Error: Target file not found: {target_path}", file=sys.stderr)
        sys.exit(1)

    if not target_path.is_file():
        print(f"Error: Target is not a file: {target_path}", file=sys.stderr)
        sys.exit(1)

    if not worktree.exists():
        print(f"Error: Worktree not found: {worktree}", file=sys.stderr)
        sys.exit(1)

    # Check for path traversal (after resolving symlinks)
    try:
        target_path.relative_to(worktree)
    except ValueError:
        print(f"Error: Target file must be inside worktree", file=sys.stderr)
        sys.exit(1)

    # Create tracer
    tracer = RuntimeTracer(
        worktree=worktree,
        max_events=args.max_events,
        max_duration=args.max_duration
    )
    _tracer_instance = tracer

    # Install signal handler for graceful termination
    signal.signal(signal.SIGTERM, signal_handler)

    # Start profiling
    tracer.start()

    # Execute the target application
    exit_code = 0
    try:
        import runpy

        # Save original state
        old_cwd = os.getcwd()
        old_sys_path = sys.path.copy()
        old_sys_argv = sys.argv.copy()

        try:
            # Set up target environment
            target_dir = target_path.parent
            if str(target_dir) not in sys.path:
                sys.path.insert(0, str(target_dir))

            os.chdir(target_dir)
            sys.argv = [str(target_path)] + target_args

            # Execute
            runpy.run_path(str(target_path), run_name="__main__")
        finally:
            # Restore original state
            os.chdir(old_cwd)
            sys.path = old_sys_path
            sys.argv = old_sys_argv
    except SystemExit as e:
        exit_code = e.code if e.code is not None else 0
    except Exception as e:
        exit_code = 1
        print(f"Error during execution: {e}", file=sys.stderr)
    finally:
        # Stop profiling
        tracer.stop()

    # Generate trace with provided IDs
    trace = tracer.get_trace(application_id, exit_code)
    # Override the trace_id with the provided one
    trace['trace_id'] = trace_id

    # Write trace atomically
    trace_out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = trace_out_path.with_suffix(".tmp")
    try:
        with open(temp_path, "w") as f:
            json.dump(trace, f, indent=2)
        # Atomic rename
        temp_path.replace(trace_out_path)
    except Exception as e:
        print(f"Error writing trace: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Trace written to: {trace_out_path}")
    print(f"Status: {trace['status']}")
    print(f"Events: {trace['statistics']['total_events']}")
    print(f"Function calls: {trace['statistics']['function_calls']}")
    print(f"Exceptions: {trace['statistics']['exceptions']}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
