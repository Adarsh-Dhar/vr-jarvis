from .config import USE_CACHED_TESTS
from .state import DEFAULT_STATE


def init_state(callback_context):
    '''Runs before the root agent. Fills missing keys and clears last turn's scene commands.'''
    state = callback_context.state
    for key, value in DEFAULT_STATE.items():
        if key not in state:
            state[key] = value
    state['scene_commands'] = []
    return None


# commit_changes and merge_branch are intentionally not implemented in this reference.
# If you add them later, this guard already protects them.
TIER2_TOOLS = {'commit_changes', 'merge_branch'}


def permission_guard(tool, args, tool_context):
    '''before_tool_callback. Returning a dict skips the tool call.'''
    name = tool.name
    if name in TIER2_TOOLS and not tool_context.state.get('approved'):
        return {'status': 'blocked', 'reason': 'This action needs explicit user approval.'}
    if name in {'run_tests', 'run_typecheck'} and not USE_CACHED_TESTS:
        if not tool_context.state.get('worktree'):
            return {'status': 'blocked', 'reason': 'Create a sandbox worktree first.'}
    return None
