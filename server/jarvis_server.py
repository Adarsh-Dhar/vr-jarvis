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
from typing import Optional, Dict, Any, List

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
from ai_agents.tools.git_tools import commit_worktree, promote_branch
from ai_agents.tools.exec_tools import _worktree_fingerprint, verification_blockers
from ai_agents.tools.graph_tools import get_source
from ai_agents.agents.registry import initialize_agents

APP, USER = 'jarvis', 'quest'
TOKEN = os.getenv('JARVIS_TOKEN')
ASK_TIMEOUT = float(os.getenv('JARVIS_ASK_TIMEOUT', '170'))   # keep below the Unity request timeout
TURN_TIMEOUT = float(os.getenv('JARVIS_TURN_TIMEOUT', '120'))
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

try:
    from google.adk.sessions import DatabaseSessionService
    sessions = DatabaseSessionService(
        db_url=os.getenv('JARVIS_SESSION_DB', 'sqlite+aiosqlite:///' + str(config.ROOT / 'data' / 'sessions.db')))
except Exception:
    # sqlalchemy/aiosqlite not installed: sessions live only for this process.
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


async def _sessions_blocking_switch():
    """Sessions that make a repository switch unsafe, derived from the REAL session state (which agent
    tools write directly) and from live locks, never from a side table that set_state() alone feeds.
    Returns a list of (session_id, reason)."""
    out = []
    for sid in list(session_last_used):
        if locks[sid].locked():
            out.append((sid, 'an agent request is running'))
            continue
        sess = await sessions.get_session(app_name=APP, user_id=USER, session_id=sid)
        if sess is None:
            continue
        st = sess.state
        wt = st.get('worktree')
        if wt and Path(str(wt)).is_dir():
            out.append((sid, 'a sandbox worktree exists'))
        elif st.get('pending_approval'):
            out.append((sid, 'an approval is pending'))
        elif isinstance(st.get('last_commit'), dict) and st['last_commit'].get('branch'):
            out.append((sid, 'a committed change is not promoted'))
    return out


def _refuse_if_switching():
    if repo_lock.locked():
        raise HTTPException(status_code=409, detail='A repository switch is in progress. Retry in a moment.')


@app.on_event('startup')
async def _register_persisted_sessions():
    """Sessions persisted in the database survive a restart, but session_last_used does not. Re-register
    them so the repo-switch guard sees their worktrees / pending approvals / unpromoted commits."""
    try:
        resp = await sessions.list_sessions(app_name=APP, user_id=USER)
        for sess in (getattr(resp, 'sessions', None) or []):
            session_last_used.setdefault(sess.id, time.time())
    except Exception as exc:   # in-memory service or empty DB
        logging.getLogger('uvicorn.error').info('no persisted sessions registered: %s', exc)


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
    repo: Optional[str] = None
    task_id: Optional[str] = None   # set when the ask implements a plan task (WORK ON IT)
    request_id: Optional[str] = None  # client-generated id; retries are ignored


def _active_task_record(state, task_id):
    """Resolve a plan task into the full record the coding agent needs.
    Returns (record, error); error is an HTTP detail string when the task
    cannot be started (missing, stale, done or blocked)."""
    plan = state.get('implementation_plan') or {}
    tasks = plan.get('tasks') or []
    task = next((t for t in tasks if str(t.get('id')) == str(task_id)), None)
    if task is None:
        return None, 'Task not found in the implementation plan: ' + str(task_id)
    arch = state.get('design') or {}
    # The plan is only valid for the architecture revision it was generated from.
    if arch.get('status') != 'approved' or \
            plan.get('architecture_revision') != arch.get('approved_revision'):
        return None, 'Task plan is stale: the architecture changed since the plan was generated. Regenerate the plan.'
    status = task.get('status') or 'pending'
    if status in ('done', 'completed'):
        return None, 'Task ' + str(task_id) + ' is already done.'
    done_ids = {str(t.get('id')) for t in tasks
                if (t.get('status') or 'pending') in ('done', 'completed')}
    missing = [str(d) for d in (task.get('depends_on') or []) if str(d) not in done_ids]
    if missing:
        return None, 'Task ' + str(task_id) + ' is blocked by unfinished dependencies: ' + ', '.join(missing)
    # Tasks inside a dependency cycle need explicit acceptance first.
    cyclic_ids = set()
    for path in (plan.get('cycle_paths') or []):
        cyclic_ids.update(str(x) for x in path)
    if str(task.get('component_id') or '') in cyclic_ids and not task.get('cycle_accepted'):
        return None, ('Task ' + str(task_id) + ' is part of a circular dependency '
                      '(see cycle_paths). Accept the cycle with a rationale via '
                      'PATCH /plan/{session}/tasks/{id} first.')
    return {
        'id': str(task.get('id')), 'title': task.get('title') or '',
        'description': task.get('description') or task.get('acceptance') or '',
        'component_id': str(task.get('component_id') or ''),
        'files': list(task.get('files') or task.get('suggested_files') or []),
        'symbols': task.get('symbols') or [],
        'acceptance_criteria': [str(c) for c in (task.get('acceptance_criteria') or [])],
        'depends_on': [str(d) for d in (task.get('depends_on') or [])],
        'repo': plan.get('repo') or state.get('repo') or '',
        'design_revision': plan.get('architecture_revision'),
        'repo_match': str(task.get('repo_match') or ''),
        'needs_investigation': bool(task.get('needs_investigation')),
    }, None


def _turn_state(body, session_state=None):
    """Build state delta for a new turn."""
    from ai_agents.agents.registry import list_agents
    state = {
        'selection': body.selection,
        'user_request': body.text,
        'repo_path': str(config.REPO_ROOT),
        'available_agents': ', '.join(list_agents()),
        'session_id': body.session_id,
        # Links this turn's code change back to its plan task so /promote
        # completes only that task. Cleared by any ask that is not task work.
        'active_task_id': (body.task_id or '').strip(),
    }
    task_id = state['active_task_id']
    if task_id:
        if session_state is None:
            state['active_task'] = {}
        else:
            record, err = _active_task_record(session_state, task_id)
            if err:
                raise HTTPException(status_code=409, detail=err)
            state['active_task'] = record
    else:
        state['active_task'] = {}
    return state


class ApproveBody(BaseModel):
    session_id: str
    approved: bool
    repo: Optional[str] = None
    request_id: Optional[str] = None   # client-generated id; retries are ignored


@app.post('/session', dependencies=[Depends(auth)])
async def new_session():
    session_id = uuid.uuid4().hex
    await ensure(session_id)
    await set_state(session_id, {'repo': config.REPO_ROOT.name})   # bound for the session's life
    return {'session_id': session_id}


repo_lock = asyncio.Lock()


