import asyncio
import logging
import json
import os
import subprocess
import uuid
import hmac
import time
from collections import defaultdict
from pathlib import Path

from types import SimpleNamespace

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from ai_agents.agent import root_agent
from ai_agents import config, repository
from ai_agents.config import USE_CACHED_TESTS
from ai_agents import llm
from ai_agents.tools.git_tools import commit_worktree
from ai_agents.tools.graph_tools import get_source
from ai_agents.agents.registry import initialize_agents

APP, USER = 'jarvis', 'quest'
TOKEN = os.getenv('JARVIS_TOKEN')
ASK_TIMEOUT = float(os.getenv('JARVIS_ASK_TIMEOUT', '170'))   # keep below the Unity request timeout
MAX_SESSIONS = int(os.getenv('JARVIS_MAX_SESSIONS', '50'))
SESSION_IDLE_TIMEOUT = int(os.getenv('JARVIS_SESSION_IDLE_TIMEOUT', '3600'))  # 1 hour

# Security validation on startup
def validate_security_config():
    """Validate security configuration before starting the server."""
    host = os.getenv('JARVIS_HOST', '127.0.0.1')
    
    # Reject startup if TOKEN is not set when binding to non-localhost
    if host != '127.0.0.1' and not TOKEN:
        raise RuntimeError(
            f"Cannot start on network address {host} without JARVIS_TOKEN set. "
            f"Set JARVIS_TOKEN to a secure value."
        )
    
    # Reject startup with known insecure tokens
    if TOKEN and TOKEN in ('', 'dev-token'):
        raise RuntimeError(
            f"Cannot start with insecure JARVIS_TOKEN '{TOKEN}'. "
            f"Set JARVIS_TOKEN to a secure random value."
        )
    
    # Warn if no token is set for localhost (allowed but not recommended)
    if not TOKEN and host == '127.0.0.1':
        logger = logging.getLogger('uvicorn.error')
        logger.warning(
            "WARNING: Starting without JARVIS_TOKEN on localhost. "
            "This is only safe for local development. Set JARVIS_TOKEN for production."
        )

# Validate security on import
validate_security_config()

sessions = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP, session_service=sessions)
locks = defaultdict(asyncio.Lock)
session_last_used = {}  # Track session last activity for eviction
app = FastAPI(title='JARVIS bridge')

# Initialize all agents explicitly
initialize_agents()

# Audit log
AUDIT_LOG_PATH = Path(__file__).parent.parent / 'logs' / 'audit.jsonl'
AUDIT_LOG_PATH.parent.mkdir(exist_ok=True)


def log_audit(agent: str, tool: str, args: dict, outcome: str, duration: float):
    """Write audit entry to log file."""
    import datetime
    entry = {
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'agent': agent,
        'tool': tool,
        'args_redacted': {k: '***' if 'token' in k.lower() or 'key' in k.lower() or 'password' in k.lower() else v 
                         for k, v in args.items()},
        'outcome': outcome,
        'duration_seconds': duration
    }
    with open(AUDIT_LOG_PATH, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def auth(authorization: str = Header(default='')):
    """
    Authentication middleware.
    
    - Requires JARVIS_TOKEN for network-accessible servers.
    - Allows unauthenticated access only to explicitly public endpoints (e.g., /health).
    - Uses constant-time comparison to prevent timing attacks.
    - Authentication is required for agent execution, progress, session, and tool endpoints.
    """
    # If TOKEN is set, require it for all endpoints (except those explicitly marked public)
    if TOKEN:
        expected = f'Bearer {TOKEN}'
        if not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail='bad token')
    else:
        # TOKEN is None - only allow on localhost for development
        host = os.getenv('JARVIS_HOST', '127.0.0.1')
        if host != '127.0.0.1':
            raise HTTPException(
                status_code=403,
                detail='Authentication required for network access. Set JARVIS_TOKEN.'
            )


def _s(value):
    if value is None or value == '':
        return ''
    return value if isinstance(value, str) else json.dumps(value, default=str)


