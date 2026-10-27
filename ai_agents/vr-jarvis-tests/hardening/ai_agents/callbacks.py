from .config import USE_CACHED_TESTS
from .state import DEFAULT_STATE


# Results that belong to one request. They are cleared every turn so no agent sees a previous turn's data.
PER_TURN_KEYS = ['changed_nodes', 'impact_static', 'tests_relevant', 'impact_report', 'answer_draft',
                 'proposed_patch', 'test_results', 'verified_answer', 'briefing']


def init_state(callback_context):
    '''Runs before the root agent. Fills missing keys and clears last turn's scene commands.'''
    state = callback_context.state
    for key, value in DEFAULT_STATE.items():
        if key not in state:
            state[key] = value
    if state.get('impact_report'):
        state['impact_context'] = state['impact_report']
    for key in PER_TURN_KEYS:
        state[key] = ''
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


MAX_HISTORY = 8


def _text(content):
    return ' '.join(part.text or '' for part in (content.parts or []))


def _is_plain_text(content):
    return bool(content.parts) and all(
        part.text and not part.function_call and not part.function_response for part in content.parts)


def trim_history(callback_context, llm_request):
    '''before_model_callback for the root agent. Keeps this turn untouched and shrinks older turns to
    short text, so the router prompt does not grow with every tool result from earlier turns.'''
    contents = list(llm_request.contents or [])
    current = 0
    for i, c in enumerate(contents):
        if c.role == 'user' and _is_plain_text(c) and not _text(c).startswith('For context'):
            current = i
    history = []
    for c in contents[:current]:
        if not _is_plain_text(c):
            continue
        text = _text(c)
        if text.startswith('For context') and not (' said:' in text and len(text) < 600):
            continue
        history.append(c)
    llm_request.contents = history[-MAX_HISTORY:] + contents[current:]
    return None