def _require_active_repo(name: Optional[str]):
    if name and name != config.REPO_ROOT.name:
        raise HTTPException(status_code=409,
            detail=f'Active repository is {config.REPO_ROOT.name}, not {name}. Select it again.')


async def _check_session_repo(session_id):
    """Design/plan endpoints carry no repo field: verify the session was started
    against the currently active repository, else its plan/design would apply
    to the wrong codebase."""
    state = (await ensure(session_id)).state
    sess_repo = state.get('repo')
    if not sess_repo:
        await set_state(session_id, {'repo': config.REPO_ROOT.name})
        return
    if sess_repo != config.REPO_ROOT.name:
        raise HTTPException(status_code=409,
            detail=f'Session repository is {sess_repo}, but the active repository '
                   f'is {config.REPO_ROOT.name}. Start a new session.')


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
            'branch': _git('rev-parse', '--abbrev-ref', 'HEAD') or '?', 'changed': changed,
            'semantic_languages': ['python', 'javascript', 'typescript'],
            'analysis_support': {
                'python': {'structure': True, 'calls': True, 'cfg': True, 'dfg': True},
                'typescript': {'structure': True, 'calls': True, 'cfg': False, 'dfg': False},
                'javascript': {'structure': True, 'calls': True, 'cfg': False, 'dfg': False},
                'other': {'structure': True, 'calls': False, 'cfg': False, 'dfg': False}},
            'persistence_warnings': list(_PERSIST_WARNINGS)}


@app.get('/graph', dependencies=[Depends(auth)])
async def graph(focus: Optional[str] = None, depth: int = 2, direction: str = 'both', resolution: Optional[str] = None):
    """Return the graph, optionally filtered by focus node, depth, direction, and resolution status."""
    if not config.GRAPH_PATH.is_file() and config.REPO_ROOT.name in repository.list_repos():
        repository.activate(config.REPO_ROOT.name)
    
    graph_data = json.loads(config.GRAPH_PATH.read_text())
    
    # If focus is specified, return a subgraph around that node
    if focus:
        from ai_agents.intelligence.graph_engine.codegraph import load_current_graph
        codegraph = load_current_graph()
        
        focus_node = codegraph.get(focus)
        if not focus_node:
            raise HTTPException(status_code=404, detail=f"Focus node not found: {focus}")
        
        # Use neighborhood method with filters
        include_unresolved = resolution is None or resolution in ['unresolved', 'all']
        hide_external = resolution == 'internal' if resolution else False
        
        neighborhood = codegraph.neighborhood(
            node_id=focus_node['id'],
            depth=depth,
            direction=direction,
            include_unresolved=include_unresolved,
            hide_external=hide_external,
            max_nodes=1000
        )
        
        return {
            'nodes': neighborhood['nodes'],
            'edges': neighborhood['edges'],
            'meta': graph_data.get('meta', {}),
            'focus': focus,
            'depth': depth,
            'direction': direction,
            'truncated': neighborhood['truncated']
        }
    
    # Return full graph with meta
    return {
        'nodes': graph_data.get('nodes', []),
        'edges': graph_data.get('edges', []),
        'meta': graph_data.get('meta', {})
    }


class RepoBody(BaseModel):
    name: str


@app.get('/repos', dependencies=[Depends(auth)])
async def repos():
    return {'active': config.REPO_ROOT.name, 'repos': [repository.info(n) for n in repository.list_repos()]}


@app.post('/repos/select', dependencies=[Depends(auth)])
async def select_repo(body: RepoBody):
    # One active repository per server process. The check and the switch happen under repo_lock so no
    # request can slip in between them (asks refuse while repo_lock is held).
    async with repo_lock:
        blockers = await _sessions_blocking_switch()
        if blockers:
            raise HTTPException(status_code=409,
                detail='Cannot switch repository: ' + '; '.join(
                    '%s (%s)' % (sid[:8], why) for sid, why in blockers[:5])
                    + '. Finish, promote or reject it first.')
        try:
            g = await asyncio.to_thread(repository.activate, body.name)
        except KeyError:
            raise HTTPException(status_code=404, detail='unknown repository: ' + body.name)
    # Sessions are bound to the repository they were created for; the client must open a new one.
    return {'active': body.name, 'nodes': len(g['nodes']), 'edges': len(g['edges']),
            'session_reset_required': True}


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


@app.get('/source/{node_id:path}', dependencies=[Depends(auth)])
async def source(node_id: str, context: int = 0):
    return get_source(node_id, SimpleNamespace(state={}), min(max(context, 0), 20))


# Skill endpoints
@app.get('/skills', dependencies=[Depends(auth)])
async def list_skills():
    """List all available skills."""
    from ai_agents.registry.skill_registry import get_skill_registry
    registry = get_skill_registry()
    skills = registry.list()
    return {
        'skills': [
            {
                'id': s.id,
                'name': s.name,
                'version': s.version,
                'owner': s.owner,
                'status': s.status.value,
                'capabilities': s.capabilities,
                'supported_languages': s.supported_languages
            }
            for s in skills
        ]
    }


@app.get('/skills/{skill_id}', dependencies=[Depends(auth)])
async def get_skill(skill_id: str):
    """Get details for a specific skill."""
    from ai_agents.registry.skill_registry import get_skill_registry
    registry = get_skill_registry()
    skill = registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    
    return {
        'id': skill.id,
        'name': skill.name,
        'version': skill.version,
        'owner': skill.owner,
        'status': skill.status.value,
        'capabilities': skill.capabilities,
        'supported_languages': skill.supported_languages,
        'tools': skill.tools,
        'permissions': skill.permissions,
        'description': skill.description
    }


class SkillRunBody(BaseModel):
    skill_id: str
    args: Dict[str, Any] = {}


