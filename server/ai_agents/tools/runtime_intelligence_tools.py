"""
Agent 7 - Runtime Intelligence Tools
Understand actual execution.

Phase 5 Status: PARTIALLY IMPLEMENTED
- Core application lifecycle tools (start_application, stop_application) implemented with subprocess management
- Trace collection and visualization implemented
- Basic recording tools return actual trace data
- Advanced tools (CPU, memory, async, debugging) remain unsupported

Technical Corrections Applied:
- Process-local registry with threading.Lock (not ADK session state)
- Session ID + trace ID for identifying executions
- Process group execution for clean termination
- Bounded log files (not PIPE)
- Graceful termination with grace period
- Symlink resolution in path validation
"""

from typing import Optional, List, Dict, Any
import subprocess
import time
import os
import sys
import signal
import uuid
import threading
from pathlib import Path
from google.adk.tools import ToolContext
from ._safe import safe

# Import trace store
from ..runtime_trace_store import get_trace_store

# Process-local registry (not ADK session state)
# Assumes single worker or sticky routing for initial implementation
_process_registry: Dict[str, Dict[str, Any]] = {}
_process_registry_lock = threading.Lock()
_watchdog_threads: Dict[str, threading.Thread] = {}


def _get_session_id(tool_context: ToolContext) -> str:
    """Get session ID from tool context."""
    return tool_context.state.get('session_id', 'default')


def _register_process(application_id: str, session_id: str, process: subprocess.Popen,
                     trace_id: str, trace_path: Path, stdout_path: Path, stderr_path: Path,
                     timeout_seconds: int = 30) -> str:
    """Register a process in the local registry."""
    with _process_registry_lock:
        registry_key = f"{session_id}:{application_id}"
        _process_registry[registry_key] = {
            'process': process,
            'trace_id': trace_id,
            'trace_path': trace_path,
            'stdout_path': stdout_path,
            'stderr_path': stderr_path,
            'started_at': time.time(),
            'timeout_seconds': timeout_seconds,
            'application_id': application_id,
            'session_id': session_id,
            'termination_reason': None,  # Will be set to 'timeout', 'manual', or None
            'watchdog_cancelled': False
        }
        return registry_key


