"""Agent tools for runtime tracing. Uses the same
``tool_context.state['worktree']`` convention as the other worktree tools,
falling back to a snapshot of the repository root when no worktree exists."""
import shutil
from pathlib import Path
from typing import List

from google.adk.tools import ToolContext

from ..runtime import trace_manager as tm
from ._common import repo_root
from ._safe import safe

_SNAP_IGNORE = shutil.ignore_patterns(
    '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env', 'build',
    'dist', '.pytest_cache', '.mypy_cache', '*.pyc')


def _validate_command(command):
    if not command or not all(isinstance(c, str) for c in command):
        return 'command must be a non-empty list of strings'
    if len(command) > 32 or any(len(c) > 512 for c in command):
        return 'command too long'
    if not command[0].endswith('.py'):
        return 'command[0] must be a .py file'
    return None


def _validate_script_in_root(script_arg, root):
    """Containment check against the real root the trace will run in.
    Resolves symlinks; returns an error string or None."""
    try:
        root_r = Path(root).resolve()
        p = (root_r / script_arg).resolve()
        p.relative_to(root_r)          # raises ValueError on escape
        if not p.is_file():
            return 'script not found: %s' % script_arg
    except ValueError:
        return 'script escapes the trace root: %s' % script_arg
    except Exception as exc:
        return 'script validation failed: %s' % exc
    return None


@safe
def start_runtime_trace(command: List[str], tool_context: ToolContext,
                        timeout_seconds: int = 30,
                        max_events: int = 20000) -> dict:
    err = _validate_command(command)
    if err:
        return {'status': 'error', 'error': err}
    wt = tool_context.state.get('worktree')
    snapshot = None
    if not wt:
        # No sandbox worktree: trace a snapshot of the repository so
        # uncommitted edits are included but the real tree is untouched.
        snapshot = tm.make_snapshot(str(repo_root()), _SNAP_IGNORE)
        wt = snapshot
    err = _validate_script_in_root(command[0], wt)
    if err:
        if snapshot:
            shutil.rmtree(Path(snapshot).parent, ignore_errors=True)
        return {'status': 'error', 'error': err}
    timeout_seconds = max(1, min(timeout_seconds, 120))
    max_events = max(1, min(max_events, 100000))
    res = tm.start(wt, command, timeout_seconds, max_events,
                   snapshot=snapshot)
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