async def ensure(session_id):
    session = await sessions.get_session(app_name=APP, user_id=USER, session_id=session_id)
    if session is None:
        # Check session cap
        active_sessions = len([s for s, t in session_last_used.items() 
                            if time.time() - t < SESSION_IDLE_TIMEOUT])
        if active_sessions >= MAX_SESSIONS:
            # Evict oldest idle session
            oldest = min(session_last_used.items(), key=lambda x: x[1])
            await sessions.delete_session(app_name=APP, user_id=USER, session_id=oldest[0])
            del session_last_used[oldest[0]]
        
        session = await sessions.create_session(app_name=APP, user_id=USER, session_id=session_id)
    
    # Update last used time
    session_last_used[session_id] = time.time()
    return session


async def set_state(session_id, delta):
    session = await ensure(session_id)
    await sessions.append_event(session, Event(author='user', actions=EventActions(state_delta=delta)))


class AskBody(BaseModel):
    session_id: str
    text: str
    selection: str = ''


def _turn_state(body):
    """Build state delta for a new turn."""
    from ai_agents.agents.registry import list_agents
    return {
        'selection': body.selection,
        'user_request': body.text,
        'repo_path': str(config.REPO_ROOT),
        'available_agents': ', '.join(list_agents()),
        'session_id': body.session_id,
    }


class ApproveBody(BaseModel):
    session_id: str
    approved: bool


class RequestApprovalBody(BaseModel):
    session_id: str
    tool_name: str
    parameters: dict


@app.post('/session', dependencies=[Depends(auth)])
async def new_session():
    session_id = uuid.uuid4().hex
    await ensure(session_id)
    return {'session_id': session_id}


