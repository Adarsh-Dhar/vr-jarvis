import time

from .config import USE_CACHED_TESTS
from .state import DEFAULT_STATE


# Results that belong to one request. They are cleared every turn so no agent sees a previous turn's data.
PER_TURN_KEYS = ['changed_nodes', 'impact_static', 'tests_relevant', 'impact_report', 'answer_draft',
                 'proposed_patch', 'test_results', 'verified_answer', 'briefing',
                 'result_repository', 'result_code_understanding', 'result_relationship',
                 'result_data_flow', 'result_runtime', 'result_debugging',
                 'result_security', 'result_software_eng', 'result_testing',
                 'result_visualization', 'result_orchestrator', 'result_conversational']


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
    state['task_log'] = []
    # Initialize tool budgets in session state (not module global)
    if 'tool_budgets' not in state:
        state['tool_budgets'] = {}
    return None


def log_agent_start(callback_context):
    log = list(callback_context.state.get('task_log', []))
    log.append({'agent': callback_context.agent_name, 'kind': 'start', 'at': time.time()})
    callback_context.state['task_log'] = log[-60:]
    return None


# commit_changes and merge_branch are intentionally not implemented in this reference.
# If you add them later, this guard already protects them.
TIER2_TOOLS = {'commit_changes', 'merge_branch'}

# Permission levels for tools
PERMISSION_LEVELS = {
    "read": 0,
    "execute": 1,
    "write": 2,
}


# Tool budget tracking is now in session state['tool_budgets']

# Tool permission assignments (from toolsets.py TOOL_LEVELS)
from .agents.toolsets import TOOL_LEVELS as TOOL_PERMISSIONS


def permission_guard(tool, args, tool_context):
    '''before_tool_callback. Returning a dict skips the tool call.'''
    name = tool.name

    # Use tool_context.agent_name (from ADK) instead of state['calling_agent']
    calling_agent = tool_context.agent_name
    
    if calling_agent:
        from .agents.toolsets import PERMISSION_CEILINGS
        from .agents.registry import AGENT_CONFIG
        agent_ceiling = PERMISSION_CEILINGS.get(calling_agent, "read")
        
        # Fail closed: tool missing from permission table is blocked for read-only agents
        tool_perm = TOOL_PERMISSIONS.get(name)
        if tool_perm is None:
            # Tool not in permission table - block for read-only agents
            if PERMISSION_LEVELS.get(agent_ceiling, 0) < PERMISSION_LEVELS.get("write", 2):
                return {
                    'status': 'blocked',
                    'reason': f'Tool {name} is not in the permission table and agent {calling_agent} has {agent_ceiling} ceiling'
                }
            tool_perm = "read"  # Default to read for write agents

        # Check if tool exceeds agent's permission ceiling
        if PERMISSION_LEVELS.get(tool_perm, 0) > PERMISSION_LEVELS.get(agent_ceiling, 0):
            return {
                'status': 'blocked',
                'reason': f'Tool {name} requires {tool_perm} permission, agent {calling_agent} has {agent_ceiling}'
            }

        # Check tool budget from session state
        tool_budgets = tool_context.state.get('tool_budgets', {})
        if calling_agent not in tool_budgets:
            tool_budgets[calling_agent] = 0
            tool_context.state['tool_budgets'] = tool_budgets
        
        # Get agent's tool budget from AGENT_CONFIG
        agent_config = AGENT_CONFIG.get(calling_agent, {})
        budget = agent_config.get("tool_budget", 20)  # Default budget
        if tool_budgets[calling_agent] >= budget:
            return {
                'status': 'blocked',
                'reason': f'Agent {calling_agent} exceeded tool budget of {budget}'
            }
        tool_budgets[calling_agent] += 1
        tool_context.state['tool_budgets'] = tool_budgets

    # Original tier2 checks
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


def evidence_collector(callback_context, tool_result):
    """Phase 1.4: after_tool_callback that copies evidence from tool results into state."""
    state = callback_context.state

    # Initialize evidence list if needed
    if "evidence" not in state:
        state["evidence"] = []

    # Extract evidence from tool result
    if isinstance(tool_result, dict):
        # Common evidence fields
        evidence_fields = ["node_id", "file", "start", "end", "evidence", "nodes", "references"]

        for field in evidence_fields:
            if field in tool_result and tool_result[field]:
                # Add to evidence list
                if isinstance(tool_result[field], list):
                    state["evidence"].extend(tool_result[field])
                else:
                    state["evidence"].append(tool_result[field])

    return None


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
