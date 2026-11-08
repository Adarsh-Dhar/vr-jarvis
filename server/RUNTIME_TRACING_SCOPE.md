# Runtime Tracing - Supported Scope

## Basic Implementation (v29)

The runtime tracing feature provides a **basic Python execution visualizer** for synchronous code within the authorized worktree. This is not a full debugger or production-grade profiler.

### Supported Capabilities

The following capabilities are fully supported in the basic implementation:

- **Synchronous Python function tracing** - Captures function calls, returns, and timing for synchronous Python code
- **Function invocation hierarchy** - Records parent-child relationships between function calls
- **Function execution timing** - Measures wall-clock duration (not CPU time) for each function call
- **Basic exception-event capture** - Records exception type, file, line, function, and timestamp
- **Runtime execution graph** - Generates nodes and edges from actual execution events for visualization
- **Runtime event timeline** - Provides a chronological view of execution events
- **Trace storage and retrieval** - Persists traces with session ownership and isolation

### Unsupported Capabilities

The following capabilities are **not supported** in the basic implementation and will be reported as unsupported or partial:

- **Async execution tracing** - Async functions, coroutines, and async generators are not traced
- **Generator tracing** - Generator functions are not traced
- **Background-thread tracing** - Code executed in worker threads is not traced
- **C/native extension calls** - Calls to C extensions are not traced
- **CPU profiling** - CPU time profiling is not provided
- **Memory profiling** - Memory usage monitoring is not provided
- **Live variable inspection** - Runtime variable state inspection is not provided
- **Function argument recording** - Function arguments are not recorded (security limitation)
- **Function return-value recording** - Function return values are not recorded (security limitation)
- **Debugger / breakpoints** - Debugging with breakpoints is not supported
- **Distributed tracing** - Tracing across distributed systems is not supported
- **Trace replay and comparison** - Trace replay and comparison are not supported

### Execution Safety

The runtime tracing feature has the following security boundaries:

**Current Implementation:**
- Copies the server's environment and removes a small number of named secret variables (JARVIS_TOKEN, API_KEY, SECRET_KEY, PASSWORD)
- Validates that the target entrypoint is inside the authorized worktree (with symlink resolution)
- Restricts tracing to files within the authorized worktree
- Rejects pseudo-files and files outside the worktree

**Important Limitations:**
- This is **not** a complete security boundary
- The environment-variable allowlist is deliberately limited but not comprehensive
- The current worktree path validation does **not** create an operating-system sandbox
- Do not describe this as sandboxed unless actual process isolation is implemented

**Recommended Safeguards:**
- Use a deliberately limited environment-variable allowlist
- Restrict the initial runtime feature to trusted repository code
- Consider implementing actual process isolation for production use

### Unsupported Case Reporting

When unsupported execution types are encountered (async, generators, background threads, etc.), the trace will:

1. Mark the trace status as `partial`
2. Add the unsupported feature to the `limitations` array in the trace
3. Report the limitation explicitly in the VR runtime panel
4. Continue tracing supported synchronous code where possible

Multiple unsupported features will all be reported in the limitations list, not just the first one encountered.

### Completion Criteria

The basic implementation is considered complete when:

- Target applications launch correctly with arguments and sibling-module imports
- Function-call, return and timing events work for supported synchronous Python code
- Parent-child relationships and recursive calls are correct
- Distinct exceptions are captured without propagation duplicates
- Traces are persisted and retrieved with session isolation
- Runtime graph nodes and edges are generated from actual execution events
- VR runtime panel displays calls, timing, exceptions and partial-trace limitations
- Focused automated tests pass with real fixture applications
- Unity compiles and runtime graph and panel verified in Meta XR Simulator
- Unsupported cases are clearly reported and execution restricted to trusted code

### Future Enhancements

The following enhancements are planned for future versions but are not in scope for the basic implementation:

- Async execution tracing support
- Generator and coroutine tracing
- Background-thread tracing
- CPU and memory profiling
- Variable state inspection
- Function argument and return value recording (with security controls)
- Interactive debugging with breakpoints
- Distributed tracing support
- Trace replay and comparison tools