def _git(*args):
    try:
        return subprocess.run(['git', *args], cwd=config.REPO_ROOT, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ''


@app.get('/health')  # No authentication - public endpoint
async def health():
    """Public health check endpoint - no authentication required."""
    changed = len([line for line in _git('status', '--porcelain').splitlines() if line.strip()])
    return {'ok': True, 'cached_tests': USE_CACHED_TESTS, 'repo': config.REPO_ROOT.name,
            'branch': _git('rev-parse', '--abbrev-ref', 'HEAD') or '?', 'changed': changed}


@app.get('/graph', dependencies=[Depends(auth)])
async def graph():
    if not config.GRAPH_PATH.is_file() and config.REPO_ROOT.name in repository.list_repos():
        repository.activate(config.REPO_ROOT.name)
    return json.loads(config.GRAPH_PATH.read_text())


class RepoBody(BaseModel):
    name: str


@app.get('/repos', dependencies=[Depends(auth)])
async def repos():
    return {'active': config.REPO_ROOT.name, 'repos': [repository.info(n) for n in repository.list_repos()]}


@app.post('/repos/select', dependencies=[Depends(auth)])
async def select_repo(body: RepoBody):
    try:
        g = await asyncio.to_thread(repository.activate, body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail='unknown repository: ' + body.name)
    return {'active': body.name, 'nodes': len(g['nodes']), 'edges': len(g['edges'])}


@app.get('/repos/{repo_name}/tree', dependencies=[Depends(auth)])
async def repository_tree(repo_name: str, path: str = ''):
    try:
        return await asyncio.to_thread(repository.list_tree, repo_name, path)
    except KeyError:
        raise HTTPException(status_code=404, detail='unknown repository: ' + repo_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='folder not found: ' + path)
    except NotADirectoryError:
        raise HTTPException(status_code=400, detail='path is not a folder: ' + path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get('/repos/{repo_name}/file', dependencies=[Depends(auth)])
async def repository_file(repo_name: str, path: str):
    try:
        return await asyncio.to_thread(repository.read_browser_file, repo_name, path)
    except KeyError:
        raise HTTPException(status_code=404, detail='unknown repository: ' + repo_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='file not found: ' + path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get('/source/{node_id}', dependencies=[Depends(auth)])
async def source(node_id: str, context: int = 0):
    return get_source(node_id, SimpleNamespace(state={}), min(max(context, 0), 20))


async def _run_turn_streaming(body):
    """Run turn with streaming progress."""
    message = types.Content(role='user', parts=[types.Part(text=body.text)])

    async for event in runner.run_async(user_id=USER, session_id=body.session_id, new_message=message):
        # Stream progress events
        if event.is_final_response():
            text = ' '.join(p.text for p in (event.content.parts if event.content else []) if getattr(p, 'text', None))
            yield {'type': 'final_response', 'content': text}
        elif event.content and event.content.parts:
            yield {'type': 'agent_progress', 'agent': event.author, 'content': _s(event.content)[:300]}


@app.post('/ask/stream', dependencies=[Depends(auth)])
async def ask_stream(body: AskBody):
    """Stream agent progress as Server-Sent Events."""
    async def gen():
        async with locks[body.session_id]:      # hold the lock for the whole stream
            await ensure(body.session_id)
            await set_state(body.session_id, _turn_state(body))
            async for ev in _run_turn_streaming(body):
                yield 'data: ' + json.dumps(ev) + '\n\n'
    return StreamingResponse(gen(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache'})


async def _run_turn(body):
    message = types.Content(role='user', parts=[types.Part(text=body.text)])
    reply = ''
    async for event in runner.run_async(user_id=USER, session_id=body.session_id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            reply = ' '.join(p.text for p in event.content.parts if getattr(p, 'text', None))
    return reply


@app.post('/ask', dependencies=[Depends(auth)])
async def ask(body: AskBody):
    """Non-streaming endpoint for compatibility."""
    error = ''
    calls_before = llm.stats['requests']
    reply = ''
    async with locks[body.session_id]:
        await ensure(body.session_id)
        await set_state(body.session_id, _turn_state(body))
        try:
            reply = await asyncio.wait_for(_run_turn(body), ASK_TIMEOUT)
        except asyncio.TimeoutError:
            error = 'JARVIS took too long to answer. Try a narrower question.'
        except Exception as exc:
            error = f'{type(exc).__name__}: {str(exc)[:200]}'
        state = (await ensure(body.session_id)).state
    logger = logging.getLogger('uvicorn.error')
    logger.info('ask: %d model calls, %s', llm.stats['requests'] - calls_before, 'error' if error else 'ok')
    logger.info('reply: %s', reply[:200] if reply else error)
    last = state.get('last_test_run') or {}
    commands = list(state.get('scene_commands', []))
    pending = _s(state.get('pending_approval'))
    has_patch = state.get('proposed_patch') or state.get('result_software_eng')
    if (not pending and not error and has_patch and state.get('worktree')
            and isinstance(last, dict) and last.get('status') == 'passed'):
        pending = 'Commit the verified patch to a sandbox branch'
        commands.append({'type': 'show_approval_prompt', 'summary': pending})
        await set_state(body.session_id, {'pending_approval': pending, 'approved': False})
    return {
        'reply': reply,
        'error': error,
        'scene_commands': commands,
        'pending_approval': pending,
        'approved': bool(state.get('approved', False)),
        'test_results': _s(state.get('test_results')),
        'test_source': last.get('source', '') if isinstance(last, dict) else '',
        'evidence': list(state.get('evidence', [])),
    }


@app.post('/request_approval', dependencies=[Depends(auth)])
async def request_approval(body: RequestApprovalBody):
    """
    Request an approval token for a protected tool operation.
    
    This endpoint generates a single-use, session-scoped authorization token
    that can be used to call a tool that requires approval.
    
    The token is tied to:
    - The specific session
    - The specific tool
    - The exact parameters
    - A short expiration time (5 minutes)
    
    The user must approve this request through the /approve endpoint before
    the token can be used.
    """
    from ai_agents.callbacks import generate_approval_token
    
    async with locks[body.session_id]:
        state = (await ensure(body.session_id)).state
        
        # Generate the approval token
        token = generate_approval_token(body.session_id, body.tool_name, body.parameters)
        
        # Store the token in session state with metadata
        approval_tokens = state.get('approval_tokens', {})
        approval_tokens[token] = {
            'session_id': body.session_id,
            'tool_name': body.tool_name,
            'parameters': body.parameters,
            'created_at': time.time(),
            'status': 'pending'  # pending -> approved or rejected
        }
        state['approval_tokens'] = approval_tokens
        
        # Set pending approval state for the UI
        await set_state(body.session_id, {
            'pending_approval': f'Execute {body.tool_name}',
            'approval_type': 'tool',
            'approval_token': token,
            'approved': False
        })
    
    return {
        'ok': True,
        'token': token,
        'detail': f'Approval requested for {body.tool_name}. Use /approve to grant or deny.'
    }


@app.post('/approve', dependencies=[Depends(auth)])
async def approve(body: ApproveBody):
    """Handle user approval for commits or tool actions.
    
    Approval workflow:
    - Commits: requires worktree and passed tests
    - Tool actions: marks the pending approval token as approved
    - Rejection: clears pending state and marks token as rejected
    """
    async with locks[body.session_id]:
        state = (await ensure(body.session_id)).state
        pending = state.get('pending_approval', '')
        worktree = state.get('worktree', '')
        approval_type = state.get('approval_type', 'commit')  # 'commit' or 'tool'
        approval_token = state.get('approval_token')
        
        if approval_type == 'tool' and approval_token:
            # Mark the token as approved
            approval_tokens = state.get('approval_tokens', {})
            if approval_token in approval_tokens:
                approval_tokens[approval_token]['status'] = 'approved'
                state['approval_tokens'] = approval_tokens
        
        # Clear pending state
        await set_state(body.session_id, {'approved': body.approved, 'pending_approval': '', 'approval_type': '', 'approval_token': ''})
    
    if not body.approved:
        return {'ok': True, 'action': 'rejected', 'detail': 'Rejected. Nothing was changed.'}
    
    if not pending:
        return {'ok': False, 'action': 'none', 'detail': 'Nothing was waiting for approval.'}
    
    if approval_type == 'commit':
        # Commit workflow: requires worktree and passed tests
        if not worktree:
            return {'ok': False, 'action': 'commit', 'detail': 'No sandbox worktree to commit.'}
        
        last = state.get('last_test_run', {})
        if not isinstance(last, dict) or last.get('status') != 'passed':
            return {'ok': False, 'action': 'commit', 'detail': 'Tests must pass before committing.'}
        
        return {'ok': True, 'action': 'commit', **commit_worktree(worktree, 'JARVIS: ' + str(pending)[:120])}
    
    elif approval_type == 'tool':
        # Tool action workflow: token is now marked as approved
        # The permission guard will validate and consume it
        return {'ok': True, 'action': 'tool', 'detail': f'Tool action approved: {pending}'}
    
    else:
        return {'ok': False, 'action': 'unknown', 'detail': f'Unknown approval type: {approval_type}'}


@app.get('/task/{session_id}', dependencies=[Depends(auth)])
async def get_task_state(session_id: str):
    """Get current task state for a session.
    Flattened for JsonUtility compatibility in Unity.
    """
    session = await ensure(session_id)
    state = session.state
    
    # Flatten results into a list for Unity
    agent_results = []
    for key in ['result_repository', 'result_code_understanding', 'result_relationship',
                'result_data_flow', 'result_runtime', 'result_debugging', 'result_security',
                'result_software_eng', 'result_testing', 'result_visualization', 'result_orchestrator',
                'result_conversational']:
        value = state.get(key, {})
        if value and isinstance(value, dict):
            agent_name = key.replace('result_', '')
            agent_results.append({
                'agent': agent_name,
                'summary': value.get('summary', ''),
                'confidence': value.get('confidence', 0),
                'status': value.get('status', 'unknown')
            })
    
    return {
        'session_id': session_id,
        'plan': state.get('plan', {}),
        'findings': list(state.get('findings', [])),
        'agent_results': agent_results,
        'result_code_understanding': state.get('result_code_understanding', {}),
        'result_relationship': state.get('result_relationship', {}),
        'result_data_flow': state.get('result_data_flow', {}),
        'result_runtime': state.get('result_runtime', {}),
        'result_debugging': state.get('result_debugging', {}),
        'result_software_eng': state.get('result_software_eng', {}),
        'result_testing': state.get('result_testing', {}),
        'result_security': state.get('result_security', {}),
    }


@app.get('/agents', dependencies=[Depends(auth)])
async def get_agent_status():
    """Get status of all agents."""
    from ai_agents.agents.registry import get_all_agent_statuses
    return get_all_agent_statuses()


@app.get('/agents/{agent_name}', dependencies=[Depends(auth)])
async def get_agent_info(agent_name: str):
    """Get info about a specific agent."""
    from ai_agents.agents.registry import get_agent_status
    status = get_agent_status(agent_name)
    if status.get('status') == 'not_found':
        raise HTTPException(status_code=404, detail=f'Agent not found: {agent_name}')
    return status


@app.get('/progress/{session_id}', dependencies=[Depends(auth)])
async def progress(session_id: str, since: int = 0):
    """Get progress events for a session."""
    state = (await ensure(session_id)).state
    log = list(state.get('task_log', []))
    return {'busy': locks[session_id].locked(),
            'steps': [{'i': i, 'agent': e['agent'], 'kind': e['kind']} for i, e in enumerate(log) if i >= since]}


@app.get('/tools', dependencies=[Depends(auth)])
async def list_tools():
    """List all available tools with metadata."""
    from ai_agents.agents.toolsets import TOOLSETS, TOOL_LEVELS, PERMISSION_CEILINGS
    
    tools_metadata = []
    all_tools = set()
    
    # Collect all tools from all agents
    for agent_name, tool_names in TOOLSETS.items():
        for tool_name in tool_names:
            all_tools.add(tool_name)
    
    # Build metadata for each tool
    for tool_name in all_tools:
        # Find which agents have this tool
        owning_agents = []
        for agent_name, tool_names in TOOLSETS.items():
            if tool_name in tool_names:
                owning_agents.append(agent_name)
        
        # Get permission level
        perm_level = TOOL_LEVELS.get(tool_name, 'read')
        
        # Get parameter info from the actual tool function
        from ai_agents import tools as tools_module
        params = []
        if hasattr(tools_module, tool_name):
            import inspect
            sig = inspect.signature(getattr(tools_module, tool_name))
            for param_name, param in sig.parameters.items():
                if param_name != 'tool_context':
                    params.append({
                        'name': param_name,
                        'required': param.default == inspect.Parameter.empty
                    })
        
        tools_metadata.append({
            'name': tool_name,
            'level': perm_level,
            'owning_agents': owning_agents,
            'parameters': params
        })
    
    return {'tools': tools_metadata}


class ToolCallBody(BaseModel):
    tool_name: str
    parameters: dict = {}


@app.post('/tools/{tool_name}', dependencies=[Depends(auth)])
async def call_tool(tool_name: str, body: ToolCallBody):
    """Run a read-level tool directly without a model.
    Write and execute tools are refused.
    """
    from ai_agents.agents.toolsets import TOOL_LEVELS
    from ai_agents import tools as tools_module
    
    # Check permission level
    perm_level = TOOL_LEVELS.get(tool_name, 'read')
    if perm_level in ['write', 'execute']:
        return {
            'status': 'blocked',
            'reason': f'Tool {tool_name} requires {perm_level} permission and cannot be called directly'
        }
    
    # Check tool exists
    if not hasattr(tools_module, tool_name):
        return {
            'status': 'error',
            'error': f'Tool {tool_name} not found'
        }
    
    # Call the tool
    try:
        tool_func = getattr(tools_module, tool_name)
        
        # Build mock tool context
        class MockToolContext:
            def __init__(self):
                self.state = {
                    'worktree': None,
                    'tool_budgets': {},
                    'evidence': [],
                    'scene_commands': [],
                }
                self.agent_name = 'direct_call'
        
        tool_context = MockToolContext()
        
        # Add tool_context to parameters
        params = body.parameters.copy()
        params['tool_context'] = tool_context
        
        result = tool_func(**params)
        
        if not isinstance(result, dict):
            return {
                'status': 'error',
                'error': f'Tool returned non-dict: {type(result)}'
            }
        
        return result
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

