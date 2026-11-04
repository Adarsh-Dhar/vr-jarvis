import asyncio
import base64
import binascii
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
ENABLE_DIRECT_TOOLS = os.getenv('JARVIS_ENABLE_DIRECT_TOOLS', '0') == '1'

# Allowlist for direct tool calls (read-only tools only)
DIRECT_TOOL_ALLOWLIST = {
    'list_files',
    'read_file',
    'read_file_range',
    'search_code',
    'get_symbol_definition',
    'get_symbol_references',
    'get_type_hierarchy',
    'get_imports',
    'get_exports',
    'get_repository_metadata',
    'get_changed_files',
    'git_diff',
    'git_log',
    'git_show',
    'git_status',
    'git_branch',
    'get_worktree_diff',
}

# Quick actions allowlist (model-free tools for Unity)
QUICK_ACTIONS_ALLOWLIST = {
    'find_callers',
    'find_callees',
    'get_symbol_definition',
    'calculate_change_impact',
    'detect_dead_code',
    'calculate_complexity',
    'scan_secrets',
}

# Security validation on startup
def validate_security_config():
    """Validate security configuration before starting the server."""
    # The actual bind address comes from uvicorn config, not JARVIS_HOST
    # We check if the server will be network-exposed (not localhost)
    # This is validated by checking if JARVIS_HOST is set to a non-localhost value
    # or if the uvicorn --host parameter is not 127.0.0.1
    
    # For now, we rely on JARVIS_HOST to indicate intended exposure
    # The actual uvicorn bind address should match JARVIS_HOST
    host = os.getenv('JARVIS_HOST', '127.0.0.1')
    
    # Reject startup with known insecure tokens
    if TOKEN and TOKEN in ('', 'dev-token'):
        raise RuntimeError(
            f"Cannot start with insecure JARVIS_TOKEN '{TOKEN}'. "
            f"Set JARVIS_TOKEN to a secure random value."
        )
    
    # If binding to non-localhost, require token
    if host != '127.0.0.1' and not TOKEN:
        raise RuntimeError(
            f"Cannot start on network address {host} without JARVIS_TOKEN set. "
            f"Set JARVIS_TOKEN to a secure value."
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


# ---------------------------------------------------------------------------
# Speech to text. The headset records the microphone and posts a short WAV here; the server transcribes it with the
# same Gemini API key the agents use, so the Quest build needs no Meta Voice SDK.
STT_MODEL = os.getenv('JARVIS_STT_MODEL', config.MODEL_NAME)
MAX_AUDIO_BYTES = int(os.getenv('JARVIS_MAX_AUDIO_BYTES', str(2_000_000)))   # about 60 s of 16 kHz mono 16-bit audio
STT_PROMPT = ('Transcribe this audio exactly as spoken. Reply with only the transcript text, nothing else. '
              'If there is no speech, reply with an empty string.')


class TranscribeBody(BaseModel):
    audio_base64: str
    mime: str = 'audio/wav'


def _transcribe_audio(audio: bytes, mime: str) -> str:
    """Blocking call to the model. Kept separate so tests can replace it."""
    from google import genai
    client = genai.Client()          # reads GOOGLE_API_KEY (or the Vertex settings) from the environment
    response = client.models.generate_content(
        model=STT_MODEL,
        contents=[types.Part.from_bytes(data=audio, mime_type=mime), STT_PROMPT],
    )
    return (response.text or '').strip().strip('"').strip()


@app.post('/transcribe', dependencies=[Depends(auth)])
async def transcribe(body: TranscribeBody):
    """Speech to text for the VR client. Returns {'text': ..., 'error': ''}."""
    if not body.mime.startswith('audio/'):
        raise HTTPException(status_code=400, detail='mime must be an audio/* type')
    try:
        audio = base64.b64decode(body.audio_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail='audio_base64 is not valid base64')
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail=f'audio is larger than {MAX_AUDIO_BYTES} bytes')
    if len(audio) < 2000:                                  # under ~60 ms of 16 kHz audio: nothing to transcribe
        return {'text': '', 'error': 'audio too short'}
    try:
        text = await asyncio.to_thread(_transcribe_audio, audio, body.mime)
    except Exception as exc:
        logging.getLogger('uvicorn.error').warning('transcribe failed: %s', exc)
        return {'text': '', 'error': f'{type(exc).__name__}: {str(exc)[:160]}'}
    return {'text': text, 'error': ''}


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

            reply = ''
            error = ''
            try:
                async for ev in _run_turn_streaming(body):
                    yield 'data: ' + json.dumps(ev) + '\n\n'
                    if ev.get('type') == 'final_response':
                        reply = ev.get('content', '')
            except asyncio.TimeoutError:
                error = 'JARVIS took too long to answer. Try a narrower question.'
                yield 'data: ' + json.dumps({'type': 'error', 'error': error}) + '\n\n'
            except Exception as exc:
                error = f'{type(exc).__name__}: {str(exc)[:200]}'
                yield 'data: ' + json.dumps({'type': 'error', 'error': error}) + '\n\n'

            # Build and send final response using the same logic as /ask
            state = (await ensure(body.session_id)).state

            # Auto-generate commit approval prompt if conditions are met
            last = state.get('last_test_run') or {}
            pending = _s(state.get('pending_approval'))
            has_patch = state.get('proposed_patch') or state.get('result_software_eng')
            if (not pending and not error and has_patch and state.get('worktree')
                    and isinstance(last, dict) and last.get('status') == 'passed'):
                pending = 'Commit the verified patch to a sandbox branch'
                commands = list(state.get('scene_commands', []))
                commands.append({'type': 'show_approval_prompt', 'summary': pending})
                await set_state(body.session_id, {'pending_approval': pending, 'approved': False, 'approval_type': 'commit'})

            # Send final state response
            final_response = _build_ask_response(reply, error, state)
            yield 'data: ' + json.dumps({'type': 'final_state', 'response': final_response}) + '\n\n'

    return StreamingResponse(gen(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache'})


async def _run_turn(body):
    message = types.Content(role='user', parts=[types.Part(text=body.text)])
    reply = ''
    async for event in runner.run_async(user_id=USER, session_id=body.session_id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            reply = ' '.join(p.text for p in event.content.parts if getattr(p, 'text', None))
    return reply


def _build_ask_response(reply: str, error: str, state: dict) -> dict:
    """Build the standardized response for /ask and /ask/stream endpoints.

    This unified function ensures both endpoints return the same structure.
    """
    last = state.get('last_test_run') or {}
    commands = list(state.get('scene_commands', []))
    pending = _s(state.get('pending_approval'))
    approval_type = state.get('approval_type', '')
    has_patch = state.get('proposed_patch') or state.get('result_software_eng')

    return {
        'reply': reply,
        'error': error,
        'scene_commands': commands,
        'pending_approval': pending,
        'approval_type': approval_type,
        'approved': bool(state.get('approved', False)),
        'test_results': _s(state.get('test_results')),
        'test_source': last.get('source', '') if isinstance(last, dict) else '',
        'evidence': list(state.get('evidence', [])),
    }


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

        # Auto-generate commit approval prompt if conditions are met
        last = state.get('last_test_run') or {}
        pending = _s(state.get('pending_approval'))
        has_patch = state.get('proposed_patch') or state.get('result_software_eng')
        if (not pending and not error and has_patch and state.get('worktree')
                and isinstance(last, dict) and last.get('status') == 'passed'):
            pending = 'Commit the verified patch to a sandbox branch'
            commands = list(state.get('scene_commands', []))
            commands.append({'type': 'show_approval_prompt', 'summary': pending})
            await set_state(body.session_id, {'pending_approval': pending, 'approved': False, 'approval_type': 'commit'})

    logger = logging.getLogger('uvicorn.error')
    logger.info('ask: %d model calls, %s', llm.stats['requests'] - calls_before, 'error' if error else 'ok')
    logger.info('reply: %s', reply[:200] if reply else error)

    return _build_ask_response(reply, error, state)


@app.post('/approve', dependencies=[Depends(auth)])
async def approve(body: ApproveBody):
    """Handle user approval for commits or tool actions.

    Approval workflow:
    - Commits: requires worktree and passed tests
    - Tool actions: marks the pending approval as approved
    - Rejection: clears pending state
    """
    async with locks[body.session_id]:
        state = (await ensure(body.session_id)).state
        pending = state.get('pending_approval', '')
        worktree = state.get('worktree', '')
        approval_type = state.get('approval_type', 'commit')  # 'commit' or 'tool'
        approval_key = state.get('approval_key')

        # Prepare state delta
        delta = {
            'approved': body.approved,
            'pending_approval': '',
            'approval_type': '',
            'approval_key': ''
        }

        if approval_type == 'tool' and approval_key and body.approved:
            # Mark the approval as approved
            pending_approvals = state.get('pending_approvals', {})
            if approval_key in pending_approvals:
                pending_approvals[approval_key]['status'] = 'approved'
                delta['pending_approvals'] = pending_approvals

        # Persist all state changes in a single call
        await set_state(body.session_id, delta)

    if not body.approved:
        return {'ok': True, 'action': 'rejected', 'detail': 'Rejected. Nothing was changed.'}

    if not pending:
        return {'ok': False, 'action': 'none', 'detail': 'Nothing was waiting for approval.'}

    if approval_type == 'commit':
        # Commit workflow: requires worktree and passed tests
        if not worktree:
            return {'ok': False, 'action': 'commit', 'detail': 'No sandbox worktree to commit.'}

        # Re-fetch state to get latest after set_state
        state = (await ensure(body.session_id)).state
        last = state.get('last_test_run', {})
        if not isinstance(last, dict) or last.get('status') != 'passed':
            return {'ok': False, 'action': 'commit', 'detail': 'Tests must pass before committing.'}

        return {'ok': True, 'action': 'commit', **commit_worktree(worktree, 'JARVIS: ' + str(pending)[:120])}

    elif approval_type == 'tool':
        # Tool action workflow: approval is now marked as approved
        # The permission guard will validate and consume it on retry
        return {'ok': True, 'action': 'tool', 'detail': f'Tool action approved: {pending}'}

    else:
        return {'ok': False, 'action': 'unknown', 'detail': f'Unknown approval type: {approval_type}'}


@app.get('/task/{session_id}', dependencies=[Depends(auth)])
async def get_task_state(session_id: str):
    """Get current task state for a session in Unity-compatible format."""
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

    # Extract plan summary
    plan = state.get('plan', {})
    plan_summary = plan.get('summary', '') if isinstance(plan, dict) else str(plan)

    # Extract findings as strings
    findings_raw = state.get('findings', [])
    findings = []
    if isinstance(findings_raw, list):
        for f in findings_raw:
            if isinstance(f, str):
                findings.append(f)
            elif isinstance(f, dict):
                findings.append(f.get('text', str(f)))
            else:
                findings.append(str(f))

    return {
        'busy': locks[session_id].locked(),
        'plan_summary': plan_summary,
        'agent_results': agent_results,
        'findings': findings
    }


@app.get('/agents', dependencies=[Depends(auth)])
async def get_agent_status():
    """Get status of all agents in Unity-compatible format."""
    from ai_agents.agents.registry import get_all_agent_statuses
    from ai_agents.agents.toolsets import PERMISSION_CEILINGS

    all_statuses = get_all_agent_statuses()
    agents_list = []

    for agent_name, status in all_statuses.items():
        if status.get('status') == 'not_found':
            continue

        agents_list.append({
            'name': agent_name,
            'model': status.get('model', 'unknown'),
            'description': status.get('description', ''),
            'tool_count': status.get('tool_count', 0),
            'level': PERMISSION_CEILINGS.get(agent_name, 'read')
        })

    return {'agents': agents_list}


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
    """Get progress events for a session.
    Use this endpoint to light agent status dots in Unity.
    """
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
    parameters: dict = {}


class ActionBody(BaseModel):
    parameters: dict = {}


@app.post('/actions/{action_name}', dependencies=[Depends(auth)])
async def run_action(action_name: str, body: ActionBody):
    """Run a quick action without a model call.
    Returns Unity-compatible response with status, title, lines, and scene_commands.
    """
    from ai_agents.agents.toolsets import TOOL_LEVELS
    from ai_agents import tools as tools_module

    start_time = time.time()
    redacted_args = {k: '***' if 'token' in k.lower() or 'key' in k.lower() or 'password' in k.lower() else v
                     for k, v in body.parameters.items()}

    # Check action is in allowlist
    if action_name not in QUICK_ACTIONS_ALLOWLIST:
        log_audit('quick_action', action_name, redacted_args, 'blocked_not_in_allowlist', time.time() - start_time)
        raise HTTPException(status_code=403, detail=f'Action {action_name} is not in the quick actions allowlist')

    # Check tool exists
    if not hasattr(tools_module, action_name):
        log_audit('quick_action', action_name, redacted_args, 'error_not_found', time.time() - start_time)
        raise HTTPException(status_code=404, detail=f'Action {action_name} not found')

    # Build a session-scoped tool context
    # Note: We need a session_id for the tool context
    session_id = uuid.uuid4().hex
    session = await ensure(session_id)

    class ActionToolContext:
        def __init__(self, session_state):
            self.state = session_state
            self.agent_name = 'quick_action'

    tool_context = ActionToolContext(session.state)

    # Call the tool
    try:
        tool_func = getattr(tools_module, action_name)

        # Add tool_context to parameters
        params = body.parameters.copy()
        params['tool_context'] = tool_context

        result = tool_func(**params)

        # Extract Unity-compatible fields
        status = result.get('status', 'success') if isinstance(result, dict) else 'success'
        title = result.get('title', action_name.replace('_', ' ').title()) if isinstance(result, dict) else action_name.replace('_', ' ').title()
        lines = result.get('lines', []) if isinstance(result, dict) else []
        scene_commands = result.get('scene_commands', []) if isinstance(result, dict) else []

        # Extract evidence if present
        if not lines and 'evidence' in result:
            evidence = result.get('evidence', [])
            if isinstance(evidence, list):
                lines = [str(e) for e in evidence]

        log_audit('quick_action', action_name, redacted_args, 'success', time.time() - start_time)

        return {
            'status': status,
            'title': title,
            'lines': lines,
            'scene_commands': scene_commands
        }

    except HTTPException:
        raise
    except Exception as e:
        log_audit('quick_action', action_name, redacted_args, f'error_{type(e).__name__}', time.time() - start_time)
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/tools/{tool_name}', dependencies=[Depends(auth)])
async def call_tool(tool_name: str, body: ToolCallBody):
    """Run a read-level tool directly without a model.
    Requires JARVIS_ENABLE_DIRECT_TOOLS=1 and tool must be in allowlist.
    """
    from ai_agents.agents.toolsets import TOOL_LEVELS
    from ai_agents import tools as tools_module

    start_time = time.time()
    outcome = 'blocked'

    # Check if direct tools are enabled
    if not ENABLE_DIRECT_TOOLS:
        log_audit('direct_call', tool_name, body.parameters, 'blocked_feature_disabled', time.time() - start_time)
        raise HTTPException(status_code=403, detail='Direct tool calls are disabled. Set JARVIS_ENABLE_DIRECT_TOOLS=1 to enable.')

    # Check tool is in permission table - fail closed
    if tool_name not in TOOL_LEVELS:
        log_audit('direct_call', tool_name, body.parameters, 'blocked_unlisted', time.time() - start_time)
        raise HTTPException(status_code=403, detail=f'Tool {tool_name} is not in the permission table and cannot be called directly')

    # Check permission level
    perm_level = TOOL_LEVELS[tool_name]
    if perm_level != 'read':
        log_audit('direct_call', tool_name, body.parameters, 'blocked_permission', time.time() - start_time)
        raise HTTPException(status_code=403, detail=f'Tool {tool_name} requires {perm_level} permission and cannot be called directly')

    # Check tool is in allowlist
    if tool_name not in DIRECT_TOOL_ALLOWLIST:
        log_audit('direct_call', tool_name, body.parameters, 'blocked_not_in_allowlist', time.time() - start_time)
        raise HTTPException(status_code=403, detail=f'Tool {tool_name} is not in the direct tool allowlist')

    # Check tool exists
    if not hasattr(tools_module, tool_name):
        log_audit('direct_call', tool_name, body.parameters, 'error_not_found', time.time() - start_time)
        raise HTTPException(status_code=404, detail=f'Tool {tool_name} not found')

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
            log_audit('direct_call', tool_name, body.parameters, 'error_invalid_result', time.time() - start_time)
            raise HTTPException(status_code=500, detail=f'Tool returned non-dict: {type(result)}')

        log_audit('direct_call', tool_name, body.parameters, 'success', time.time() - start_time)
        return result

    except HTTPException:
        raise
    except Exception as e:
        log_audit('direct_call', tool_name, body.parameters, f'error_{type(e).__name__}', time.time() - start_time)
        raise HTTPException(status_code=500, detail=str(e))

