import asyncio
import base64
import binascii
import hashlib
import logging
import json
import os
import re
import subprocess
import sys
import traceback
import uuid
import hmac
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional, Dict, Any, List, Literal

from types import SimpleNamespace

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

sys.path.insert(0, str(Path(__file__).parent))
from api_models import *  # noqa: F401,F403  (response models)

from ai_agents.agent import root_agent
from ai_agents import config, repository
from ai_agents.config import USE_CACHED_TESTS
from ai_agents import llm
from ai_agents.tools.git_tools import (
    commit_worktree, create_worktree, promote_branch)
from ai_agents.tools.exec_tools import (
    _clear_verification, _review_verdict, _worktree_fingerprint,
    verification_blockers, review_blockers, run_tests, run_typecheck)
from ai_agents.tools.security_tools import run_security_scan
from ai_agents.tools.path_resolver import (
    PathResolutionError, resolve_worktree_read, resolve_worktree_write)
from ai_agents.tools.workspace_tools import (
    apply_line_edit, quick_syntax_check, worktree_symbols)
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

# Explicit session backend: 'sqlite' (durable, default) or 'memory' (volatile,
# for tests/dev). An unknown value fails startup instead of silently falling
# back to whichever service happened to import.
SESSION_BACKEND = os.getenv('JARVIS_SESSION_BACKEND', 'sqlite').lower()
if SESSION_BACKEND not in ('sqlite', 'memory'):
    raise RuntimeError('JARVIS_SESSION_BACKEND must be sqlite or memory')

if SESSION_BACKEND == 'sqlite':
    from google.adk.sessions import DatabaseSessionService   # ImportError fails startup
    (config.ROOT / 'data').mkdir(parents=True, exist_ok=True)
    sessions = DatabaseSessionService(
        db_url=os.getenv('JARVIS_SESSION_DB',
                         'sqlite+aiosqlite:///' + str(config.ROOT / 'data' / 'sessions.db')))
else:
    sessions = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP, session_service=sessions)
locks = defaultdict(asyncio.Lock)
session_last_used = {}  # Track session last activity for eviction
app = FastAPI(title='JARVIS bridge')


def _rid(request):
    return request.headers.get('x-request-id') or uuid.uuid4().hex


_CODES = {400: 'BAD_REQUEST', 401: 'UNAUTHORIZED', 403: 'FORBIDDEN',
          404: 'NOT_FOUND', 409: 'CONFLICT', 422: 'VALIDATION_ERROR',
          429: 'CAPACITY_EXCEEDED', 503: 'UNAVAILABLE'}


@app.exception_handler(StarletteHTTPException)
async def _http_exc(request, exc):
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(status_code=exc.status_code, content={
        'status': 'error',
        'error': {'code': _CODES.get(exc.status_code, 'ERROR'),
                  'message': detail, 'details': {}},
        'request_id': _rid(request),
        # Unity still reads the legacy 'detail' field on errors.
        'detail': detail})


@app.exception_handler(RequestValidationError)
async def _val_exc(request, exc):
    return JSONResponse(status_code=422, content={
        'status': 'error',
        'error': {'code': 'VALIDATION_ERROR', 'message': 'Invalid request.',
                  'details': {'errors': jsonable_encoder(exc.errors())}},
        'request_id': _rid(request)})


@app.exception_handler(Exception)
async def _unhandled(request, exc):
    rid = _rid(request)
    logging.getLogger('uvicorn.error').error(
        'unhandled %s: %s', rid, traceback.format_exc())
    return JSONResponse(status_code=500, content={
        'status': 'error',
        'error': {'code': 'INTERNAL_ERROR',
                  'message': 'Unexpected server error.', 'details': {}},
        'request_id': rid})

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


_session_create_lock = asyncio.Lock()

# Lease-based session management: sessions carry a '_lease' record in
# their state (holder + expiry) so eviction and repo-switch guards only
# touch sessions whose lease is live. Works on both the sqlite and the
# in-memory backend because the record lives in session state.
from ai_agents.intelligence.session_leases import SessionLeaseManager
_session_leases = SessionLeaseManager()


async def _session_lease_state(sid):
    """(has_live_lease, lease_dict) for eviction decisions."""
    sess = await sessions.get_session(app_name=APP, user_id=USER,
                                      session_id=sid)
    if sess is None:
        return False, None
    lease = (sess.state or {}).get('_lease')
    if not isinstance(lease, dict):
        return False, None
    live = float(lease.get('expires_at', 0)) > time.time()
    return live, lease


async def _session_is_safe_to_evict(sid) -> bool:
    """A session may only be evicted when its lease is live-or-absent,
    it is past the idle timeout, and nothing in its real state would be
    lost: no running turn (lock held), no worktree on disk, no pending
    approval, no unpromoted commit, no in-flight design/plan work."""
    if locks[sid].locked():
        return False
    sess = await sessions.get_session(app_name=APP, user_id=USER, session_id=sid)
    if sess is None:
        return True
    st = sess.state
    wt = st.get('worktree')
    if wt and Path(str(wt)).is_dir():
        return False
    if st.get('pending_approval'):
        return False
    lc = st.get('last_commit')
    if isinstance(lc, dict) and lc.get('branch'):
        return False
    if st.get('design_in_progress') or st.get('plan_in_progress'):
        return False
    return True


async def _evict_one_safe_session() -> bool:
    """Evict the oldest session that is past the idle timeout AND safe to
    drop. Returns False when every expired session is still in use."""
    now = time.time()
    expired = sorted(
        (t, s) for s, t in session_last_used.items()
        if now - t >= SESSION_IDLE_TIMEOUT)
    for _, sid in expired:
        if await _session_is_safe_to_evict(sid):
            await sessions.delete_session(app_name=APP, user_id=USER, session_id=sid)
            session_last_used.pop(sid, None)
            locks.pop(sid, None)
            return True
    return False


async def ensure(session_id):
    session = await sessions.get_session(app_name=APP, user_id=USER, session_id=session_id)
    if session is None:
        async with _session_create_lock:
            session = await sessions.get_session(
                app_name=APP, user_id=USER, session_id=session_id)
            if session is None:
                if len(session_last_used) >= MAX_SESSIONS:
                    if not await _evict_one_safe_session():
                        raise HTTPException(
                            status_code=429,
                            detail='Session capacity reached and no idle session can be safely removed.')
                session = await sessions.create_session(
                    app_name=APP, user_id=USER, session_id=session_id)
    session_last_used[session_id] = time.time()
    # Renew the session lease on every access; a live lease held by a
    # different holder is reported but not stolen.
    try:
        await _session_leases.acquire_async(sessions, session)
    except Exception:
        pass  # lease bookkeeping must never break session access
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
    # Fail-closed tool contracts: a bad schema or a missing core schema must
    # stop the server at boot, not mid-run.
    from ai_agents.registry.tool_registry import get_tool_registry
    get_tool_registry()
    # Fail-closed agent/tool contracts: a tool missing from a toolset, a bad
    # instruction reference or a missing schema stops the server at boot.
    from ai_agents.agents.validate_toolsets import validate_runtime_agent_contracts
    validate_runtime_agent_contracts()
    # Connectivity probe: prove the session backend can create and delete a
    # session before serving traffic.
    probe = '__startup_probe__'
    await sessions.create_session(app_name=APP, user_id=USER, session_id=probe)
    await sessions.delete_session(app_name=APP, user_id=USER, session_id=probe)

    # Periodically reclaim finished runtime traces and their snapshots.
    async def _trace_gc():
        from ai_agents.runtime import trace_manager as _tm
        while True:
            await asyncio.sleep(300)
            try:
                _tm.cleanup_expired()
            except Exception:
                pass
    asyncio.get_event_loop().create_task(_trace_gc())
    try:
        resp = await sessions.list_sessions(app_name=APP, user_id=USER)
        persisted = list(getattr(resp, 'sessions', None) or [])
        for sess in persisted:
            # Stamp with the session's real last activity, not restart time,
            # so the idle-timeout eviction still applies after a restart.
            session_last_used.setdefault(
                sess.id, float(getattr(sess, 'last_update_time', 0) or 0))
        # Lease migration: pre-lease persisted sessions get an initial
        # lease record so they are never treated as unowned/abandoned.
        from ai_agents.intelligence.session_leases import (
            migrate_legacy_sessions)
        migrated = await migrate_legacy_sessions(
            sessions, APP, USER,
            list_sessions=lambda app_name, user_id: sessions.list_sessions(
                app_name=app_name, user_id=user_id))
        if migrated:
            logging.getLogger('uvicorn.error').info(
                'migrated %d session(s) to lease records', migrated)
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


