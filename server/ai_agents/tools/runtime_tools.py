"""Agent tools for runtime tracing. Uses the same
``tool_context.state['worktree']`` convention as the other worktree tools."""
from typing import List

from google.adk.tools import ToolContext

from ..runtime import trace_manager as tm
from ._safe import safe


@safe
def start_runtime_trace(command: List[str], tool_context: ToolContext,
                        timeout_seconds: int = 30,
                        max_events: int = 20000) -> dict:
    wt = tool_context.state.get('worktree')
    if not wt:
        return {'status': 'error',
                'error': 'no active worktree; create one first'}
    if not command or not command[0].endswith('.py'):
        return {'status': 'error',
                'error': 'command[0] must be a .py file inside the worktree'}
    timeout_seconds = max(1, min(timeout_seconds, 120))
    max_events = max(1, min(max_events, 100000))
    res = tm.start(wt, command, timeout_seconds, max_events)
    sessions = dict(tool_context.state.get('trace_sessions') or {})
    sessions[res['trace_id']] = wt
    tool_context.state['trace_sessions'] = sessions
    res = dict(res)
    res.pop('status', None)          # the trace's own status, not the tool's
    return {'status': 'ok', **res}


@safe
def stop_runtime_trace(trace_id: str, tool_context: ToolContext) -> dict:
    if trace_id not in (tool_context.state.get('trace_sessions') or {}):
        return {'status': 'not_found',
                'error': 'unknown trace_id for this session'}
    res = tm.stop(trace_id)
    res = dict(res)
    inner = res.pop('status', None)
    res['trace_status'] = inner
    return {'status': 'ok', **res}


@safe
def get_runtime_trace(trace_id: str, tool_context: ToolContext) -> dict:
    if trace_id not in (tool_context.state.get('trace_sessions') or {}):
        return {'status': 'not_found',
                'error': 'unknown trace_id for this session'}
    return tm.get(trace_id)