@app.post('/skills/{skill_id}/run', dependencies=[Depends(auth)])
async def run_skill(skill_id: str, body: SkillRunBody):
    """Run a skill (read-only skills only)."""
    from ai_agents.registry.skill_registry import get_skill_registry
    from ai_agents.callbacks import permission_guard
    
    registry = get_skill_registry()
    skill = registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    
    # Check if skill requires write or execute permissions
    write_or_execute = any(p in ['write', 'execute', 'modify'] for p in skill.permissions)
    if write_or_execute:
        raise HTTPException(status_code=403, detail="Skills with write/execute permissions cannot be run via API")
    
    # Run the skill
    result = registry.run(skill_id, body.args, {})
    
    return {
        'skill_id': skill_id,
        'status': result.status.value,
        'data': result.data,
        'evidence': result.evidence,
        'errors': result.errors,
        'unsupported': result.unsupported
    }


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
    _refuse_if_switching()
    _require_active_repo(body.repo)
    await _check_session_repo(body.session_id)
    async def gen():
        async with locks[body.session_id]:      # hold the lock for the whole stream
            session = await ensure(body.session_id)
            await set_state(body.session_id, _turn_state(body, session.state))

            reply = ''
            error = ''
            deadline = time.monotonic() + TURN_TIMEOUT
            stream = _run_turn_streaming(body).__aiter__()
            try:
                while True:
                    try:
                        ev = await asyncio.wait_for(stream.__anext__(),
                                                    timeout=max(1.0, deadline - time.monotonic()))
                    except StopAsyncIteration:
                        break
                    yield 'data: ' + json.dumps(ev) + '\n\n'
                    if ev.get('type') == 'final_response':
                        reply = ev.get('content', '')
            except asyncio.TimeoutError:
                error = 'JARVIS timed out on this request. Nothing was changed. Try again.'
                yield 'data: ' + json.dumps({'type': 'error', 'error': error}) + '\n\n'
            except Exception as exc:
                error = f'{type(exc).__name__}: {str(exc)[:200]}'
                yield 'data: ' + json.dumps({'type': 'error', 'error': error}) + '\n\n'

            # Build and send final response using the same logic as /ask
            state = (await ensure(body.session_id)).state

            # Offer commit approval only when the same evidence /approve requires is present
            await _maybe_prompt_commit(body.session_id, state, error)
            state = (await ensure(body.session_id)).state

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


def _unverified_evidence(state: dict) -> list:
    from ai_agents.tools.graph_tools import _graph
    nodes = _graph()['nodes']
    return [i for i in state.get('evidence', []) if i not in nodes]


def _build_ask_response(reply: str, error: str, state: dict) -> dict:
    """Build the standardized response for /ask and /ask/stream endpoints.

    This unified function ensures both endpoints return the same structure.
    """
    last = state.get('last_test_run') or {}
    commands = list(state.get('scene_commands', []))
    pending = _s(state.get('pending_approval'))
    approval_type = state.get('approval_type', '')
    has_patch = state.get('proposed_patch') or state.get('result_software_eng')

    # Structured evidence items for the contract: {file, first_line,
    # last_line, node_id, kind}. kind is 'confirmed' for graph nodes the
    # tools actually returned; anything else stays in unverified_evidence.
    from ai_agents.tools.graph_tools import _graph as _g
    nodes = _g()['nodes']
    evidence_items = []
    for eid in state.get('evidence', []):
        n = nodes.get(eid) or {}
        evidence_items.append({
            'node_id': str(eid),
            'file': str(n.get('file') or ''),
            'first_line': int(n.get('start') or n.get('line') or 0),
            'last_line': int(n.get('end') or n.get('line') or 0),
            'kind': 'confirmed' if n else 'unsupported',
        })

    return {
        'reply': reply,
        'error': error,
        'scene_commands': commands,
        'pending_approval': pending,
        'approval_type': approval_type,
        'approved': bool(state.get('approved', False)),
        'test_results': _s(state.get('test_results')),
        'test_source': last.get('source', '') if isinstance(last, dict) else '',
        'test_run': last if isinstance(last, dict) else {},
        'evidence': list(state.get('evidence', [])),
        'evidence_items': evidence_items,
        'unverified_evidence': _unverified_evidence(state),
        'task_id': state.get('active_task_id') or '',
        'active_task': state.get('active_task') or {},
        'proposal_status': ('pending' if pending else
                            'committed' if state.get('last_commit') else
                            'proposed' if has_patch else 'none'),
        'tool_errors': [str(e) for e in (state.get('tool_errors') or [])],
    }


async def _maybe_prompt_commit(session_id, state, error):
    """Offer the commit approval only when the recorded evidence would pass /approve. Returns the prompt
    text, or '' when nothing is offered. Same gate as /approve: no evidence, no prompt."""
    if error or _s(state.get('pending_approval')):
        return ''
    if not (state.get('proposed_patch') or state.get('result_software_eng')) or not state.get('worktree'):
        return ''
    allow_cached = os.getenv('JARVIS_ALLOW_CACHED_APPROVAL') == '1'
    why = await asyncio.to_thread(verification_blockers, state, state.get('worktree'), allow_cached)
    if why:
        return ''
    pending = 'Commit the verified patch to a sandbox branch'
    await set_state(session_id, {'pending_approval': pending, 'approved': False, 'approval_type': 'commit'})
    return pending


async def _seen_request(session_id, request_id):
    """True when this client request id was already handled for the session;
    records it otherwise. Prevents retry storms from double-patching."""
    if not request_id:
        return False
    state = (await ensure(session_id)).state
    seen = state.get('handled_request_ids') or []
    if request_id in seen:
        return True
    await set_state(session_id, {'handled_request_ids': (list(seen) + [request_id])[-200:]})
    return False


@app.post('/ask', dependencies=[Depends(auth)])
async def ask(body: AskBody):
    """Non-streaming endpoint for compatibility."""
    _refuse_if_switching()
    _require_active_repo(body.repo)
    await _check_session_repo(body.session_id)
    error = ''
    if await _seen_request(body.session_id, body.request_id):
        return {'reply': '', 'error': '', 'duplicate': True,
                'scene_commands': [], 'pending_approval': '', 'approved': False,
                'test_results': '', 'test_source': '', 'evidence': [],
                'unverified_evidence': [], 'task_id': '', 'proposal_status': 'none'}
    calls_before = llm.stats['requests']
    reply = ''
    async with locks[body.session_id]:
        session = await ensure(body.session_id)
        await set_state(body.session_id, _turn_state(body, session.state))
        try:
            reply = await asyncio.wait_for(_run_turn(body), TURN_TIMEOUT)
        except asyncio.TimeoutError:
            error = 'JARVIS timed out on this request. Nothing was changed. Try again.'
        except Exception as exc:
            error = f'{type(exc).__name__}: {str(exc)[:200]}'
        state = (await ensure(body.session_id)).state

        # Offer commit approval only when the same evidence /approve requires is present
        await _maybe_prompt_commit(body.session_id, state, error)
        state = (await ensure(body.session_id)).state

    logger = logging.getLogger('uvicorn.error')
    logger.info('ask: %d model calls, %s', llm.stats['requests'] - calls_before, 'error' if error else 'ok')
    logger.info('reply: %s', reply[:200] if reply else error)

    return _build_ask_response(reply, error, state)