@app.post('/session', dependencies=[Depends(auth)], response_model=SessionResponse)
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
    to the wrong codebase. Also refuses while a repository switch is in progress."""
    _refuse_if_switching()
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


@app.get('/health', response_model=HealthResponse)  # No authentication - public endpoint
async def health():
    """Public health check endpoint - no authentication required."""
    changed = len([line for line in _git('status', '--porcelain').splitlines() if line.strip()])
    return {'ok': True, 'cached_tests': USE_CACHED_TESTS, 'repo': config.REPO_ROOT.name,
            'branch': _git('rev-parse', '--abbrev-ref', 'HEAD') or '?', 'changed': changed,
            'session_backend': SESSION_BACKEND,
            'persistence_mode': 'durable' if SESSION_BACKEND == 'sqlite' else 'volatile',
            'semantic_languages': ['python', 'javascript', 'typescript'],
            'analysis_support': {
                'python': {'structure': True, 'calls': True, 'cfg': True, 'dfg': True},
                'typescript': {'structure': True, 'calls': True, 'cfg': False, 'dfg': False},
                'javascript': {'structure': True, 'calls': True, 'cfg': False, 'dfg': False},
                'other': {'structure': True, 'calls': False, 'cfg': False, 'dfg': False}},
            'verification': {
                'test_runner': 'auto-detected (jest when package.json uses it, '
                               'pytest for Python test layouts)',
                'typescript': 'npx tsc --noEmit when tsconfig.json exists',
                'python': 'mypy/pyright when configured, else AST parse check'},
            'persistence_warnings': list(_PERSIST_WARNINGS)}


@app.get('/metrics/llm', dependencies=[Depends(auth)])
async def metrics_llm():
    """Cumulative model-call counters for this process (see ai_agents/llm.py)."""
    return dict(llm.stats)


class FeedbackBody(BaseModel):
    session_id: str
    request_id: Optional[str] = None
    rating: Literal['up', 'down']
    note: str = ''
    question: str = ''
    reply: str = ''


@app.post('/feedback', dependencies=[Depends(auth)])
async def feedback(body: FeedbackBody):
    """Thumbs up/down on an answer; appended to data/feedback.jsonl for review."""
    _append_jsonl(_FEEDBACK_PATH, {
        'ts': int(time.time()), 'session': body.session_id[:8],
        'request_id': body.request_id or '', 'rating': body.rating,
        'note': body.note[:500], 'question': body.question[:300],
        'reply': body.reply[:500]})
    return {'ok': True}


@app.get('/graph', dependencies=[Depends(auth)], response_model=GraphResponse)
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


@app.get('/repos', dependencies=[Depends(auth)], response_model=RepositoryListResponse)
async def repos():
    return {'active': config.REPO_ROOT.name, 'repos': [repository.info(n) for n in repository.list_repos()]}


@app.post('/repos/select', dependencies=[Depends(auth)], response_model=RepositorySelectResponse)
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


@app.get('/repos/{repo_name}/tree', dependencies=[Depends(auth)], response_model=RepositoryTreeResponse)
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


@app.get('/repos/{repo_name}/file', dependencies=[Depends(auth)], response_model=RepositoryFileResponse)
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
            # Re-check under the session lock: /repos/select treats a held session
            # lock as a blocker, so once we hold it no switch can start, and if one
            # is in progress or already completed these checks refuse the turn.
            try:
                _refuse_if_switching()
                _require_active_repo(body.repo)
                await _check_session_repo(body.session_id)
            except HTTPException as exc:
                yield 'data: ' + json.dumps({'type': 'error', 'error': exc.detail}) + '\n\n'
                return
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
            try:
                final_response = AskResponse.model_validate(
                    final_response).model_dump(mode='json')
            except Exception as exc:
                yield 'data: ' + json.dumps(
                    {'type': 'error',
                     'error': 'Final response failed contract validation: %s' % exc}) + '\n\n'
                return
            yield 'data: ' + json.dumps({'type': 'final_state', 'response': final_response}) + '\n\n'

    return StreamingResponse(gen(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache'})


async def _run_turn(body):
    message = types.Content(role='user', parts=[types.Part(text=body.text)])
    reply = ''
    agents = []
    async for event in runner.run_async(user_id=USER, session_id=body.session_id, new_message=message):
        if event.author and event.author not in agents:
            agents.append(event.author)
        if event.is_final_response() and event.content and event.content.parts:
            reply = ' '.join(p.text for p in event.content.parts if getattr(p, 'text', None))
    _last_agents[body.session_id] = agents
    return reply


def _evidence_ids(state: dict) -> list:
    """Evidence entries usable as graph node ids. Older turns or buggy writers
    may leave dicts/scalars in state['evidence']; only strings are ids."""
    return [e for e in state.get('evidence', []) if isinstance(e, str)]


def _unverified_evidence(state: dict) -> list:
    from ai_agents.tools.graph_tools import _graph
    nodes = _graph()['nodes']
    return [i for i in _evidence_ids(state) if i not in nodes]


def _security_scan_summary(state):
    """Compact record of the deterministic security scan for the validation
    record — independent of whether a model review ran."""
    from ai_agents.tools.exec_tools import security_blockers
    scan = state.get('security_scan') or {}
    fs = scan.get('findings') or []
    new = [f for f in fs if f.get('introduced_by_current_change')]
    return {'status': scan.get('status', 'not_run'),
            'scanner': scan.get('scanner'),
            'scanner_version': scan.get('scanner_version'),
            'ruleset_version': scan.get('ruleset_version'),
            'introduced': len(new), 'preexisting': len(fs) - len(new),
            'blocking': security_blockers(state, state.get('worktree', ''))}


def _code_review_summary(state):
    """Compact verdict + blocker count from the independent code review, for the
    validation record. None when no review ran this turn."""
    from ai_agents.tools.exec_tools import _review_verdict
    cr = _review_verdict(state)
    if cr is None:
        return None
    findings = cr.get('findings') or []
    blockers = [f for f in findings
                if isinstance(f, dict) and str(f.get('severity') or '').lower() == 'blocker']
    return {'verdict': cr.get('verdict'), 'summary': str(cr.get('summary') or '')[:300],
            'blockers': len(blockers),
            'suggested_tests': [str(t)[:120] for t in (cr.get('suggested_tests') or [])[:10]],
            'security': cr.get('security') or {'status': 'not_analysed'}}


def _parse_agent_result(value):
    """Fail-closed adapter: dicts, JSON strings and AgentResult instances are
    accepted; anything else raises TypeError."""
    from ai_agents.agent_result import AgentResult

    if isinstance(value, AgentResult):
        return value
    if isinstance(value, dict):
        return AgentResult.model_validate(value)
    if isinstance(value, str):
        return AgentResult.model_validate_json(value)
    raise TypeError(f"unsupported specialist result type: {type(value).__name__}")


def _agent_result_view(state):
    """Validate state['result_*'] payloads against the common AgentResult
    contract. Returns (answer, limitations, degraded): the first specialist
    answer found, evidence-path validation errors, and whether any result
    failed validation. Malformed populated results degrade the response
    rather than disappearing silently."""
    from ai_agents.agent_result import AgentResult, validate_evidence_paths
    limitations, degraded, answer = [], False, ''
    for key, value in state.items():
        if not key.startswith('result_'):
            continue
        if value is None or value == '' or value == {} or value == []:
            continue  # specialist did not run / produced nothing
        try:
            res = _parse_agent_result(value)
        except Exception as exc:
            degraded = True
            limitations.append('%s: result failed AgentResult validation: %s'
                               % (key, exc))
            continue
        if res.status in ('partial', 'unsupported', 'failed'):
            degraded = True
            if res.reason:
                limitations.append('%s: %s' % (key, res.reason))
            limitations.extend('%s: %s' % (key, lim) for lim in res.limitations)
        errs = validate_evidence_paths(res, config.REPO_ROOT)
        if errs:
            degraded = True
            limitations.extend('%s: %s' % (key, e) for e in errs)
        if res.answer and not answer:
            answer = res.answer
    return answer, limitations, degraded


def _validated_agent_result_entry(agent_name, value):
    """One /task agent_results entry. The raw payload is validated against
    the AgentResult envelope and repository evidence-path rules before any
    of it is presented: an invalid result is marked 'invalid' with its
    validation errors and an empty summary — never a verified code fact."""
    from ai_agents.agent_result import AgentResult, validate_evidence_paths
    entry = {
        'agent': agent_name,
        'summary': value.get('summary', ''),
        'confidence': value.get('confidence', 0),
        'status': value.get('status', 'unknown')
    }
    try:
        res = _parse_agent_result(value)
        path_errs = validate_evidence_paths(res, config.REPO_ROOT)
        if path_errs:
            entry.update(status='invalid', validated=False,
                         validation_errors=path_errs, summary='')
        elif res.status in ('partial', 'unsupported', 'failed'):
            entry.update(status=res.status, validated=False,
                         validation_errors=[
                             res.reason or 'specialist reported %s'
                             % res.status])
        else:
            entry['validated'] = True
    except Exception as exc:
        entry.update(status='invalid', validated=False,
                     validation_errors=[str(exc)], summary='')
    return entry


def _worktree_review(state: dict) -> dict:
    """The change under review, read straight from the sandbox worktree (git), not from model text.

    Gives the UI the complete diff (the model used to copy it into a tool call, which could cut it
    short), the files and branch, and the same fingerprint the test runner records, so the UI can
    show exactly which change a test run covered. Returns {} when there is no worktree."""
    wt = state.get('worktree')
    if not wt or not Path(str(wt)).is_dir():
        return {}

    def git(*args):
        p = subprocess.run(['git', *args], cwd=str(wt), capture_output=True, text=True, timeout=15)
        return p.stdout if p.returncode == 0 else ''

    try:
        subprocess.run(['git', 'add', '-N', '.'], cwd=str(wt), capture_output=True, text=True, timeout=15)
        diff = git('diff', 'HEAD')
        files = [f for f in git('diff', '--name-only', 'HEAD').splitlines() if f.strip()]
        branch = git('rev-parse', '--abbrev-ref', 'HEAD').strip()
        fp = _worktree_fingerprint(str(wt))
    except Exception:
        logging.getLogger('uvicorn.error').exception('worktree review failed')
        return {}
    lines = diff.splitlines()
    return {
        'diff': diff[:400000],
        'files': files,
        'branch': branch,
        'diff_hash': fp.get('diff_hash', ''),
        'additions': sum(1 for l in lines if l.startswith('+') and not l.startswith('+++')),
        'deletions': sum(1 for l in lines if l.startswith('-') and not l.startswith('---')),
    }


def _build_ask_response(reply: str, error: str, state: dict) -> dict:
    """Build the standardized response for /ask and /ask/stream endpoints.

    This unified function ensures both endpoints return the same structure.
    """
    agent_answer, result_limitations, results_degraded = _agent_result_view(state)
    if not reply and agent_answer:
        reply = agent_answer
    last = state.get('last_test_run') or {}
    commands = list(state.get('scene_commands', []))
    pending = _s(state.get('pending_approval'))
    approval_type = state.get('approval_type', '')
    has_patch = state.get('proposed_patch') or state.get('result_software_eng')

    # The diff the developer reviews must be the real worktree diff, never a model-copied one.
    review = _worktree_review(state) if (has_patch or pending or last) else {}
    if review.get('diff'):
        ghost_node = ''
        kept = []
        for c in commands:
            if isinstance(c, dict) and c.get('type') == 'show_ghost_diff':
                ghost_node = ghost_node or str(c.get('node_id') or '')
                continue
            kept.append(c)
        kept.append({'type': 'show_ghost_diff', 'node_id': ghost_node, 'diff': review['diff']})
        commands = kept

    # Structured evidence items for the contract: {file, first_line,
    # last_line, node_id, kind}. kind is 'confirmed' for graph nodes the
    # tools actually returned; anything else stays in unverified_evidence.
    from ai_agents.tools.graph_tools import _graph as _g
    nodes = _g()['nodes']
    evidence_items = []
    for eid in _evidence_ids(state):
        n = nodes.get(eid) or {}
        evidence_items.append({
            'node_id': str(eid),
            'file': str(n.get('file') or ''),
            'first_line': int(n.get('start') or n.get('line') or 0),
            'last_line': int(n.get('end') or n.get('line') or 0),
            'kind': 'confirmed' if n else 'unsupported',
        })

    resp = {
        'reply': reply,
        'error': error,
        'scene_commands': commands,
        'pending_approval': pending,
        'approval_type': approval_type,
        'approved': bool(state.get('approved', False)),
        'test_results': _s(state.get('test_results')),
        'code_review': _s(state.get('code_review')),
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
    if review:
        resp['validated'] = {'task_id': state.get('active_task_id') or '',
                             'branch': review['branch'], 'files': review['files'],
                             'diff_hash': review['diff_hash'],
                             'additions': review['additions'], 'deletions': review['deletions']}
    if results_degraded:
        # Only present when an AgentResult payload failed validation, so the
        # standard response shape is unchanged for healthy turns.
        resp['status'] = 'partial'
        resp['limitations'] = result_limitations
    return resp


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


_METRICS_PATH = config.ROOT / 'data' / 'metrics.jsonl'
_FEEDBACK_PATH = config.ROOT / 'data' / 'feedback.jsonl'
_last_agents = {}   # session_id -> agents that spoke in the last turn


def _llm_snapshot():
    return {k: llm.stats.get(k, 0) for k in
            ('requests', 'prompt_tokens', 'output_tokens', 'model_ms', 'pace_ms')}


def _ask_metrics(before, t_start, session_id):
    now = _llm_snapshot()
    return {'model_calls': now['requests'] - before['requests'],
            'prompt_tokens': now['prompt_tokens'] - before['prompt_tokens'],
            'output_tokens': now['output_tokens'] - before['output_tokens'],
            'model_ms': now['model_ms'] - before['model_ms'],
            'pace_ms': now['pace_ms'] - before['pace_ms'],
            'latency_ms': int((time.monotonic() - t_start) * 1000),
            'agents': _last_agents.pop(session_id, []),
            'model': config.MODEL_NAME, 'lite_model': config.LITE_MODEL_NAME}


def _append_jsonl(path, row):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as f:
            print(json.dumps(row), file=f)
    except Exception:
        pass   # metrics must never break a request


def _log_metrics(body, resp):
    row = {'ts': int(time.time()), 'session': body.session_id[:8],
           'request_id': body.request_id or '',
           'error': bool(resp.get('error')),
           'evidence': len(resp.get('evidence_items') or []),
           'unverified': len(resp.get('unverified_evidence') or []),
           'tool_errors': len(resp.get('tool_errors') or []),
           'proposal_status': resp.get('proposal_status', ''),
           **resp.get('metrics', {})}
    if os.getenv('JARVIS_LOG_PROMPTS') == '1':   # off by default: prompts can hold code
        row['text'] = body.text[:300]
    _append_jsonl(_METRICS_PATH, row)


_FAST_CALLERS = re.compile('^[ ]*(?:who|what)[ ]+calls[ ]+`?([A-Za-z_][A-Za-z0-9_.]*)`?[ ]*[?]?[ ]*$', re.I)


def _fast_answer(text):
    """Deterministic answer for simple 'who calls X' questions, straight from the
    graph index — no model calls. Off unless JARVIS_FAST_PATH=1. Returns None when
    disabled, unmatched, or the name is unknown/ambiguous (agents handle those)."""
    if os.getenv('JARVIS_FAST_PATH') != '1':
        return None
    m = _FAST_CALLERS.match(text or '')
    if not m:
        return None
    from ai_agents.tools.graph_tools import _graph
    g = _graph()
    hits = [n for n in g['nodes'].values()
            if n.get('name') == m.group(1) and n.get('kind') in ('function', 'method')]
    if len(hits) != 1:
        return None                    # unknown or ambiguous: let the agents handle it
    t = hits[0]
    callers = [g['nodes'][e['src']] for e in g['in'].get(t['id'], [])
               if e.get('type') == 'calls' and e['src'] in g['nodes']]
    if callers:
        lines = ['%s (%s)' % (c['name'], c.get('file', '?')) for c in callers[:20]]
        reply = '%s is called by: %s.' % (t['name'], '; '.join(lines))
    else:
        reply = 'No callers of %s were found in the index.' % t['name']
    return {'reply': reply,
            'evidence': [t['id']] + [c['id'] for c in callers[:20]],
            'commands': [{'type': 'highlight_callers', 'node_id': t['id']}]}


@app.post('/ask', dependencies=[Depends(auth)], response_model=AskResponse)
async def ask(body: AskBody):
    """Non-streaming endpoint for compatibility."""
    _refuse_if_switching()
    _require_active_repo(body.repo)
    await _check_session_repo(body.session_id)
    before = _llm_snapshot()
    t_start = time.monotonic()
    reply = ''
    async with locks[body.session_id]:
        # Re-check under the session lock (see /ask/stream): the switch guard in
        # /repos/select only sees held session locks, so this makes the repo
        # check and the turn atomic with respect to a repository switch.
        _refuse_if_switching()
        _require_active_repo(body.repo)
        await _check_session_repo(body.session_id)
        if await _seen_request(body.session_id, body.request_id):
            return {'reply': '', 'error': '', 'duplicate': True,
                    'scene_commands': [], 'pending_approval': '', 'approved': False,
                    'test_results': '', 'test_source': '', 'evidence': [],
                    'unverified_evidence': [], 'task_id': '', 'proposal_status': 'none'}
        session = await ensure(body.session_id)
        await set_state(body.session_id, _turn_state(body, session.state))
        error = ''
        fast = _fast_answer(body.text)          # deterministic path; None unless JARVIS_FAST_PATH=1
        if fast:
            reply = fast['reply']
            _last_agents[body.session_id] = ['fast_path']
            await set_state(body.session_id, {'evidence': fast['evidence'],
                                              'scene_commands': fast['commands']})
        else:
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
    logger.info('ask: %d model calls, %s', llm.stats['requests'] - before['requests'],
                'error' if error else 'ok')
    logger.info('reply: %s', reply[:200] if reply else error)
    resp = _build_ask_response(reply, error, state)
    resp['metrics'] = _ask_metrics(before, t_start, body.session_id)
    _log_metrics(body, resp)
    return resp


@app.post('/approve', dependencies=[Depends(auth)], response_model=ApprovalResponse)
async def approve(body: ApproveBody):
    _refuse_if_switching()
    _require_active_repo(body.repo)
    await _check_session_repo(body.session_id)
    async with locks[body.session_id]:
        # Re-check under the session lock so a repository switch cannot slip
        # between the checks above and the approval/commit below.
        _refuse_if_switching()
        _require_active_repo(body.repo)
        await _check_session_repo(body.session_id)
        if await _seen_request(body.session_id, body.request_id):
            return {'ok': True, 'duplicate': True, 'detail': 'Request already handled.'}
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
                      'code_review': _code_review_summary(state),
                      'security_scan': _security_scan_summary(state),
                      'checks_not_run': last.get('checks_not_run') or []}
            await set_state(body.session_id, {**cleared, 'approved': True,
                            'last_commit': {'branch': result['branch'], 'commit': result['commit']},
                            'validation_record': record})
            result['validation'] = record
        return {'action': 'commit', **result}


class PromoteBody(BaseModel):
    session_id: str
    repo: Optional[str] = None


@app.post('/promote', dependencies=[Depends(auth)], response_model=PromotionResponse)
async def promote(body: PromoteBody):
    _refuse_if_switching()
    _require_active_repo(body.repo)
    await _check_session_repo(body.session_id)
    async with locks[body.session_id]:
        # Re-check under the session lock so a repository switch cannot slip
        # between the checks above and the promote below.
        _refuse_if_switching()
        _require_active_repo(body.repo)
        await _check_session_repo(body.session_id)
        state = (await ensure(body.session_id)).state
        last = state.get('last_commit') or {}
        if not last.get('branch'):
            return {'ok': False, 'detail': 'No committed change to promote.'}
        res = await asyncio.to_thread(promote_branch, last['branch'])
        if not res.get('ok'):
            return res
        persisted = True
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
                persisted = await _persist_design(body.session_id)
        return {**res, 'graph_refreshed': True, 'nodes': len(g['nodes']),
                'edges': len(g['edges']), **_persist_fields(persisted)}


@app.get('/task/{session_id}', dependencies=[Depends(auth)], response_model=TaskResponse)
async def get_task_state(session_id: str):
    """Get current task state for a session in Unity-compatible format."""
    session = await ensure(session_id)
    state = session.state

    # Flatten results into a list for Unity. Every specialist result is
    # parsed and validated against the AgentResult contract first; an
    # invalid result is reported as invalid, never as a completed answer.
    agent_results = []
    for key in ['result_repository', 'result_code_understanding', 'result_relationship',
                'result_data_flow', 'result_software_eng', 'result_testing',
                'result_visualization', 'result_orchestrator', 'result_conversational']:
        value = state.get(key, {})
        if value and isinstance(value, dict):
            agent_name = key.replace('result_', '')
            agent_results.append(_validated_agent_result_entry(agent_name, value))

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
from ai_agents.tools.design_ops import apply_design_op, finalize_edit

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
    plan_stale = bool(state.get('plan_stale')) or (
        bool(view.get('plan')) and bool(view.get('architecture')) and
        (view['architecture'].get('revision') != (view['plan'].get('architecture_revision') or 0)))
    view['plan_stale'] = plan_stale
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


async def _persist_design(session_id) -> bool:
    """Persist design state to disk; returns False (and records a warning)
    when the write fails so endpoints can surface it instead of silently
    losing the design."""
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
    return ok


def _persist_fields(persisted: bool) -> dict:
    return {'persisted': persisted,
            **({} if persisted else {'persistence_warning':
               'Design state could not be saved to disk; it exists only in the active session.'})}


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


@app.post('/design/requirements', dependencies=[Depends(auth)], response_model=DesignResponse)
async def design_requirements(body: DesignIdeaBody):
    await _check_session_repo(body.session_id)
    res = await asyncio.to_thread(extract_requirements, body.idea_text)
    await set_state(body.session_id, {'design_requirements': res['requirements']})
    persisted = await _persist_design(body.session_id)
    # Never present a heuristic fallback as a clean AI result.
    if res.get('source') == 'heuristic':
        res = dict(res)
        res['warning'] = ('Requirements were produced by the heuristic '
                          'fallback, not the AI model.')
    return {**res, **_persist_fields(persisted)}


@app.post('/design/propose', dependencies=[Depends(auth)], response_model=DesignResponse)
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

    await set_state(body.session_id, {'design_in_progress': True})
    try:
        prop = await asyncio.to_thread(propose_architecture, req)
    finally:
        await set_state(body.session_id, {'design_in_progress': False})
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
    persisted = await _persist_design(body.session_id)
    out = {'status': 'ok', 'provenance': arch['provenance'],
           'requirements_source': req_source,
           'requirements': req, 'architecture': arch,
           **_persist_fields(persisted)}
    if 'heuristic' in (arch['provenance'], req_source):
        out['warning'] = ('Part of this proposal came from the heuristic fallback, '
                          'not the AI model. Review it before relying on it.')
    return out


@app.get('/design/{session_id}', dependencies=[Depends(auth)], response_model=DesignResponse)
async def design_get(session_id: str):
    return await _design_view(session_id)


@app.post('/design/{session_id}/edit', dependencies=[Depends(auth)], response_model=DesignResponse)
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
        working, err = apply_design_op(working, op)
        if err:
            raise HTTPException(status_code=400, detail=err)
        touched_questions = touched_questions or (op.op or '').strip() in question_ops
    had_plan = bool(view.get('plan'))
    working = finalize_edit(arch, working, 'edited_by_user')
    # Editing the design invalidates the implementation plan AND any
    # repository comparison computed against the previous revision.
    delta = {'design': working, 'implementation_plan': {}, 'design_compare': {}, 'plan_stale': had_plan}
    if touched_questions and isinstance(view.get('requirements'), dict):
        # Keep the requirements document in step: its open_questions mirror the architecture's.
        req = copy.deepcopy(view['requirements'])
        req['open_questions'] = list(working.get('open_questions') or [])
        delta['design_requirements'] = req
    await set_state(session_id, delta)
    persisted = await _persist_design(session_id)
    return {'ok': True, 'architecture': working, **_persist_fields(persisted)}


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


@app.post('/design/{session_id}/compare', dependencies=[Depends(auth)], response_model=DesignResponse)
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
    persisted = await _persist_design(session_id)
    return {**res, **_persist_fields(persisted)}


@app.post('/design/{session_id}/approve', dependencies=[Depends(auth)], response_model=DesignResponse)
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
    delta = {'design': arch}
    if not body.approved:
        # A rejected design must not leave an approved plan behind: drop the plan and
        # any comparison, and mark the plan stale if one existed (same as an edit does).
        delta.update({'implementation_plan': {}, 'design_compare': {},
                      'plan_stale': bool(view.get('plan'))})
    await set_state(session_id, delta)
    plan = None
    if body.approved:
        # Approving completes the design workflow: generate the implementation
        # plan immediately so the developer does not need a second manual step.
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
        await set_state(session_id, {'implementation_plan': plan, 'plan_stale': False})
    persisted = await _persist_design(session_id)
    if not persisted:
        raise HTTPException(status_code=503, detail='Design persistence failed')
    out = {'ok': True, 'architecture': arch, **_persist_fields(persisted)}
    if plan is not None:
        out['plan'] = plan
    return out


@app.post('/plan/generate', dependencies=[Depends(auth)], response_model=ImplementationPlanResponse)
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
    await set_state(body.session_id, {'plan_in_progress': True})
    try:
        res = await asyncio.to_thread(generate_implementation_plan,
                                      {'architecture': arch}, None,
                                      str(gpath) if gpath else None)
    finally:
        await set_state(body.session_id, {'plan_in_progress': False})
    plan = {'architecture_version': arch.get('version'),
            'architecture_revision': arch.get('revision'),
            'repo': repo_name or config.REPO_ROOT.name,
            'status': 'active',
            'tasks': res['tasks'], 'circular': res.get('circular') or [],
            'cycle_paths': res.get('cycle_paths') or []}
    await set_state(body.session_id, {'implementation_plan': plan, 'plan_stale': False})
    persisted = await _persist_design(body.session_id)
    if not persisted:
        raise HTTPException(status_code=503, detail='Design persistence failed')
    return {**plan, **_persist_fields(persisted)}


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
    persisted = await _persist_design(session_id)
    return {'ok': True, 'task': task, 'plan': plan, **_persist_fields(persisted)}


@app.get('/agents', dependencies=[Depends(auth)], response_model=AgentListResponse)
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


@app.get('/progress/{session_id}', dependencies=[Depends(auth)], response_model=ProgressResponse)
async def progress(session_id: str, since: int = 0):
    """Get progress events for a session.
    Use this endpoint to light agent status dots in Unity.
    """
    state = (await ensure(session_id)).state
    log = list(state.get('task_log', []))
    return {'busy': locks[session_id].locked(),
            'steps': [{'i': i, 'agent': e['agent'], 'kind': e['kind']} for i, e in enumerate(log) if i >= since]}


@app.get('/tools', dependencies=[Depends(auth)], response_model=ToolListResponse)
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



# ---------------------------------------------------------------------------
# Workspace editing: a human edits files in the sandbox worktree directly (VR
# keyboard or IDE). Every write goes through resolve_worktree_write, is
# conflict-checked with base_hash, carries a request_id so retries cannot
# double-apply, is refused while an agent turn holds the session lock, and
# clears all four verification evidence keys so /approve stays honest.
# The worktree absolute path is never returned to the client.

class WsOpenBody(BaseModel):
    session_id: str
    repo: Optional[str] = None


class WsFileBody(BaseModel):
    session_id: str
    path: str
    content: str
    base_hash: str            # hash of the file text the client edited from
    repo: Optional[str] = None
    request_id: Optional[str] = None


class WsLineEditBody(BaseModel):
    session_id: str
    path: str
    op: Literal['replace', 'insert_after', 'delete']
    start: int                # 1-based first line
    end: Optional[int] = None  # 1-based last line (replace/delete)
    text: str = ''
    base_hash: str
    repo: Optional[str] = None
    request_id: Optional[str] = None


class WsRevertBody(BaseModel):
    session_id: str
    path: str
    repo: Optional[str] = None
    request_id: Optional[str] = None


def _ws_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _ws_read_text(path):
    """Full decoded text of a worktree file plus a truncation flag. The hash is
    always computed over the FULL text so base_hash stays stable for big files."""
    raw = Path(path).read_bytes()
    text = raw.decode('utf-8', errors='replace')
    cap = repository.MAX_BROWSER_FILE_BYTES
    return text, len(raw) > cap or len(text) > cap


def _ws_content(text):
    return text[:repository.MAX_BROWSER_FILE_BYTES]


async def _ws_guard(session_id, repo):
    """Shared checks for every workspace route."""
    _refuse_if_switching()
    _require_active_repo(repo)
    await _check_session_repo(session_id)


def _ws_worktree(state):
    wt = state.get('worktree')
    if not wt or not Path(str(wt)).is_dir():
        raise HTTPException(status_code=409,
                            detail='No sandbox worktree. Call /workspace/open first.')
    return Path(str(wt))


def _ws_refuse_busy(session_id):
    """Writes are refused while an agent turn holds the session lock. Must run
    BEFORE acquiring the lock: inside it locked() is always true."""
    if locks[session_id].locked():
        raise HTTPException(status_code=409,
                            detail='An agent turn is running for this session. Try again when it finishes.')


async def _ws_clear_evidence(session_id):
    """A human edit invalidates the same four evidence keys an agent patch does."""
    await set_state(session_id, {'last_test_run': {}, 'last_typecheck': {},
                                 'code_review': {}, 'security_scan': {}})


def _ws_write_atomic(target, content):
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + '.jarvis-tmp')
    tmp.write_text(content, encoding='utf-8')
    os.replace(tmp, target)


def _ws_rel(target, wt):
    return target.relative_to(Path(wt).resolve()).as_posix()


@app.post('/workspace/open', dependencies=[Depends(auth)])
async def ws_open(body: WsOpenBody):
    """Ensure the session has a sandbox worktree; create one on branch
    jarvis/edit when missing. Never returns the absolute path."""
    await _ws_guard(body.session_id, body.repo)
    state = (await ensure(body.session_id)).state
    wt = state.get('worktree')
    if not wt or not Path(str(wt)).is_dir():
        ctx = SimpleNamespace(state=dict(state), agent_name='workspace')
        res = await asyncio.to_thread(create_worktree, ctx, 'jarvis/edit')
        if res.get('status') != 'ok':
            raise HTTPException(status_code=500,
                                detail=res.get('error') or 'could not create worktree')
        new_wt = ctx.state.get('worktree')
        await set_state(body.session_id, {
            'worktree': new_wt,
            'last_test_run': {}, 'last_typecheck': {},
            'code_review': {}, 'security_scan': {}})
        wt = new_wt
    wt_path = Path(str(wt))

    def _info():
        branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                cwd=str(wt_path), capture_output=True, text=True,
                                timeout=10).stdout.strip()
        dirty = bool(subprocess.run(['git', 'status', '--porcelain'],
                                    cwd=str(wt_path), capture_output=True, text=True,
                                    timeout=10).stdout.strip())
        return branch, dirty

    branch, dirty = await asyncio.to_thread(_info)
    return {'ok': True, 'worktree_name': wt_path.name, 'branch': branch, 'dirty': dirty}


@app.get('/workspace/file', dependencies=[Depends(auth)])
async def ws_get_file(session_id: str, path: str, repo: Optional[str] = None):
    """Read a file from the session worktree when one exists, else from the
    main checkout. Returns content, its sha256 hash and the read source."""
    await _ws_guard(session_id, repo)
    state = (await ensure(session_id)).state
    wt = state.get('worktree')
    if wt and Path(str(wt)).is_dir():
        wt_root = Path(str(wt)).resolve()
        try:
            target = resolve_worktree_read(path, root=wt_root)
        except PathResolutionError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        rel = target.relative_to(wt_root)
        if rel.parts and rel.parts[0] in ('.git', 'node_modules'):
            raise HTTPException(status_code=400, detail='path is not readable: ' + path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail='file not found: ' + path)
        text, truncated = await asyncio.to_thread(_ws_read_text, target)
        truncated = truncated or len(text) > repository.MAX_BROWSER_FILE_BYTES
        return {'path': rel.as_posix(), 'content': _ws_content(text),
                'hash': _ws_hash(text), 'truncated': truncated,
                'size': len(text.encode('utf-8')), 'source': 'worktree'}
    try:
        data = await asyncio.to_thread(repository.read_browser_file,
                                       config.REPO_ROOT.name, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='file not found: ' + path)
    except KeyError:
        raise HTTPException(status_code=404, detail='unknown repository')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    content = data.get('content') or ''
    return {'path': data.get('path') or path, 'content': content,
            'hash': _ws_hash(content), 'truncated': bool(data.get('truncated')),
            'size': data.get('size', len(content)), 'source': 'main'}


@app.put('/workspace/file', dependencies=[Depends(auth)])
async def ws_put_file(body: WsFileBody):
    """Whole-file write into the worktree with base_hash conflict detection."""
    await _ws_guard(body.session_id, body.repo)
    _ws_refuse_busy(body.session_id)
    start = time.time()
    async with locks[body.session_id]:
        if await _seen_request(body.session_id, body.request_id):
            return {'ok': True, 'duplicate': True}
        state = (await ensure(body.session_id)).state
        wt = _ws_worktree(state)
        try:
            target = resolve_worktree_write(body.path, root=wt)
        except PathResolutionError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        payload = body.content.encode('utf-8')
        if len(payload) > config.MAX_EDIT_BYTES:
            raise HTTPException(
                status_code=413,
                detail='content is larger than JARVIS_MAX_EDIT_BYTES (%d bytes)'
                       % config.MAX_EDIT_BYTES)
        if target.exists():
            if target.is_dir():
                raise HTTPException(status_code=400,
                                    detail='path is a directory: ' + body.path)
            current_text = (await asyncio.to_thread(_ws_read_text, target))[0]
            if _ws_hash(current_text) != body.base_hash:
                return JSONResponse(status_code=409, content={
                    'ok': False, 'conflict': True,
                    'current_hash': _ws_hash(current_text),
                    'current_content': _ws_content(current_text),
                    'detail': 'File changed outside the editor.'})
        elif body.base_hash not in ('', _ws_hash('')):
            return JSONResponse(status_code=409, content={
                'ok': False, 'conflict': True, 'current_hash': '',
                'current_content': '',
                'detail': 'File was deleted outside the editor.'})
        rel = _ws_rel(target, wt)
        await asyncio.to_thread(_ws_write_atomic, target, body.content)
        await _ws_clear_evidence(body.session_id)
        syn = await asyncio.to_thread(quick_syntax_check, wt, rel)
        symbols = await asyncio.to_thread(worktree_symbols, wt, rel)
        log_audit('user', 'workspace_write',
                  {'path': body.path, 'bytes': len(payload)}, 'ok',
                  time.time() - start)
        return {'ok': True, 'hash': _ws_hash(body.content), 'size': len(payload),
                'syntax_errors': syn['errors'], 'checked': syn['checked'],
                'symbols': symbols, 'verification': 'stale'}


@app.post('/workspace/edit', dependencies=[Depends(auth)])
async def ws_edit_lines(body: WsLineEditBody):
    """Line-range edit for the VR UI; same guarantees as PUT /workspace/file."""
    await _ws_guard(body.session_id, body.repo)
    _ws_refuse_busy(body.session_id)
    start = time.time()
    async with locks[body.session_id]:
        if await _seen_request(body.session_id, body.request_id):
            return {'ok': True, 'duplicate': True}
        state = (await ensure(body.session_id)).state
        wt = _ws_worktree(state)
        try:
            target = resolve_worktree_write(body.path, root=wt)
        except PathResolutionError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not target.is_file():
            raise HTTPException(status_code=404,
                                detail='file not found: ' + body.path)
        current_text = (await asyncio.to_thread(_ws_read_text, target))[0]
        if _ws_hash(current_text) != body.base_hash:
            return JSONResponse(status_code=409, content={
                'ok': False, 'conflict': True,
                'current_hash': _ws_hash(current_text),
                'current_content': _ws_content(current_text),
                'detail': 'File changed outside the editor.'})
        new_text, err = apply_line_edit(current_text, body.op,
                                       body.start, body.end, body.text)
        if err:
            raise HTTPException(status_code=400, detail=err)
        rel = _ws_rel(target, wt)
        await asyncio.to_thread(_ws_write_atomic, target, new_text)
        await _ws_clear_evidence(body.session_id)
        syn = await asyncio.to_thread(quick_syntax_check, wt, rel)
        symbols = await asyncio.to_thread(worktree_symbols, wt, rel)
        log_audit('user', 'workspace_edit',
                  {'path': body.path, 'op': body.op, 'start': body.start,
                   'end': body.end}, 'ok', time.time() - start)
        return {'ok': True, 'hash': _ws_hash(new_text),
                'size': len(new_text.encode('utf-8')),
                'lines': len(new_text.splitlines()),
                'syntax_errors': syn['errors'], 'checked': syn['checked'],
                'symbols': symbols, 'verification': 'stale'}


@app.post('/workspace/revert', dependencies=[Depends(auth)])
async def ws_revert(body: WsRevertBody):
    """Restore a worktree file to HEAD, or delete it when it is untracked."""
    await _ws_guard(body.session_id, body.repo)
    _ws_refuse_busy(body.session_id)
    start = time.time()
    async with locks[body.session_id]:
        if await _seen_request(body.session_id, body.request_id):
            return {'ok': True, 'duplicate': True}
        state = (await ensure(body.session_id)).state
        wt = _ws_worktree(state)
        try:
            target = resolve_worktree_write(body.path, root=wt)
        except PathResolutionError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        rel = _ws_rel(target, wt)

        def _do_revert():
            in_head = subprocess.run(
                ['git', 'cat-file', '-e', 'HEAD:' + rel],
                cwd=str(wt), capture_output=True).returncode == 0
            existed = in_head or target.exists()
            if in_head:
                subprocess.run(['git', 'checkout', 'HEAD', '--', rel],
                               cwd=str(wt), capture_output=True)
            elif target.exists():
                target.unlink()
            return existed

        existed = await asyncio.to_thread(_do_revert)
        if not existed:
            raise HTTPException(status_code=404,
                                detail='nothing to revert: ' + body.path)
        await _ws_clear_evidence(body.session_id)
        log_audit('user', 'workspace_revert', {'path': body.path}, 'ok',
                  time.time() - start)
        new_hash = ''
        if target.is_file():
            new_hash = _ws_hash((await asyncio.to_thread(_ws_read_text, target))[0])
        return {'ok': True, 'hash': new_hash, 'reverted': True,
                'verification': 'stale'}


@app.get('/workspace/diff', dependencies=[Depends(auth)])
async def ws_diff(session_id: str, repo: Optional[str] = None):
    """The cumulative worktree diff plus the fingerprint /approve compares."""
    await _ws_guard(session_id, repo)
    state = (await ensure(session_id)).state
    review = await asyncio.to_thread(_worktree_review, state)
    if not review:
        return {'ok': True, 'worktree': False, 'diff': '', 'files': [],
                'branch': '', 'diff_hash': '', 'additions': 0, 'deletions': 0}
    return {'ok': True, 'worktree': True, **review}


def _ws_evidence_state(record, fp, fingerprinted):
    """fresh / stale / missing for one piece of verification evidence."""
    if not record:
        return 'missing'
    if record.get('diff_hash') and fp.get('diff_hash') \
            and record['diff_hash'] != fp['diff_hash']:
        return 'stale'
    if fingerprinted and record.get('head') and fp.get('head') \
            and record['head'] != fp['head']:
        return 'stale'
    return 'fresh'


@app.get('/workspace/status', dependencies=[Depends(auth)])
async def ws_status(session_id: str, repo: Optional[str] = None):
    """Worktree state plus the freshness of each verification evidence key.
    Used by the UI and for IDE-change polling (diff_hash changes without a
    UI write mean the file changed on disk)."""
    await _ws_guard(session_id, repo)
    state = (await ensure(session_id)).state
    wt = state.get('worktree')
    has_wt = bool(wt) and Path(str(wt)).is_dir()
    out = {'ok': True, 'busy': locks[session_id].locked(), 'worktree': has_wt,
           'dirty': False, 'files': [], 'diff_hash': '', 'head': '',
           'verification': {'tests': 'missing', 'typecheck': 'missing',
                            'review': 'missing', 'security': 'missing'}}
    if not has_wt:
        return out
    fp = await asyncio.to_thread(_worktree_fingerprint, str(wt))
    review = await asyncio.to_thread(_worktree_review, state)
    out.update({'dirty': bool(review.get('files')),
                'files': review.get('files') or [],
                'diff_hash': fp.get('diff_hash', ''),
                'head': fp.get('head', '')})
    out['verification'] = {
        'tests': _ws_evidence_state(state.get('last_test_run'), fp, True),
        'typecheck': _ws_evidence_state(state.get('last_typecheck'), fp, True),
        'security': _ws_evidence_state(state.get('security_scan'), fp, True),
        # code_review carries no guaranteed fingerprint; it is cleared by every
        # write, so presence means it post-dates the last edit.
        'review': _ws_evidence_state(state.get('code_review'), fp, False),
    }
    return out


# ---------------------------------------------------------------------------
# Verification and approval for human workspace edits. /workspace/verify runs
# the deterministic checks directly (no model turn), /workspace/review runs
# the independent reviewer agent on the worktree diff, and /workspace/submit
# moves a fully verified edit into the same pending_approval flow /approve
# already gates. All three take the session lock and refuse while an agent
# turn holds it, exactly like the write routes.

_WS_VERIFY_STEPS = {'tests', 'typecheck', 'security'}


class WsVerifyBody(BaseModel):
    session_id: str
    steps: List[str] = []           # subset of tests/typecheck/security; empty = all
    test_files: List[str] = []
    repo: Optional[str] = None
    request_id: Optional[str] = None


class WsReviewBody(BaseModel):
    session_id: str
    repo: Optional[str] = None
    request_id: Optional[str] = None


class WsSubmitBody(BaseModel):
    session_id: str
    repo: Optional[str] = None
    request_id: Optional[str] = None


def _ws_verify_view(state, fp):
    """The evidence keys plus their fresh/stale/missing status, in the shape
    /workspace/status reports so the UI renders both identically."""
    return {
        'test_run': state.get('last_test_run') or {},
        'typecheck': state.get('last_typecheck') or {},
        'security_scan': state.get('security_scan') or {},
        'verification': {
            'tests': _ws_evidence_state(state.get('last_test_run'), fp, True),
            'typecheck': _ws_evidence_state(state.get('last_typecheck'), fp, True),
            'security': _ws_evidence_state(state.get('security_scan'), fp, True),
            'review': _ws_evidence_state(state.get('code_review'), fp, False),
        },
    }


@app.post('/workspace/verify', dependencies=[Depends(auth)])
async def ws_verify(body: WsVerifyBody):
    """Run test/typecheck/security verification directly against the worktree
    and record the evidence under the same state keys the agent tools write,
    so /approve treats a human edit exactly like an agent patch."""
    await _ws_guard(body.session_id, body.repo)
    _ws_refuse_busy(body.session_id)
    if USE_CACHED_TESTS:
        # /approve rejects cached results anyway; refuse up front instead of
        # recording evidence that can never approve.
        raise HTTPException(
            status_code=409,
            detail='Cached test results are enabled (JARVIS_CACHED_TESTS=1); '
                   'verification must run live.')
    steps = [s for s in (body.steps or sorted(_WS_VERIFY_STEPS))
             if s in _WS_VERIFY_STEPS]
    if not steps:
        raise HTTPException(status_code=400,
                            detail='No valid steps; use tests, typecheck, security.')
    async with locks[body.session_id]:
        if await _seen_request(body.session_id, body.request_id):
            state = (await ensure(body.session_id)).state
            fp = await _ws_fingerprint(state)
            return {'ok': True, 'duplicate': True, **_ws_verify_view(state, fp)}
        state = (await ensure(body.session_id)).state
        wt = _ws_worktree(state)
        # The tools mutate tool_context.state; a plain dict copy keeps the real
        # session state untouched until we copy the evidence keys back.
        ctx = SimpleNamespace(state=dict(state), agent_name='workspace')
        ran = []
        try:
            if 'tests' in steps:
                await asyncio.to_thread(run_tests, list(body.test_files or []), ctx)
                ran.append('last_test_run')
            if 'typecheck' in steps:
                await asyncio.to_thread(run_typecheck, ctx)
                ran.append('last_typecheck')
            if 'security' in steps:
                await asyncio.to_thread(run_security_scan, ctx)
                ran.append('security_scan')
        finally:
            delta = {k: ctx.state.get(k, {}) for k in ran}
            if delta:
                await set_state(body.session_id, delta)
        state = (await ensure(body.session_id)).state
        fp = await _ws_fingerprint(state)
        return {'ok': True, **_ws_verify_view(state, fp)}


async def _ws_fingerprint(state):
    wt = state.get('worktree')
    if not wt or not Path(str(wt)).is_dir():
        return {}
    try:
        return await asyncio.to_thread(_worktree_fingerprint, str(wt))
    except Exception:
        return {}


@app.post('/workspace/review', dependencies=[Depends(auth)])
async def ws_review(body: WsReviewBody):
    """Independent review of the worktree diff for a human edit.

    Default: run the code_reviewer agent against this session — it writes
    state['code_review'] through the same output_key contract the fix pipeline
    uses, so review_blockers and /approve see no difference. With
    JARVIS_ALLOW_HUMAN_REVIEW=1 a human acceptance is recorded instead (the
    independent check is skipped; keep it off unless you accept that)."""
    await _ws_guard(body.session_id, body.repo)
    _ws_refuse_busy(body.session_id)
    async with locks[body.session_id]:
        if await _seen_request(body.session_id, body.request_id):
            return {'ok': True, 'duplicate': True}
        state = (await ensure(body.session_id)).state
        _ws_worktree(state)
        if config.ALLOW_HUMAN_REVIEW:
            review = {'verdict': 'approve',
                      'summary': 'Human review accepted (JARVIS_ALLOW_HUMAN_REVIEW).',
                      'findings': [], 'acceptance': []}
            await set_state(body.session_id, {'code_review': review})
            state = dict(state)
            state['code_review'] = review
            return {'ok': True, 'source': 'human', 'verdict': 'approve',
                    'summary': review['summary'],
                    'blockers': review_blockers(state)}
        from ai_agents.agents.fix import code_reviewer
        reviewer_runner = Runner(agent=code_reviewer, app_name=APP,
                                 session_service=sessions)
        message = types.Content(role='user', parts=[types.Part(text=(
            'Review the current sandbox worktree diff for commit. '
            'Follow your review instructions exactly and return the review JSON.'))])

        async def _run():
            async for _event in reviewer_runner.run_async(
                    user_id=USER, session_id=body.session_id,
                    new_message=message):
                pass
        try:
            await asyncio.wait_for(_run(), TURN_TIMEOUT)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504,
                                detail='Review agent timed out.')
        except HTTPException:
            raise
        except Exception as exc:
            logging.getLogger('uvicorn.error').exception('workspace review failed')
            raise HTTPException(status_code=500,
                                detail='Review agent failed: %s' % str(exc)[:200])
        state = (await ensure(body.session_id)).state
        cr = _review_verdict(state) or {}
        blockers = review_blockers(state)
        return {'ok': not blockers, 'source': 'agent',
                'verdict': str(cr.get('verdict') or ''),
                'summary': str(cr.get('summary') or '')[:500],
                'blockers': blockers}


@app.post('/workspace/submit', dependencies=[Depends(auth)])
async def ws_submit(body: WsSubmitBody):
    """Move a verified human edit into the commit approval flow. Runs the same
    verification_blockers gate /approve uses, then sets pending_approval so the
    existing HOLD-TO-APPROVE / PROMOTE path works unchanged."""
    await _ws_guard(body.session_id, body.repo)
    _ws_refuse_busy(body.session_id)
    async with locks[body.session_id]:
        if await _seen_request(body.session_id, body.request_id):
            return {'ok': True, 'duplicate': True}
        state = (await ensure(body.session_id)).state
        wt = _ws_worktree(state)
        why = await asyncio.to_thread(verification_blockers, state, str(wt), False)
        if why:
            return JSONResponse(status_code=409,
                                content={'ok': False, 'blockers': why})
        pending = 'Commit your edit to a sandbox branch'
        await set_state(body.session_id, {'pending_approval': pending,
                                          'approved': False,
                                          'approval_type': 'commit'})
        review = await asyncio.to_thread(_worktree_review, state)
        return {'ok': True, 'pending_approval': pending, 'review': review}
