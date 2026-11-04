import time
import secrets
import hashlib
import json

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

# Permission levels for tools
PERMISSION_LEVELS = {
    "read": 0,
    "execute": 1,
    "write": 2,
}


# Tool budget tracking is now in session state['tool_budgets']

# Tool permission assignments (from toolsets.py TOOL_LEVELS)
from .agents.toolsets import TOOL_LEVELS as TOOL_PERMISSIONS


def generate_approval_token(session_id: str, tool_name: str, args: dict) -> str:
    """
    Generate a single-use, session-scoped approval token.
    
    The token is tied to:
    - session_id: The specific session
    - tool_name: The specific tool being called
    - args: The exact arguments (hashed for consistency)
    - A random nonce to prevent guessing
    
    Tokens are stored in session state with an expiration time.
    """
    # Create a deterministic hash of the arguments
    args_hash = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]
    
    # Generate a random nonce
    nonce = secrets.token_hex(16)
    
    # Create the token
    token = f"{session_id}:{tool_name}:{args_hash}:{nonce}"
    
    return token


def validate_approval_token(token: str, session_id: str, tool_name: str, args: dict, tool_context) -> bool:
    """
    Validate and consume an approval token.
    
    Returns True if the token is valid, approved, and was consumed.
    Returns False if the token is invalid, expired, not approved, or already used.
    """
    state = tool_context.state
    
    # Get pending approval tokens from session state
    approval_tokens = state.get('approval_tokens', {})
    
    # Check if token exists
    if token not in approval_tokens:
        return False
    
    # Get token metadata
    token_data = approval_tokens[token]
    
    # CRITICAL: Check if token was actually approved by the user
    if token_data.get('status') != 'approved':
        # Token exists but was not approved (rejected or still pending)
        return False
    
    # Verify token matches the current request
    if token_data.get('session_id') != session_id:
        return False
    if token_data.get('tool_name') != tool_name:
        return False
    
    # Verify arguments match (optional - can be strict or loose)
    args_hash = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]
    if token_data.get('args_hash') != args_hash:
        return False
    
    # Check expiration (5 minutes default)
    import time
    if time.time() - token_data.get('created_at', 0) > 300:
        # Token expired
        del approval_tokens[token]
        state['approval_tokens'] = approval_tokens
        return False
    
    # Token is valid and approved - consume it (single-use)
    del approval_tokens[token]
    state['approval_tokens'] = approval_tokens
    
    return True


def permission_guard(tool, args, tool_context):
    '''
    before_tool_callback. Returning a dict skips the tool call.
    
    Enforces:
    - Permission ceilings per agent
    - Tool budgets per session
    - Single-use approval tokens for protected operations
    - Audit logging for all authorization attempts
    '''
    name = tool.name
    start_time = time.time()
    outcome = 'blocked'
    redacted_args = {k: '***' if 'token' in k.lower() or 'key' in k.lower() or 'password' in k.lower() else v 
                     for k, v in args.items()}

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
        
        # Increment per-turn budget (atomic - this happens before tool execution)
        per_turn_budgets[calling_agent] += 1
        tool_context.state['per_turn_budgets'] = per_turn_budgets
        
        # Increment concurrent call count (atomic)
        concurrent_calls[calling_agent] = current_concurrent + 1
        tool_context.state['concurrent_calls'] = concurrent_calls
        
        # Store tool start time for timeout tracking
        tool_timeouts = tool_context.state.get('tool_timeouts', {})
        if not isinstance(tool_timeouts, dict):
            tool_timeouts = {}
            tool_context.state['tool_timeouts'] = tool_timeouts
        tool_timeouts[name] = {'start_time': time.time(), 'agent': calling_agent}
        tool_context.state['tool_timeouts'] = tool_timeouts

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
    
    # Check for approval token if tool requires it
    # Tools that require approval tokens can be listed in TIER2_TOOLS or checked via permissions
    # For now, we check if the tool is in a list that requires approval
    if name in TIER2_TOOLS:
        # Check for valid approval token
        approval_token = args.get('approval_token')
        if approval_token:
            session_id = tool_context.state.get('session_id', '')
            if not validate_approval_token(approval_token, session_id, name, args, tool_context):
                outcome = 'blocked_invalid_token'
                _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
                return {
                    'status': 'blocked',
                    'reason': 'Invalid or expired approval token'
                }
        else:
            outcome = 'blocked_no_token'
            _log_authorization(calling_agent, name, redacted_args, outcome, time.time() - start_time)
            return {
                'status': 'blocked',
                'reason': 'This action requires a valid approval token'
            }
    
    # Permission granted
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

    # Decrement concurrent call count after tool completes
    calling_agent = callback_context.agent_name
    if calling_agent:
        concurrent_calls = state.get('concurrent_calls', {})
        if isinstance(concurrent_calls, dict) and calling_agent in concurrent_calls:
            concurrent_calls[calling_agent] = max(0, concurrent_calls[calling_agent] - 1)
            state['concurrent_calls'] = concurrent_calls

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
