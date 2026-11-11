import time
import secrets
import hashlib
import json

from .config import USE_CACHED_TESTS
from .state import DEFAULT_STATE


# Results that belong to one request. They are cleared every turn so no agent sees a previous turn's data.
PER_TURN_KEYS = ['changed_nodes', 'impact_static', 'tests_relevant', 'impact_report', 'answer_draft',
                 'proposed_patch', 'test_results', 'code_review', 'verified_answer',
                 'result_repository', 'result_code_understanding', 'result_relationship',
                 'result_data_flow', 'result_software_eng', 'result_testing',
                 'result_visualization', 'result_orchestrator', 'result_conversational',
                 'result_implementation_planning']


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
    
    # Reset per-turn budgets at the start of each new turn
    # We track per-turn budgets separately from session-wide budgets
    if 'per_turn_budgets' not in state:
        state['per_turn_budgets'] = {}
    else:
        # Reset per-turn budgets for a new turn
        state['per_turn_budgets'] = {}
    
    # Initialize session-scoped spatial state
    if 'session_states' not in state:
        state['session_states'] = {}
    
    # Initialize concurrent call tracking
    if 'concurrent_calls' not in state:
        state['concurrent_calls'] = {}
    
    # Initialize per-tool timeout tracking
    if 'tool_timeouts' not in state:
        state['tool_timeouts'] = {}
    
    return None


def log_agent_start(callback_context):
    log = list(callback_context.state.get('task_log', []))
    log.append({'agent': callback_context.agent_name, 'kind': 'start', 'at': time.time()})
    callback_context.state['task_log'] = log[-60:]
    return None


# commit_changes and merge_branch are intentionally not implemented in this reference.
# If you add them later, this guard already protects them.
TIER2_TOOLS = {'commit_changes', 'merge_branch'}

# Write tools that can only touch the sandbox worktree (or session bookkeeping). The human gate for
# these changes is the commit approval in /approve, not a hold gesture per tool call; commit_changes
# and merge_branch stay in TIER2_TOOLS.
SANDBOX_WRITE_TOOLS = {
    'create_worktree', 'apply_patch_to_worktree', 'record_task_targets', 'edit_file', 'apply_patch',
    'search_and_replace', 'format_code', 'organize_imports',
}

# Permission levels for tools
PERMISSION_LEVELS = {
    "read": 0,
    "execute": 1,
    "write": 2,
}


# Tool budget tracking is now in session state['tool_budgets']

# Tool permission assignments (from toolsets.py TOOL_LEVELS)
from .agents.toolsets import TOOL_LEVELS as TOOL_PERMISSIONS


def _record_grant(state, calling_agent: str, name: str) -> None:
    """Count a tool call that was actually granted. Blocked attempts must not
    consume budget or leak a concurrent-call slot."""
    per_turn_budgets = state.get('per_turn_budgets')
    if not isinstance(per_turn_budgets, dict):
        per_turn_budgets = {}
    per_turn_budgets[calling_agent] = per_turn_budgets.get(calling_agent, 0) + 1
    state['per_turn_budgets'] = per_turn_budgets

    concurrent_calls = state.get('concurrent_calls')
    if not isinstance(concurrent_calls, dict):
        concurrent_calls = {}
    concurrent_calls[calling_agent] = concurrent_calls.get(calling_agent, 0) + 1
    state['concurrent_calls'] = concurrent_calls

    tool_timeouts = state.get('tool_timeouts')
    if not isinstance(tool_timeouts, dict):
        tool_timeouts = {}
    tool_timeouts[name] = {'start_time': time.time(), 'agent': calling_agent}
    state['tool_timeouts'] = tool_timeouts


def generate_approval_key(tool_name: str, args: dict) -> str:
    """
    Generate a deterministic key for an approval request.
    Used to identify if a retried tool call matches a previously approved request.
    """
    args_hash = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]
    return f"{tool_name}:{args_hash}"