@app.post('/approve', dependencies=[Depends(auth)])
async def approve(body: ApproveBody):
    _refuse_if_switching()
    _require_active_repo(body.repo)
    await _check_session_repo(body.session_id)
    if await _seen_request(body.session_id, body.request_id):
        return {'ok': True, 'duplicate': True, 'detail': 'Request already handled.'}
    async with locks[body.session_id]:
        state = (await ensure(body.session_id)).state
        pending = state.get('pending_approval', '')
        worktree = state.get('worktree', '')
        approval_type = state.get('approval_type', 'commit')
        approval_key = state.get('approval_key')
        cleared = {'pending_approval': '', 'approval_type': '', 'approval_key': ''}

        if not body.approved:
            await set_state(body.session_id, {**cleared, 'approved': False})
            return {'ok': True, 'action': 'rejected', 'detail': 'Rejected. Nothing was changed.'}

        if not pending:
            return {'ok': False, 'action': 'none', 'detail': 'Nothing was waiting for approval.'}

        if approval_type == 'tool':
            delta = {**cleared, 'approved': True}
            pending_approvals = state.get('pending_approvals', {})
            if approval_key and approval_key in pending_approvals:
                pending_approvals[approval_key]['status'] = 'approved'
                delta['pending_approvals'] = pending_approvals
            await set_state(body.session_id, delta)
            return {'ok': True, 'action': 'tool', 'detail': f'Tool action approved: {pending}'}

        if approval_type != 'commit':
            return {'ok': False, 'action': 'unknown', 'detail': f'Unknown approval type: {approval_type}'}

        # Commit path: every check runs BEFORE anything is cleared, so a refusal leaves the proposal pending.
        if not worktree:
            return {'ok': False, 'action': 'commit', 'detail': 'No sandbox worktree to commit.'}
        allow_cached = os.getenv('JARVIS_ALLOW_CACHED_APPROVAL') == '1'
        if allow_cached:
            logging.getLogger('uvicorn.error').warning(
                'approve: accepting CACHED test results (JARVIS_ALLOW_CACHED_APPROVAL=1)')
        blockers = await asyncio.to_thread(verification_blockers, state, worktree, allow_cached)
        if blockers:
            return {'ok': False, 'action': 'commit', 'detail': ' '.join(blockers), 'blockers': blockers}
        last = state.get('last_test_run') or {}
        fp = _worktree_fingerprint(worktree)
        tc = state.get('last_typecheck') or {}

        result = await asyncio.to_thread(commit_worktree, worktree, 'JARVIS: ' + str(pending)[:120])
        if result.get('ok'):
            # Structured validation record: what was verified, against which patch.
            record = {'task_id': state.get('active_task_id') or state.get('last_patch_task_id') or '',
                      'commit': result.get('commit'), 'branch': result.get('branch'),
                      'diff_hash': fp['diff_hash'],
                      'test_run': {'command': last.get('command'), 'exit_code': last.get('exit_code'),
                                   'passed': last.get('passed'), 'failed': last.get('failed'),
                                   'skipped': last.get('skipped'), 'source': last.get('source')},
                      'typecheck': tc.get('typecheck'), 'source_tc': tc.get('source'),
                      'checks_not_run': last.get('checks_not_run') or []}
            await set_state(body.session_id, {**cleared, 'approved': True,
                            'last_commit': {'branch': result['branch'], 'commit': result['commit']},
                            'validation_record': record})
            result['validation'] = record
        return {'action': 'commit', **result}


class PromoteBody(BaseModel):
    session_id: str
    repo: Optional[str] = None


@app.post('/promote', dependencies=[Depends(auth)])
async def promote(body: PromoteBody):
    _refuse_if_switching()
    _require_active_repo(body.repo)
    await _check_session_repo(body.session_id)
    async with locks[body.session_id]:
        state = (await ensure(body.session_id)).state
        last = state.get('last_commit') or {}
        if not last.get('branch'):
            return {'ok': False, 'detail': 'No committed change to promote.'}
        res = await asyncio.to_thread(promote_branch, last['branch'])
        if not res.get('ok'):
            return res
        g = await asyncio.to_thread(repository.activate, config.REPO_ROOT.name)   # re-index + clear caches
        await set_state(body.session_id, {'last_commit': {}, 'worktree': ''})
        # The promoted change belongs to the task that was in flight: mark only
        # that task done. active_task_id is set by asks sent via WORK ON IT; a
        # plain ask clears it, so unrelated running tasks are left untouched.
        plan = state.get('implementation_plan')
        if isinstance(plan, dict) and plan.get('tasks'):
            active = str(state.get('active_task_id') or state.get('last_patch_task_id') or '')
            running = [t for t in plan['tasks'] if t.get('status') == 'running']
            targets = ([t for t in running if str(t.get('id')) == active] if active
                       else running if len(running) == 1 else [])
            # Structured completion record: what was committed, verified against
            # which patch, and which design revision it implements.
            vr = state.get('validation_record') or {}
            completion = {'branch': last.get('branch'), 'commit': last.get('commit'),
                          'test_run': vr.get('test_run') or {},
                          'typecheck': vr.get('typecheck'),
                          'diff_hash': vr.get('diff_hash') or '',
                          'design_revision': (plan.get('architecture_revision')
                                              or vr.get('design_revision'))}
            targets_state = state.get('task_targets') or {}
            for t in targets:
                t['status'] = 'done'
                t['evidence'] = 'promoted branch %s (%s)' % (
                    last.get('branch'), (last.get('commit') or '')[:10])
                t['completion'] = completion
                # Files the coding agent confirmed/rejected become the task record.
                if targets_state.get('confirmed_targets'):
                    t['confirmed_targets'] = targets_state['confirmed_targets']
                if targets_state.get('rejected_targets'):
                    t['rejected_targets'] = targets_state['rejected_targets']
            if targets:
                await set_state(body.session_id, {'implementation_plan': plan,
                                                  'active_task_id': '',
                                                  'task_targets': {},
                                                  'validation_record': {}})
                await _persist_design(body.session_id)
        return {**res, 'graph_refreshed': True, 'nodes': len(g['nodes']), 'edges': len(g['edges'])}