def _get_process(application_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Get a process from the local registry."""
    with _process_registry_lock:
        registry_key = f"{session_id}:{application_id}"
        return _process_registry.get(registry_key)


def _unregister_process(application_id: str, session_id: str):
    """Unregister a process from the local registry."""
    with _process_registry_lock:
        registry_key = f"{session_id}:{application_id}"
        if registry_key in _process_registry:
            # Cancel watchdog before unregistering
            _process_registry[registry_key]['watchdog_cancelled'] = True
            del _process_registry[registry_key]
        # Stop watchdog thread if exists
        watchdog_key = f"{session_id}:{application_id}"
        if watchdog_key in _watchdog_threads:
            # Watchdog will self-terminate when it sees the process is unregistered
            del _watchdog_threads[watchdog_key]


def _process_watchdog(application_id: str, session_id: str, timeout_seconds: int, process: subprocess.Popen, trace_id: str):
    """
    Independent watchdog thread that enforces timeout from application launch.
    This runs independently of trace collection and will terminate the process
    if it exceeds the configured maximum duration.
    
    Uses process reference and trace_id to ensure it only terminates its own process,
    preventing old watchdogs from affecting newer applications with the same ID.
    """
    watchdog_key = f"{session_id}:{application_id}"
    
    # Wait for the timeout duration
    time.sleep(timeout_seconds)
    
    # Check if process is still registered and running
    with _process_registry_lock:
        proc_info = _process_registry.get(watchdog_key)
        if not proc_info:
            # Process was already unregistered (completed or stopped)
            return
        
        # Verify this is still the same process (prevent old watchdog from terminating new process)
        if proc_info['process'] is not process or proc_info['trace_id'] != trace_id:
            # This is a different process with the same application_id
            return
        
        # Check if watchdog was cancelled
        if proc_info.get('watchdog_cancelled', False):
            return
        
        # Check if process is still running
        if process.poll() is None:
            # Process exceeded timeout - terminate it and record reason
            proc_info['termination_reason'] = 'timeout'
            try:
                process.terminate()
                # Give grace period for trace finalization
                time.sleep(2)
                if process.poll() is None:
                    # Force kill if still running
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            except Exception:
                pass


@safe
def start_application(
    application_id: str,
    environment: str,
    tool_context: ToolContext,
    entrypoint: Optional[str] = None,
    arguments: Optional[List[str]] = None,
    timeout_seconds: int = 30
) -> dict:
    """
    Launch a Python application in an authorized environment with runtime tracing.

    Args:
        application_id: Identifier for the application
        environment: Environment configuration (dev, staging, prod)
        tool_context: Tool context
        entrypoint: Path to Python entrypoint file (required for tracing)
        arguments: Optional command-line arguments
        timeout_seconds: Maximum execution duration in seconds

    Returns:
        Process ID and status
    """
    # Get worktree from tool context
    worktree = tool_context.state.get('worktree')
    if not worktree:
        return {
            'status': 'blocked',
            'reason': 'No authorized worktree available',
            'application_id': application_id
        }

    worktree_path = Path(worktree).resolve()

    # Validate entrypoint
    if not entrypoint:
        return {
            'status': 'blocked',
            'reason': 'Entrypoint required for runtime tracing',
            'application_id': application_id
        }

    entrypoint_path = Path(entrypoint).resolve()

    # Check entrypoint exists and is a Python file
    if not entrypoint_path.exists():
        return {
            'status': 'blocked',
            'reason': f'Entrypoint not found: {entrypoint}',
            'application_id': application_id
        }

    if not entrypoint_path.is_file():
        return {
            'status': 'blocked',
            'reason': f'Entrypoint is not a file: {entrypoint}',
            'application_id': application_id
        }

    if not entrypoint_path.suffix == '.py':
        return {
            'status': 'blocked',
            'reason': f'Entrypoint must be a Python file: {entrypoint}',
            'application_id': application_id
        }

    # Validate entrypoint is inside worktree (resolve symlinks)
    try:
        entrypoint_path.relative_to(worktree_path)
    except ValueError:
        return {
            'status': 'blocked',
            'reason': 'Entrypoint must be inside authorized worktree',
            'application_id': application_id
        }

    # Create unique trace ID
    trace_id = str(uuid.uuid4())
    session_id = _get_session_id(tool_context)

    # Set up trace output path
    trace_store = get_trace_store()
    trace_path = trace_store.storage_dir / f"{trace_id}.json"

    # Set up bounded log files
    logs_dir = trace_store.storage_dir / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{trace_id}.stdout"
    stderr_path = logs_dir / f"{trace_id}.stderr"

    # Get trace runner path
    runner_path = Path(__file__).parent.parent / 'runtime_trace_runner.py'

    # Build command
    cmd = [
        sys.executable,
        str(runner_path),
        '--target', str(entrypoint_path),
        '--trace-out', str(trace_path),
        '--max-events', '5000',
        '--max-duration', str(timeout_seconds),
        '--worktree', str(worktree_path),
        '--trace-id', trace_id,
        '--application-id', application_id
    ]

    # Add application arguments after -- separator
    if arguments:
        cmd.append('--')
        cmd.extend(arguments)

    # Prepare restricted environment with allowlist
    env = os.environ.copy()
    
    # Environment variable allowlist for trusted repository code
    # This is not a complete security boundary, but reduces credential exposure
    allowed_keys = {
        'PATH', 'HOME', 'USER', 'SHELL', 'TERM', 'LANG', 'LC_ALL', 'LC_CTYPE',
        'PYTHONPATH', 'PYTHONUNBUFFERED', 'TZ',
        # Build tools and compilers
        'CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS',
        # Package managers
        'VIRTUAL_ENV', 'CONDA_PREFIX',
    }
    
    # Remove all variables not in allowlist
    keys_to_remove = [key for key in env.keys() if key not in allowed_keys]
    for key in keys_to_remove:
        env.pop(key, None)

    try:
        # Launch in process group for clean termination
        process = subprocess.Popen(
            cmd,
            cwd=str(worktree_path),
            env=env,
            stdout=open(stdout_path, 'w'),
            stderr=open(stderr_path, 'w'),
            shell=False,
            start_new_session=True  # Create new process group
        )

        # Register process
        _register_process(
            application_id=application_id,
            session_id=session_id,
            process=process,
            trace_id=trace_id,
            trace_path=trace_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout_seconds=timeout_seconds
        )

        # Start independent watchdog thread for timeout enforcement
        watchdog_key = f"{session_id}:{application_id}"
        watchdog_thread = threading.Thread(
            target=_process_watchdog,
            args=(application_id, session_id, timeout_seconds, process, trace_id),
            daemon=True
        )
        watchdog_thread.start()
        with _process_registry_lock:
            _watchdog_threads[watchdog_key] = watchdog_thread

        return {
            'status': 'ok',
            'application_id': application_id,
            'pid': process.pid,
            'trace_id': trace_id,
            'entrypoint': str(entrypoint_path),
            'timeout_seconds': timeout_seconds,
            'environment': environment
        }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'application_id': application_id
        }


@safe
def stop_application(application_id: str, tool_context: ToolContext) -> dict:
    """
    Stop a running application.

    Args:
        application_id: Application identifier
        tool_context: Tool context

    Returns:
        Status of stop operation
    """
    session_id = _get_session_id(tool_context)
    proc_info = _get_process(application_id, session_id)

    if not proc_info:
        return {
            'status': 'not_found',
            'reason': 'Application not found in process registry',
            'application_id': application_id
        }

    process = proc_info['process']
    trace_path = proc_info['trace_path']
    trace_id = proc_info['trace_id']

    try:
        if process.poll() is None:
            # Process is still running - terminate gracefully
            process.terminate()
            try:
                process.wait(timeout=5)  # Grace period
            except subprocess.TimeoutExpired:
                # Didn't stop - kill process group
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass

        # Save trace file to trace store if it exists
        if trace_path.exists():
            try:
                with open(trace_path, 'r') as f:
                    trace_data = f.read()
                    trace = __import__('json').loads(trace_data)
                
                trace_store = get_trace_store()
                save_success = trace_store.save_trace(trace_id, session_id, trace)
                
                if not save_success:
                    return {
                        'status': 'error',
                        'error': 'Failed to save trace (exceeds size limit)',
                        'application_id': application_id
                    }
            except Exception as e:
                # Trace save failed but process is stopped - return warning
                return {
                    'status': 'partial',
                    'warning': f'Process stopped but trace save failed: {e}',
                    'application_id': application_id
                }

        # Unregister process
        _unregister_process(application_id, session_id)

        return {
            'status': 'ok',
            'application_id': application_id,
            'trace_id': trace_id if trace_path.exists() else None,
            'stopped': True
        }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'application_id': application_id
        }


@safe
def collect_execution_trace(
    application_id: str,
    duration: int,
    tool_context: ToolContext
) -> dict:
    """
    Collect execution trace from a running or completed application.

    Args:
        application_id: Application identifier
        duration: Maximum wait time in seconds
        tool_context: Tool context

    Returns:
        Trace summary and events
    """
    session_id = _get_session_id(tool_context)
    proc_info = _get_process(application_id, session_id)

    if not proc_info:
        return {
            'status': 'not_found',
            'reason': 'Application not found in process registry',
            'application_id': application_id
        }

    process = proc_info['process']
    trace_path = proc_info['trace_path']
    trace_id = proc_info['trace_id']
    timeout_seconds = proc_info.get('timeout_seconds', 30)
    started_at = proc_info.get('started_at', time.time())
    termination_reason = proc_info.get('termination_reason')

    # Calculate remaining time from configured deadline
    elapsed_since_start = time.time() - started_at
    remaining_time = max(0, timeout_seconds - elapsed_since_start)

    # Enforce actual deadline from application launch
    enforced_timeout = min(duration, remaining_time)

    # Wait for process to finish (up to enforced deadline)
    exit_code = None
    interrupted = False
    timeout_hit = False

    # If watchdog already terminated the process, check the reason
    if termination_reason == 'timeout':
        timeout_hit = True
        interrupted = True
        exit_code = process.poll() if process.poll() is not None else None
    else:
        try:
            if process.poll() is None:
                # Process still running - wait with timeout
                try:
                    exit_code = process.wait(timeout=enforced_timeout)
                except subprocess.TimeoutExpired:
                    # Timeout - terminate gracefully
                    timeout_hit = True
                    interrupted = True
                    process.terminate()
                    try:
                        process.wait(timeout=5)  # Grace period for trace finalization
                    except subprocess.TimeoutExpired:
                        # Didn't stop - kill process group
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    exit_code = None  # Indicate interrupted
            else:
                exit_code = process.poll()

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'application_id': application_id
            }

    # Load trace file
    if not trace_path.exists():
        # Unregister process since we're done
        _unregister_process(application_id, session_id)

        return {
            'status': 'partial',
            'reason': 'Trace file not generated',
            'application_id': application_id,
            'interrupted': interrupted,
            'timeout_hit': timeout_hit,
            'trace_available': False
        }

    try:
        with open(trace_path, 'r') as f:
            trace_data = f.read()
            trace = __import__('json').loads(trace_data)
    except Exception as e:
        _unregister_process(application_id, session_id)
        return {
            'status': 'error',
            'error': f'Failed to load trace: {e}',
            'application_id': application_id
        }

    # If timeout was hit, ensure trace reflects this
    if timeout_hit:
        # Add timeout limitation if not already present
        limitations = trace.get('limitations', [])
        
        # Remove any SIGTERM interruption message if this was an automatic timeout
        # The watchdog terminates with SIGTERM, but we want to classify it as duration_limit
        limitations = [lim for lim in limitations if 'SIGTERM' not in lim and 'interrupted' not in lim.lower()]
        
        # Add timeout limitation if not already present
        if not any('timeout' in limit.lower() or 'duration limit' in limit.lower() for limit in limitations):
            limitations.append(f"Execution terminated after {timeout_seconds}s duration limit")
        
        # Always update the trace with modified limitations
        trace['limitations'] = limitations
        trace['status'] = 'partial'
        
        # Update trace file
        try:
            with open(trace_path, 'w') as f:
                __import__('json').dump(trace, f, indent=2)
        except Exception:
            pass  # Best effort to update

    # Store trace in trace store with session ownership
    trace_store = get_trace_store()
    save_success = trace_store.save_trace(trace_id, session_id, trace)

    if not save_success:
        _unregister_process(application_id, session_id)
        return {
            'status': 'error',
            'error': 'Failed to save trace (exceeds size limit)',
            'application_id': application_id
        }

    # Save trace ID in session state for recording tools
    tool_context.state['runtime_trace_id'] = trace_id

    # Unregister process
    _unregister_process(application_id, session_id)

    # Determine actual status
    if interrupted:
        status = 'partial'
    elif trace.get('status') == 'failed':
        status = 'failed'
    elif trace.get('truncated') or trace.get('limitations'):
        status = 'partial'
    else:
        status = 'ok'

    # Check if we have real events
    stats = trace.get('statistics', {})
    if stats.get('total_events', 0) == 0:
        status = 'partial'

    return {
        'status': status,
        'application_id': application_id,
        'trace_id': trace_id,
        'provenance': trace.get('provenance', 'runtime_observed'),
        'execution_status': trace.get('status', 'unknown'),
        'function_calls': stats.get('function_calls', 0),
        'function_returns': stats.get('function_returns', 0),
        'exceptions': stats.get('exceptions', 0),
        'duration_ms': trace.get('duration_ms', 0),
        'truncated': trace.get('truncated', False),
        'trace_available': True,
        'limitations': trace.get('limitations', []),
        'interrupted': interrupted,
        'timeout_hit': timeout_hit
    }


@safe
def attach_runtime_profiler(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Attach a profiler."""
    return {
        'status': 'unsupported',
        'reason': 'Runtime profiling uses built-in sys.setprofile during execution',
        'application_id': application_id
    }


@safe
def attach_debugger(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Attach a debugger."""
    return {
        'status': 'unsupported',
        'reason': 'Debugging requires Debug Adapter Protocol (DAP) integration',
        'application_id': application_id
    }


@safe
def record_function_calls(
    application_id: str,
    tool_context: ToolContext,
    function_names: Optional[List[str]] = None
) -> dict:
    """Record observed function calls from trace."""
    session_id = _get_session_id(tool_context)

    # First try to get from process registry (for active applications)
    proc_info = _get_process(application_id, session_id)

    trace = None
    if proc_info:
        trace_id = proc_info['trace_id']
        trace_store = get_trace_store()
        trace = trace_store.get_trace(trace_id, session_id)
    else:
        # If not in process registry, try to get trace ID from session state
        trace_id = tool_context.state.get('runtime_trace_id')
        if trace_id:
            trace_store = get_trace_store()
            trace = trace_store.get_trace(trace_id, session_id)

    if not trace:
        return {
            'status': 'not_found',
            'reason': 'Trace not found for application',
            'application_id': application_id
        }

    # Filter events for function calls
    call_events = [
        e for e in trace.get('events', [])
        if e.get('event_type') == 'function_call'
    ]

    # Filter by function names if provided
    if function_names:
        call_events = [
            e for e in call_events
            if e.get('function_name') in function_names
        ]

    return {
        'status': 'ok',
        'application_id': application_id,
        'trace_id': trace.get('trace_id'),
        'function_calls': call_events,
        'total_calls': len(call_events)
    }


@safe
def record_function_arguments(
    application_id: str,
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Record permitted argument information."""
    return {
        'status': 'unsupported',
        'reason': 'Function argument recording not implemented (security limitation)',
        'application_id': application_id,
        'function_id': function_id
    }


@safe
def record_function_returns(
    application_id: str,
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Record return values."""
    return {
        'status': 'unsupported',
        'reason': 'Function return recording not implemented (security limitation)',
        'application_id': application_id,
        'function_id': function_id
    }


@safe
def record_execution_timing(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Record measured execution duration per call."""
    session_id = _get_session_id(tool_context)

    # First try to get from process registry (for active applications)
    proc_info = _get_process(application_id, session_id)

    trace = None
    if proc_info:
        trace_id = proc_info['trace_id']
        trace_store = get_trace_store()
        trace = trace_store.get_trace(trace_id, session_id)
    else:
        # If not in process registry, try to get trace ID from session state
        trace_id = tool_context.state.get('runtime_trace_id')
        if trace_id:
            trace_store = get_trace_store()
            trace = trace_store.get_trace(trace_id, session_id)

    if not trace:
        return {
            'status': 'not_found',
            'reason': 'Trace not found for application',
            'application_id': application_id
        }

    # Extract timing information from call events
    call_events = [
        e for e in trace.get('events', [])
        if e.get('event_type') == 'function_call'
    ]

    timing_data = []
    for event in call_events:
        timing_data.append({
            'call_id': event.get('call_id'),
            'function_name': event.get('function_name'),
            'file': event.get('file'),
            'line': event.get('line'),
            'duration_ms': event.get('duration_ms', 0),
            'elapsed_ms': event.get('elapsed_ms', 0)
        })

    return {
        'status': 'ok',
        'application_id': application_id,
        'trace_id': trace.get('trace_id'),
        'timing_data': timing_data,
        'total_calls': len(timing_data)
    }


@safe
def record_variable_state(
    application_id: str,
    variable_id: str,
    tool_context: ToolContext
) -> dict:
    """Observe selected runtime variables."""
    return {
        'status': 'unsupported',
        'reason': 'Variable state observation not implemented (security limitation)',
        'application_id': application_id,
        'variable_id': variable_id
    }


@safe
def record_memory_usage(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Monitor memory consumption."""
    return {
        'status': 'unsupported',
        'reason': 'Memory profiling not implemented in Partial scope',
        'application_id': application_id
    }


@safe
def record_cpu_usage(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Monitor CPU utilization."""
    return {
        'status': 'unsupported',
        'reason': 'CPU profiling not implemented in Partial scope',
        'application_id': application_id
    }


@safe
def record_network_activity(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Observe network operations."""
    return {
        'status': 'unsupported',
        'reason': 'Network activity monitoring not implemented in Partial scope',
        'application_id': application_id
    }


@safe
def record_database_activity(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Observe database operations."""
    return {
        'status': 'unsupported',
        'reason': 'Database activity monitoring not implemented in Partial scope',
        'application_id': application_id
    }


@safe
def record_async_tasks(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Observe asynchronous tasks."""
    return {
        'status': 'unsupported',
        'reason': 'Async task tracing not implemented in Partial scope',
        'application_id': application_id
    }


@safe
def record_thread_activity(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Observe threads."""
    return {
        'status': 'unsupported',
        'reason': 'Thread activity tracing not implemented in Partial scope',
        'application_id': application_id
    }


@safe
def capture_application_logs(
    application_id: str,
    tool_context: ToolContext,
    since: Optional[str] = None
) -> dict:
    """Collect bounded stdout/stderr from trace logs."""
    session_id = _get_session_id(tool_context)
    proc_info = _get_process(application_id, session_id)

    if not proc_info:
        return {
            'status': 'not_found',
            'reason': 'Application not found in process registry',
            'application_id': application_id
        }

    stdout_path = proc_info['stdout_path']
    stderr_path = proc_info['stderr_path']

    # Read bounded excerpts (last 100 lines)
    stdout_excerpt = []
    stderr_excerpt = []

    try:
        if stdout_path.exists():
            with open(stdout_path, 'r') as f:
                lines = f.readlines()
                stdout_excerpt = lines[-100:] if len(lines) > 100 else lines
    except Exception:
        pass

    try:
        if stderr_path.exists():
            with open(stderr_path, 'r') as f:
                lines = f.readlines()
                stderr_excerpt = lines[-100:] if len(lines) > 100 else lines
    except Exception:
        pass

    return {
        'status': 'ok',
        'application_id': application_id,
        'stdout_lines': len(stdout_excerpt),
        'stderr_lines': len(stderr_excerpt),
        'stdout_excerpt': ''.join(stdout_excerpt),
        'stderr_excerpt': ''.join(stderr_excerpt)
    }


@safe
def capture_runtime_events(
    application_id: str,
    tool_context: ToolContext,
    event_types: Optional[List[str]] = None
) -> dict:
    """Collect runtime events."""
    return {
        'status': 'unsupported',
        'reason': 'Runtime event capture handled by collect_execution_trace',
        'application_id': application_id
    }


@safe
def compare_execution_traces(
    trace1_id: str,
    trace2_id: str,
    tool_context: ToolContext
) -> dict:
    """Compare different executions."""
    return {
        'status': 'unsupported',
        'reason': 'Trace comparison not implemented in Partial scope',
        'trace1_id': trace1_id,
        'trace2_id': trace2_id
    }


@safe
def replay_execution_trace(trace_id: str, tool_context: ToolContext) -> dict:
    """Replay a captured execution where supported."""
    return {
        'status': 'unsupported',
        'reason': 'Trace replay not implemented in Partial scope',
        'trace_id': trace_id
    }
