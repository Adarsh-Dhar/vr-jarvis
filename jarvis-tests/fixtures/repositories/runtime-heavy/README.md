# Runtime-Heavy Fixture

A repository with async code, threads, race conditions, memory leaks, and slow functions.
Each has a known recorded trace for testing runtime intelligence tools.

## Components

- **async_code.py**: Async/await patterns with concurrent operations
- **threaded_code.py**: Multi-threaded code with a deliberate race condition
- **memory_leak.py**: Code with a memory leak (growing list)
- **slow_function.py**: Intentionally slow function for timeout testing
- **traces/**: Recorded execution traces for each component

## Traces

Each component has a corresponding trace file showing:
- Function call sequence
- Thread interactions
- Memory allocations
- Timing information

## Usage

Use this fixture to test:
- Runtime intelligence tools
- Performance monitoring
- Memory leak detection
- Race condition detection
- Timeout handling