def validate_approval(tool_name: str, args: dict, tool_context) -> bool:
    """
    Check if a tool call has been approved via the hold gesture.

    The approval flow:
    1. permission_guard blocks a write tool and stores {tool_name, args_hash, status: 'pending'} in state
    2. User holds, Unity calls /approve, which marks status: 'approved'
    3. Agent retries the tool call with same tool_name and args
    4. This function checks if {tool_name, args_hash} exists and is approved
    5. If approved, consume it (single-use) and return True

    Returns True if the call was approved and consumed.
    Returns False if not approved, expired, or already used.
    """
    state = tool_context.state

    # Get pending approvals from session state
    pending_approvals = state.get('pending_approvals', {})

    # Generate the approval key
    approval_key = generate_approval_key(tool_name, args)

    # Check if approval exists
    if approval_key not in pending_approvals:
        return False

    # Get approval metadata
    approval_data = pending_approvals[approval_key]

    # Check if approval was granted
    if approval_data.get('status') != 'approved':
        return False

    # Check expiration (5 minutes default)
    if time.time() - approval_data.get('created_at', 0) > 300:
        # Approval expired
        del pending_approvals[approval_key]
        state['pending_approvals'] = pending_approvals
        return False

    # Approval is valid - consume it (single-use)
    del pending_approvals[approval_key]
    state['pending_approvals'] = pending_approvals

    return True


def permission_guard(tool, args, tool_context):
    '''
    before_tool_callback. Returning a dict skips the tool call.

    Enforces:
    - Permission ceilings per agent
    - Tool budgets per session
    - Approval workflow for write tools (server-side via hold gesture)
    - Audit logging for all authorization attempts
    '''
    name = tool.name
    start_time = time.time()
    outcome = 'blocked'
    redacted_args = {k: '***' if 'token' in k.lower() or 'key' in k.lower() or 'password' in k.lower() else v
                     for k, v in args.items()}

    # Tool-contract validation: arguments must satisfy the registered input
    # schema before permission checks run. This is additive to permissions.
    try:
        from .registry.tool_registry import get_tool_registry
        arg_errors = get_tool_registry().validate_arguments(name, args or {})
        if arg_errors:
            outcome = 'blocked_contract'
            _log_authorization(tool_context.agent_name, name, redacted_args, outcome, time.time() - start_time)
            return {'status': 'error', 'error': 'Invalid arguments for %s: %s' % (name, '; '.join(arg_errors)),
                    'validation': 'input_schema'}
    except Exception:
        pass  # contract validation must never break tool dispatch

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
                outcome = 'blocked_permission_table'
                _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
                return {
                    'status': 'blocked',
                    'reason': f'Tool {name} is not in the permission table and agent {calling_agent} has {agent_ceiling} ceiling'
                }
            tool_perm = "read"  # Default to read for write agents

        # Check if tool exceeds agent's permission ceiling
        if PERMISSION_LEVELS.get(tool_perm, 0) > PERMISSION_LEVELS.get(agent_ceiling, 0):
            outcome = 'blocked_ceiling'
            _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
            return {
                'status': 'blocked',
                'reason': f'Tool {name} requires {tool_perm} permission, agent {calling_agent} has {agent_ceiling}'
            }

        # Check tool budget from session state
        # Use per-turn budgets that reset at the start of each new turn
        per_turn_budgets = tool_context.state.get('per_turn_budgets')
        if not isinstance(per_turn_budgets, dict):
            per_turn_budgets = {}
            tool_context.state['per_turn_budgets'] = per_turn_budgets
        if calling_agent not in per_turn_budgets:
            per_turn_budgets[calling_agent] = 0
            tool_context.state['per_turn_budgets'] = per_turn_budgets

        # Get agent's tool budget from AGENT_CONFIG
        agent_config = AGENT_CONFIG.get(calling_agent, {})
        budget = agent_config.get("tool_budget", 20)  # Default budget per turn
        if per_turn_budgets[calling_agent] >= budget:
            outcome = 'blocked_budget'
            _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
            return {
                'status': 'blocked',
                'reason': f'Agent {calling_agent} exceeded per-turn tool budget of {budget}'
            }

        # Check concurrent call limits
        concurrent_calls = tool_context.state.get('concurrent_calls', {})
        if not isinstance(concurrent_calls, dict):
            concurrent_calls = {}
            tool_context.state['concurrent_calls'] = concurrent_calls

        # Get concurrent limit from AGENT_CONFIG (default 5)
        concurrent_limit = agent_config.get("concurrent_limit", 5)
        current_concurrent = concurrent_calls.get(calling_agent, 0)
        if current_concurrent >= concurrent_limit:
            outcome = 'blocked_concurrent'
            _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
            return {
                'status': 'blocked',
                'reason': f'Agent {calling_agent} exceeded concurrent call limit of {concurrent_limit}'
            }

    tool_perm = TOOL_PERMISSIONS.get(name, 'read')   # also defined when there is no calling agent

    # Original tier2 checks
    if name in TIER2_TOOLS and not tool_context.state.get('approved'):
        outcome = 'blocked_tier2'
        _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
        return {'status': 'blocked', 'reason': 'This action needs explicit user approval.'}
    if name in {'run_tests', 'run_typecheck'} and not USE_CACHED_TESTS:
        if not tool_context.state.get('worktree'):
            outcome = 'blocked_worktree'
            _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
            return {'status': 'blocked', 'reason': 'Create a sandbox worktree first.'}

    # NEW: Approval workflow for write tools
    # If tool requires write permission, check if it's been approved via hold gesture
    if tool_perm == 'write' and name in SANDBOX_WRITE_TOOLS:
        # Sandbox-only write: allowed once the ceiling/budget checks above passed.
        if name != 'create_worktree' and not tool_context.state.get('worktree') \
                and name != 'record_task_targets':
            return {'status': 'blocked', 'reason': 'Create a sandbox worktree first.'}
        if calling_agent:
            _record_grant(tool_context.state, calling_agent, name)
        _log_authorization(calling_agent, name, redacted_args, 'granted_sandbox', time.time() - start_time)
        return None
    if tool_perm == 'write':
        # Check if this call was previously approved
        if validate_approval(name, args, tool_context):
            # Approved - proceed with execution
            _record_grant(tool_context.state, calling_agent, name)
            outcome = 'granted'
            _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
            return None

        # Not approved - store approval request and block
        approval_key = generate_approval_key(name, args)
        pending_approvals = tool_context.state.get('pending_approvals', {})
        pending_approvals[approval_key] = {
            'tool_name': name,
            'args': args,
            'created_at': time.time(),
            'status': 'pending'
        }
        tool_context.state['pending_approvals'] = pending_approvals

        # Set UI state for approval prompt
        tool_context.state['pending_approval'] = f'Execute {name}'
        tool_context.state['approval_type'] = 'tool'
        tool_context.state['approval_key'] = approval_key
        tool_context.state['approved'] = False

        outcome = 'blocked_needs_approval'
        _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
        return {
            'status': 'blocked',
            'reason': f'Tool {name} requires user approval (hold gesture)',
            'approval_key': approval_key
        }

    # Permission granted
    if calling_agent:
        _record_grant(tool_context.state, calling_agent, name)
    outcome = 'granted'
    _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
    return None