@app.get('/task/{session_id}', dependencies=[Depends(auth)])
async def get_task_state(session_id: str):
    """Get current task state for a session in Unity-compatible format."""
    session = await ensure(session_id)
    state = session.state

    # Flatten results into a list for Unity
    agent_results = []
    for key in ['result_repository', 'result_code_understanding', 'result_relationship',
                'result_data_flow', 'result_software_eng', 'result_testing',
                'result_visualization', 'result_orchestrator', 'result_conversational']:
        value = state.get(key, {})
        if value and isinstance(value, dict):
            agent_name = key.replace('result_', '')
            agent_results.append({
                'agent': agent_name,
                'summary': value.get('summary', ''),
                'confidence': value.get('confidence', 0),
                'status': value.get('status', 'unknown')
            })

    # Extract plan summary and task list (implementation plans from /plan/generate win over ad-hoc plans)
    plan = state.get('implementation_plan') or state.get('plan') or {}
    plan_summary = plan.get('summary', '') if isinstance(plan, dict) else str(plan)
    raw_tasks = plan.get('tasks', []) if isinstance(plan, dict) else (plan if isinstance(plan, list) else [])
    tasks = []
    for i, t in enumerate(raw_tasks if isinstance(raw_tasks, list) else []):
        if isinstance(t, dict):
            # Keep every field the plan stored (description, suggested_files,
            # confirmed_targets, rejected_targets, new_files, modifies_existing,
            # needs_investigation, design_revision, cycle_*, completion, ...) and
            # normalise the ones Unity reads by type.
            rec = dict(t)
            rec.update({'id': str(t.get('id', i)),
                        'title': t.get('title') or t.get('summary', ''),
                        'status': t.get('status', 'pending'),
                        'depends_on': [str(d) for d in (t.get('depends_on') or [])],
                        'component_id': str(t.get('component_id') or ''),
                        'acceptance': str(t.get('acceptance') or ''),
                        'acceptance_criteria': [str(c) for c in (t.get('acceptance_criteria') or [])],
                        'files': [str(f) for f in (t.get('files') or [])],
                        'symbols': t.get('symbols') or [],
                        'repo_match': str(t.get('repo_match') or ''),
                        'owner': str(t.get('owner') or ''),
                        'evidence': str(t.get('evidence') or ''),
                        'evidence_check': t.get('evidence_check')})
            tasks.append(rec)
        elif isinstance(t, str):
            tasks.append({'id': str(i), 'title': t, 'status': 'pending',
                          'depends_on': [], 'component_id': '', 'acceptance': '', 'owner': ''})

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
        'tasks': tasks,
        'circular': [str(c) for c in (plan.get('circular') or [])] if isinstance(plan, dict) else [],
        'agent_results': agent_results,
        'findings': findings
    }


# ---------------------------------------------------------------------------
# Architecture design workflow: idea -> requirements -> proposed architecture
# -> repository comparison -> approved plan. Model output proposes; only an
# explicit human call approves. Editing an approved architecture reverts it
# to draft and invalidates any plan generated from it.

from ai_agents.tools.architecture_tools import (
    extract_requirements, propose_architecture, compare_to_repository,
    generate_implementation_plan, verify_task_evidence,
    _blank_architecture, save_design, load_design,
)

DESIGN_KEYS = ('design_requirements', 'design', 'design_compare', 'implementation_plan')

# Allowed values for architecture kinds; anything else is rejected.
COMPONENT_KINDS = {'service', 'library', 'ui', 'data', 'external'}
RELATIONSHIP_KINDS = {'calls', 'reads', 'publishes'}


def _valid_design_id(value):
    """Component/relationship ids must be short, printable tokens."""
    v = (value or '').strip()
    return bool(v) and len(v) <= 64 and all(ch.isalnum() or ch in '_.-' for ch in v)


def _disk_payload(session_id):
    d = load_design(session_id)
    return {
        'requirements': d.get('requirements'),
        'architecture': d.get('architecture'),
        'compare': d.get('compare'),
        'plan': d.get('plan'),
    }


async def _design_view(session_id):
    """Merge live session state with the on-disk copy.

    A key present in session state wins even when its value is empty
    ({} / []): the endpoints use empty values to *invalidate* a plan,
    comparison or proposal, and falling back to disk in that case would
    resurrect stale data that was deliberately cleared.
    """
    state = (await ensure(session_id)).state
    disk = _disk_payload(session_id)
    view = {}
    for state_key, disk_key in (('design_requirements', 'requirements'),
                                ('design', 'architecture'),
                                ('design_compare', 'compare'),
                                ('implementation_plan', 'plan')):
        view[disk_key] = state[state_key] if state_key in state else disk[disk_key]
    # A comparison is only valid for the revision it was computed against.
    # Edits already clear it; this marks any survivor explicitly stale.
    cmp_ = view.get('compare')
    arch = view.get('architecture')
    if isinstance(cmp_, dict) and cmp_ and isinstance(arch, dict):
        rev = cmp_.get('design_revision')
        if rev is not None and rev != arch.get('revision'):
            cmp_ = dict(cmp_)
            cmp_['stale'] = True
            view['compare'] = cmp_
    return view


_PERSIST_WARNINGS = []   # recent design-persistence failures, surfaced via /health


async def _persist_design(session_id):
    view = await _design_view(session_id)
    ok = save_design(session_id, {
        'requirements': view['requirements'],
        'architecture': view['architecture'],
        'compare': view['compare'],
        'plan': view['plan'],
    })
    if not ok:
        import datetime
        _PERSIST_WARNINGS.append({'session_id': session_id,
                                  'at': datetime.datetime.utcnow().isoformat()})
        del _PERSIST_WARNINGS[:-20]


class DesignIdeaBody(BaseModel):
    session_id: str
    idea_text: str = ''


class DesignProposeBody(BaseModel):
    session_id: str
    idea_text: str = ''


class DesignEditOp(BaseModel):
    op: str
    id: str = ''
    src: str = ''
    dst: str = ''
    kind: str = ''
    label: str = ''
    name: str = ''
    responsibility: str = ''
    component_kind: str = ''
    requirement_ids: list = []
    question: str = ''        # open-question text (resolve/update/add ops)
    new_question: str = ''    # replacement text for update_question
    answer: str = ''          # developer's resolution/rationale for resolve_question
    cycle_rationale: str = '' # required reason when accepting a dependency cycle


class DesignEditBody(BaseModel):
    session_id: str
    ops: List[DesignEditOp] = []


class DesignApproveBody(BaseModel):
    session_id: str
    approved: bool = True
    approved_by: str = 'user'


class PlanGenerateBody(BaseModel):
    session_id: str


