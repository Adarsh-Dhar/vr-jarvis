"""Runtime tracing: executes a script inside the worktree under a
sys.settrace tracer and records call/return/exception events (names and
locations only — never argument or return values)."""