def _log_authorization(agent: str, tool: str, args: dict, outcome: str, duration: float):
    """Log authorization attempt to audit log."""
    import datetime
    from pathlib import Path
    
    AUDIT_LOG_PATH = Path(__file__).parent.parent.parent / 'logs' / 'audit.jsonl'
    AUDIT_LOG_PATH.parent.mkdir(exist_ok=True)
    
    entry = {
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'type': 'authorization',
        'agent': agent,
        'tool': tool,
        'args_redacted': args,
        'outcome': outcome,
        'duration_seconds': duration
    }
    
    try:
        with open(AUDIT_LOG_PATH, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception:
        # Don't fail the operation if logging fails
        pass


MAX_HISTORY = 8


def _text(content):
    return ' '.join(part.text or '' for part in (content.parts or []))


def _is_plain_text(content):
    return bool(content.parts) and all(
        part.text and not part.function_call and not part.function_response for part in content.parts)


def evidence_collector(tool, args, tool_context, tool_response):
    """Phase 1.4: after_tool_callback that copies evidence from tool results into state
    and releases the concurrent-call slot taken by permission_guard."""
    state = tool_context.state

    # Initialize evidence list if needed
    if "evidence" not in state:
        state["evidence"] = []

    # Extract evidence from tool result
    if isinstance(tool_response, dict):
        # Common evidence fields
        evidence_fields = ["node_id", "file", "start", "end", "evidence", "nodes", "references"]

        for field in evidence_fields:
            if field in tool_response and tool_response[field]:
                # Add to evidence list
                if isinstance(tool_response[field], list):
                    state["evidence"].extend(tool_response[field])
                else:
                    state["evidence"].append(tool_response[field])

    # Decrement concurrent call count
    calling_agent = tool_context.agent_name
    concurrent_calls = state.get('concurrent_calls', {})
    if calling_agent in concurrent_calls and concurrent_calls[calling_agent] > 0:
        concurrent_calls[calling_agent] -= 1
        state['concurrent_calls'] = concurrent_calls

    # Tool-contract validation: results must satisfy the registered output
    # schema. A violation replaces the response with a structured error.
    try:
        from .registry.tool_registry import get_tool_registry
        output_errors = get_tool_registry().validate_result(tool.name, tool_response)
        if output_errors:
            return {'status': 'error',
                    'error': 'Tool %s returned an invalid result: %s' % (tool.name, '; '.join(output_errors)),
                    'validation': 'output_schema'}
    except Exception:
        pass

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