class PlanTaskPatch(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    evidence: Optional[str] = None      # required to mark a task done
    accept_cycles: bool = False         # explicit acceptance of circular deps
    cycle_rationale: str = ''           # required reason for accepting a cycle
    request_id: Optional[str] = None    # client-generated id; retries are ignored


def _next_id(prefix, items, key='id'):
    used = {str(x.get(key)) for x in items}
    i = 1
    while '%s%d' % (prefix, i) in used:
        i += 1
    return '%s%d' % (prefix, i)


def _question_matches(questions, text):
    """Indexes of open questions matching `text`: exact, then case-insensitive,
    then substring. Empty text matches nothing."""
    if not text:
        return []
    exact = [i for i, q in enumerate(questions) if q == text]
    if exact:
        return exact
    low = text.lower()
    ci = [i for i, q in enumerate(questions) if q.lower() == low]
    if ci:
        return ci
    return [i for i, q in enumerate(questions) if low in q.lower()]


def _apply_design_op(arch, op):
    """Apply one edit op to a deep copy of the architecture. Returns (arch, error)."""
    import copy
    arch = copy.deepcopy(arch)
    comps = arch.setdefault('components', [])
    rels = arch.setdefault('relationships', [])
    comp_ids = {c.get('id') for c in comps}
    op_type = (op.op or '').strip()

    if op_type == 'add_component':
        if not op.name.strip():
            return arch, 'add_component requires a name'
        cid = op.id.strip() or _next_id('c', comps)
        if not _valid_design_id(cid):
            return arch, 'invalid component id: ' + cid
        if cid in comp_ids:
            return arch, 'component id already exists: ' + cid
        kind = op.component_kind or 'service'
        if kind not in COMPONENT_KINDS:
            return arch, 'invalid component kind: ' + kind
        comps.append({'id': cid, 'name': op.name.strip(),
                      'responsibility': op.responsibility,
                      'kind': kind,
                      'requirement_ids': [str(x) for x in op.requirement_ids]})
    elif op_type == 'remove_component':
        if op.id not in comp_ids:
            return arch, 'unknown component: ' + op.id
        dangling = [r for r in rels if r.get('src') == op.id or r.get('dst') == op.id]
        if dangling:
            return arch, 'component %s has %d relationship(s); remove them first' % (op.id, len(dangling))
        arch['components'] = [c for c in comps if c.get('id') != op.id]
    elif op_type == 'update_component':
        comp = next((c for c in comps if c.get('id') == op.id), None)
        if comp is None:
            return arch, 'unknown component: ' + op.id
        for field, val in (('name', op.name), ('responsibility', op.responsibility), ('kind', op.component_kind)):
            if val:
                if field == 'kind' and val not in COMPONENT_KINDS:
                    return arch, 'invalid component kind: ' + val
                comp[field] = val
        if op.requirement_ids:
            comp['requirement_ids'] = [str(x) for x in op.requirement_ids]
    elif op_type == 'add_relationship':
        if op.src not in comp_ids or op.dst not in comp_ids:
            return arch, 'relationship endpoints must be existing component ids'
        if op.src == op.dst:
            return arch, 'a component cannot relate to itself'
        rid = op.id.strip() or _next_id('e', rels)
        if not _valid_design_id(rid):
            return arch, 'invalid relationship id: ' + rid
        if any(r.get('id') == rid for r in rels):
            return arch, 'relationship id already exists: ' + rid
        kind = op.kind or 'calls'
        if kind not in RELATIONSHIP_KINDS:
            return arch, 'invalid relationship kind: ' + kind
        rels.append({'id': rid, 'src': op.src, 'dst': op.dst,
                     'kind': kind, 'label': op.label})
    elif op_type == 'remove_relationship':
        before = len(rels)
        arch['relationships'] = [r for r in rels
                                 if r.get('id') != op.id
                                 and not (op.src and op.dst and r.get('src') == op.src and r.get('dst') == op.dst)]
        if len(arch['relationships']) == before:
            return arch, 'relationship not found'
    elif op_type == 'update_relationship':
        rel = next((r for r in rels if r.get('id') == op.id), None)
        if rel is None:
            return arch, 'unknown relationship: ' + op.id
        for field, val in (('kind', op.kind), ('label', op.label), ('src', op.src), ('dst', op.dst)):
            if val:
                if field == 'kind' and val not in RELATIONSHIP_KINDS:
                    return arch, 'invalid relationship kind: ' + val
                rel[field] = val
        comp_ids = {c.get('id') for c in arch['components']}
        if rel.get('src') not in comp_ids or rel.get('dst') not in comp_ids:
            return arch, 'relationship would dangle: unknown component id'
    elif op_type == 'resolve_question':
        questions = arch.setdefault('open_questions', [])
        idx = _question_matches(questions, op.question)
        if not idx:
            return arch, 'open question not found: ' + (op.question or '<empty>')
        answer = (op.answer or '').strip()
        if not answer:
            return arch, ('resolve_question requires a non-empty answer. '
                          'Pass the developer\'s resolution in "answer", or use '
                          'op "defer_question" with a reason to postpone it.')
        resolved = arch.setdefault('resolved_questions', [])
        for i in sorted(idx, reverse=True):
            # Keep the decision on record: the question, the developer's
            # answer/rationale and the revision it resolved at.
            resolved.append({'question': questions[i], 'answer': answer,
                             'revision': int(arch.get('revision') or 0) + 1})
            questions.pop(i)
    elif op_type == 'defer_question':
        # Explicit decision to postpone a question: it leaves the approval
        # gate but stays on record with the reason it was deferred.
        questions = arch.setdefault('open_questions', [])
        idx = _question_matches(questions, op.question)
        if not idx:
            return arch, 'open question not found: ' + (op.question or '<empty>')
        reason = (op.answer or op.label or '').strip()
        if not reason:
            return arch, 'defer_question requires a reason in "answer"'
        deferred = arch.setdefault('deferred_questions', [])
        for i in sorted(idx, reverse=True):
            deferred.append({'question': questions[i], 'reason': reason,
                             'revision': int(arch.get('revision') or 0) + 1})
            questions.pop(i)
    elif op_type == 'reopen_question':
        # Move a deferred or resolved question back to open_questions so it
        # blocks approval again.
        questions = arch.setdefault('open_questions', [])
        for key in ('deferred_questions', 'resolved_questions'):
            entries = arch.get(key) or []
            hit = next((e for e in entries
                        if _question_matches([e.get('question', '')], op.question)), None)
            if hit is not None:
                entries.remove(hit)
                text = hit.get('question', '')
                if text and text not in questions:
                    questions.append(text)
                return arch, None
        return arch, 'no deferred or resolved question matches: ' + (op.question or '<empty>')
    elif op_type == 'update_question':
        questions = arch.setdefault('open_questions', [])
        idx = _question_matches(questions, op.question)
        if not idx:
            return arch, 'open question not found: ' + (op.question or '<empty>')
        if not op.new_question.strip():
            return arch, 'update_question requires new_question text'
        questions[idx[0]] = op.new_question.strip()
    elif op_type == 'add_question':
        text = (op.question or op.new_question).strip()
        if not text:
            return arch, 'add_question requires question text'
        questions = arch.setdefault('open_questions', [])
        if text not in questions:
            questions.append(text)
    else:
        return arch, 'unknown op: ' + op_type

    # Final validation: no dangling relationships may survive any op sequence.
    comp_ids = {c.get('id') for c in arch.get('components', [])}
    for r in arch.get('relationships', []):
        if r.get('src') not in comp_ids or r.get('dst') not in comp_ids:
            return arch, 'dangling relationship: %s -> %s' % (r.get('src'), r.get('dst'))
    return arch, None


@app.post('/design/requirements', dependencies=[Depends(auth)])
async def design_requirements(body: DesignIdeaBody):
    await _check_session_repo(body.session_id)
    res = await asyncio.to_thread(extract_requirements, body.idea_text)
    await set_state(body.session_id, {'design_requirements': res['requirements']})
    await _persist_design(body.session_id)
    # Never present a heuristic fallback as a clean AI result.
    if res.get('source') == 'heuristic':
        res = dict(res)
        res['warning'] = ('Requirements were produced by the heuristic '
                          'fallback, not the AI model.')
    return res


@app.post('/design/propose', dependencies=[Depends(auth)])
async def design_propose(body: DesignProposeBody):
    await _check_session_repo(body.session_id)
    req = None
    req_source = 'unknown'
    if body.idea_text.strip():
        res = await asyncio.to_thread(extract_requirements, body.idea_text)
        req = res['requirements']
        req_source = res.get('source') or 'unknown'
    else:
        view = await _design_view(body.session_id)
        req = view['requirements']
        req_source = ((view.get('architecture') or {}).get('requirements_source')
                      or 'stored')
    if not req or not any(req.get(k) for k in ('goals', 'functional')):
        raise HTTPException(status_code=400, detail='No requirements: pass idea_text or call /design/requirements first.')

    prop = await asyncio.to_thread(propose_architecture, req)
    arch = _blank_architecture()
    arch['components'] = prop['components']
    arch['relationships'] = prop['relationships']
    arch['open_questions'] = list(req.get('open_questions') or [])
    # 'model' = generated by the LLM, 'heuristic' = template fallback,
    # 'unknown' = caller did not report a source. The UI must label these
    # differently — a fallback proposal is not an AI design.
    arch['provenance'] = prop.get('source') or 'unknown'
    arch['requirements_source'] = req_source
    arch['revision'] = 1
    # A new proposal invalidates any previous comparison and plan.
    await set_state(body.session_id, {'design_requirements': req, 'design': arch,
                                      'design_compare': {}, 'implementation_plan': {}})
    await _persist_design(body.session_id)
    out = {'status': 'ok', 'provenance': arch['provenance'],
           'requirements_source': req_source,
           'requirements': req, 'architecture': arch}
    if 'heuristic' in (arch['provenance'], req_source):
        out['warning'] = ('Part of this proposal came from the heuristic fallback, '
                          'not the AI model. Review it before relying on it.')
    return out


@app.get('/design/{session_id}', dependencies=[Depends(auth)])
async def design_get(session_id: str):
    return await _design_view(session_id)


@app.post('/design/{session_id}/edit', dependencies=[Depends(auth)])
async def design_edit(session_id: str, body: DesignEditBody):
    await _check_session_repo(session_id)
    view = await _design_view(session_id)
    arch = view['architecture']
    if not arch:
        raise HTTPException(status_code=404, detail='No architecture proposal for this session.')
    import copy
    working = copy.deepcopy(arch)
    question_ops = {'resolve_question', 'update_question', 'add_question',
                    'defer_question', 'reopen_question'}
    touched_questions = False
    for op in body.ops:
        working, err = _apply_design_op(working, op)
        if err:
            raise HTTPException(status_code=400, detail=err)
        touched_questions = touched_questions or (op.op or '').strip() in question_ops
    working['revision'] = int(arch.get('revision') or 1) + 1
    # Provenance survives edits: a hand-edited model design is still 'model';
    # a heuristic fallback stays 'heuristic' even after edits. The flag lets
    # the UI say "edited by you" without lying about the origin.
    working['edited_by_user'] = True
    if working.get('status') == 'approved':
        # Editing an approved architecture reverts it to draft and invalidates its plan.
        working['status'] = 'draft'
        working['approved_by'] = ''
        working['approved_version'] = 0
        working['approved_revision'] = 0
    # Editing the design invalidates the implementation plan AND any
    # repository comparison computed against the previous revision.
    delta = {'design': working, 'implementation_plan': {}, 'design_compare': {}}
    if touched_questions and isinstance(view.get('requirements'), dict):
        # Keep the requirements document in step: its open_questions mirror the architecture's.
        req = copy.deepcopy(view['requirements'])
        req['open_questions'] = list(working.get('open_questions') or [])
        delta['design_requirements'] = req
    await set_state(session_id, delta)
    await _persist_design(session_id)
    return {'ok': True, 'architecture': working}


def _graph_path_for_repo(name: Optional[str]):
    """Index path for repository `name`, building the index if needed.

    Lets design endpoints work on a repository other than the globally active
    one without mutating config.REPO_ROOT/GRAPH_PATH for every session."""
    if not name:
        return None
    if name not in repository.list_repos():
        raise HTTPException(status_code=404, detail='unknown repository: ' + name)
    path = config.INDEX_DIR / (name + '.json')
    if not path.is_file():
        try:
            path, _graph = repository.build_graph(name)
        except Exception as exc:
            raise HTTPException(status_code=500,
                                detail='could not index repository: ' + str(exc)[:200])
    return path


@app.post('/design/{session_id}/compare', dependencies=[Depends(auth)])
async def design_compare(session_id: str, repo: Optional[str] = None,
                         override_matches: Optional[Dict[str, str]] = None):
    await _check_session_repo(session_id)
    view = await _design_view(session_id)
    arch = view['architecture']
    if not arch:
        raise HTTPException(status_code=404, detail='No architecture proposal for this session.')
    gpath = _graph_path_for_repo(repo)
    res = await asyncio.to_thread(compare_to_repository,
                                  {'architecture': arch}, None,
                                  str(gpath) if gpath else None,
                                  repo=repo or config.REPO_ROOT.name,
                                  override_matches=override_matches)
    # Record which repository and revision the comparison ran against so
    # staleness is explicit and plan generation grounds tasks in the same graph.
    res['repo'] = repo or config.REPO_ROOT.name
    res['design_revision'] = arch.get('revision')
    await set_state(session_id, {'design_compare': res})
    await _persist_design(session_id)
    return res


@app.post('/design/{session_id}/approve', dependencies=[Depends(auth)])
async def design_approve(session_id: str, body: DesignApproveBody):
    await _check_session_repo(session_id)
    view = await _design_view(session_id)
    arch = view['architecture']
    if not arch:
        raise HTTPException(status_code=404, detail='No architecture proposal for this session.')
    if body.approved:
        open_q = arch.get('open_questions') or []
        comp_ids = {c.get('id') for c in arch.get('components', [])}
        dangling = [r for r in arch.get('relationships', [])
                    if r.get('src') not in comp_ids or r.get('dst') not in comp_ids]
        if open_q or dangling:
            raise HTTPException(status_code=409, detail='Cannot approve: unresolved open questions or dangling relationships.')
        arch['status'] = 'approved'
        arch['approved_by'] = body.approved_by
        arch['approved_version'] = arch.get('version')
        # The editing revision is what actually identifies the approved design;
        # 'version' is only the schema version and never changes per edit.
        arch['approved_revision'] = arch.get('revision')
    else:
        arch['status'] = 'draft'
        arch['approved_by'] = ''
        arch['approved_version'] = 0
        arch['approved_revision'] = 0
    await set_state(session_id, {'design': arch})
    await _persist_design(session_id)
    return {'ok': True, 'architecture': arch}


@app.post('/plan/generate', dependencies=[Depends(auth)])
async def plan_generate(body: PlanGenerateBody):
    await _check_session_repo(body.session_id)
    view = await _design_view(body.session_id)
    arch = view['architecture']
    if not arch:
        raise HTTPException(status_code=404, detail='No architecture proposal for this session.')
    if arch.get('status') != 'approved':
        raise HTTPException(status_code=409, detail='Architecture must be approved before generating a plan.')
    # Ground tasks in the same repository the comparison ran against.
    repo_name = (view.get('compare') or {}).get('repo')
    gpath = _graph_path_for_repo(repo_name)
    res = await asyncio.to_thread(generate_implementation_plan,
                                  {'architecture': arch}, None,
                                  str(gpath) if gpath else None)
    plan = {'architecture_version': arch.get('version'),
            'architecture_revision': arch.get('revision'),
            'repo': repo_name or config.REPO_ROOT.name,
            'status': 'active',
            'tasks': res['tasks'], 'circular': res.get('circular') or [],
            'cycle_paths': res.get('cycle_paths') or []}
    await set_state(body.session_id, {'implementation_plan': plan})
    await _persist_design(body.session_id)
    return plan


@app.patch('/plan/{session_id}/tasks/{task_id}', dependencies=[Depends(auth)])
async def plan_update_task(session_id: str, task_id: str, body: PlanTaskPatch):
    await _check_session_repo(session_id)
    view = await _design_view(session_id)
    plan = view['plan']
    arch = view['architecture']
    if not plan or not plan.get('tasks'):
        raise HTTPException(status_code=404, detail='No implementation plan for this session.')
    # Defensive: a plan only drives the architecture revision it was generated
    # from, and only while that revision is the approved one.
    if arch and (arch.get('status') != 'approved'
                 or plan.get('architecture_revision') != arch.get('approved_revision')):
        raise HTTPException(status_code=409,
                            detail='Plan is stale: the approved architecture revision changed. Regenerate the plan.')
    if body.request_id:
        seen = (await ensure(session_id)).state.get('handled_request_ids') or []
        if body.request_id in seen:
            return {'ok': True, 'duplicate': True, 'detail': 'Request already handled.'}
        await set_state(session_id, {'handled_request_ids': (seen + [body.request_id])[-200:]})
    task = next((t for t in plan['tasks'] if str(t.get('id')) == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail='Task not found: ' + task_id)
    if body.title is not None:
        task['title'] = body.title
    if body.status is not None:
        raw = body.status.strip().lower()
        if raw in ('running', 'in_progress', 'in-progress'):
            new_status = 'running'
        elif raw in ('done', 'completed'):
            new_status = 'done'
        elif raw == 'pending':
            new_status = 'pending'
        else:
            raise HTTPException(status_code=400, detail='Invalid task status: ' + body.status)
        current = task.get('status') or 'pending'
        current = {'completed': 'done', 'in_progress': 'running', 'in-progress': 'running'}.get(current, current)
        # Valid transitions: pending -> running|done, running -> done|pending,
        # done -> pending (reopen for corrections). Same-status is a no-op.
        allowed = {'pending': {'pending', 'running', 'done'},
                   'running': {'running', 'done', 'pending'},
                   'done': {'done', 'pending'}}
        if new_status not in allowed.get(current, {current}):
            raise HTTPException(status_code=409,
                                detail='Cannot move task from %s to %s.' % (current, new_status))
        if new_status in ('running', 'done') and new_status != current:
            done_ids = {str(t.get('id')) for t in plan['tasks']
                        if (t.get('status') or 'pending') in ('done', 'completed')}
            missing = [str(d) for d in (task.get('depends_on') or []) if str(d) not in done_ids]
            if missing:
                raise HTTPException(status_code=409,
                                    detail='Task is blocked by unfinished dependencies: ' + ', '.join(missing))
            # Tasks inside a dependency cycle cannot be scheduled until the
            # developer either fixes the architecture or explicitly accepts
            # the cycle for this task.
            cyclic_ids = set()
            for path in (plan.get('cycle_paths') or []):
                cyclic_ids.update(str(x) for x in path)
            if str(task.get('component_id') or '') in cyclic_ids and not task.get('cycle_accepted'):
                if not body.accept_cycles:
                    raise HTTPException(
                        status_code=409,
                        detail='Task %s is part of a circular dependency (%s). '
                               'Resolve the cycle in the architecture or resubmit '
                               'with accept_cycles=true and a cycle_rationale.'
                               % (task_id, task.get('component_id')))
                rationale = (body.cycle_rationale or '').strip()
                if not rationale:
                    raise HTTPException(
                        status_code=400,
                        detail='Accepting a circular dependency requires a '
                               'cycle_rationale explaining why it is safe.')
                task['cycle_accepted'] = True
                task['cycle_rationale'] = rationale
        if new_status == 'done' and current != 'done':
            # Manual DONE is not proof of work: require the developer to
            # record what demonstrates the task is complete (tests run,
            # commit hash, review sign-off, ...).
            ev = (body.evidence or '').strip()
            if not ev:
                raise HTTPException(
                    status_code=400,
                    detail='Marking a task done requires evidence '
                           '(e.g. tests run, commit hash). Pass it in the '
                           '"evidence" field.')
            # Independently verify whatever the evidence claims: commit SHAs,
            # branches, pytest node ids and graph node ids are checked against
            # the repository. A claim that contradicts the repo rejects the
            # completion; unverifiable prose is allowed but recorded.
            # Evidence is checked against the plan's repository and graph,
            # not whichever repo happens to be globally active.
            plan_repo = plan.get('repo') or config.REPO_ROOT.name
            repo_root = config.REPOSITORY_DIR / plan_repo
            graph_path = config.INDEX_DIR / (plan_repo + '.json')
            check = await asyncio.to_thread(verify_task_evidence, ev,
                                            repo_root if repo_root.is_dir() else None,
                                            str(graph_path) if graph_path.is_file() else None)
            if check.get('verdict') == 'failed':
                bad = '; '.join('%s: %s' % (c['claim'], c['detail'])
                                for c in check['checks'] if c['status'] == 'failed')
                raise HTTPException(
                    status_code=409,
                    detail='Evidence contradicts the repository: ' + bad)
            task['evidence'] = ev
            task['evidence_check'] = check
        task['status'] = new_status
    await set_state(session_id, {'implementation_plan': plan})
    await _persist_design(session_id)
    return {'ok': True, 'task': task, 'plan': plan}


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

