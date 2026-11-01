import asyncio
import json
import os
import subprocess
import uuid
from collections import defaultdict

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
from ai_agents.tools.git_tools import commit_worktree
from ai_agents.tools.graph_tools import get_source

APP, USER = 'jarvis', 'quest'
TOKEN = os.getenv('JARVIS_TOKEN', '')
ASK_TIMEOUT = float(os.getenv('JARVIS_ASK_TIMEOUT', '110'))   # keep below the Unity request timeout

sessions = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP, session_service=sessions)
locks = defaultdict(asyncio.Lock)
app = FastAPI(title='JARVIS bridge')


def auth(authorization: str = Header(default='')):
    # LAN only. Set JARVIS_TOKEN and put the same value in JarvisServerSettings.Token.
    if TOKEN and authorization != 'Bearer ' + TOKEN:
        raise HTTPException(status_code=401, detail='bad token')


def _s(value):
    if value is None or value == '':
        return ''
    return value if isinstance(value, str) else json.dumps(value, default=str)


async def ensure(session_id):
    session = await sessions.get_session(app_name=APP, user_id=USER, session_id=session_id)
    if session is None:
        session = await sessions.create_session(app_name=APP, user_id=USER, session_id=session_id)
    return session


async def set_state(session_id, delta):
    session = await ensure(session_id)
    await sessions.append_event(session, Event(author='user', actions=EventActions(state_delta=delta)))


class AskBody(BaseModel):
    session_id: str
    text: str
    selection: str = ''


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


@app.get('/health')
async def health():
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
        if event.author == 'agent':
            yield {
                "type": "agent_progress",
                "agent": event.agent_name if hasattr(event, 'agent_name') else "unknown",
                "content": _s(event.content) if event.content else ""
            }
        elif event.is_final_response():
            yield {
                "type": "final_response",
                "content": ' '.join(p.text for p in event.content.parts if getattr(p, 'text', None))
            }


@app.post('/ask', dependencies=[Depends(auth)])
async def ask(body: AskBody):
    """Stream agent progress as Server-Sent Events."""
    error = ''
    reply = ''
    state = {}
    
    async with locks[body.session_id]:
        await ensure(body.session_id)
        await set_state(body.session_id, {'selection': body.selection})
        
        try:
            # Streaming response
            async def event_generator():
                async for event in _run_turn_streaming(body):
                    yield f"data: {json.dumps(event)}\n\n"
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"}
            )
        except Exception as exc:
            error = f'{type(exc).__name__}: {str(exc)[:200]}'
            return {"error": error}


# Non-streaming fallback for compatibility
async def _run_turn(body):
    message = types.Content(role='user', parts=[types.Part(text=body.text)])
    reply = ''
    async for event in runner.run_async(user_id=USER, session_id=body.session_id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            reply = ' '.join(p.text for p in event.content.parts if getattr(p, 'text', None))
    return reply


@app.post('/ask/nonstream', dependencies=[Depends(auth)])
async def ask_nonstream(body: AskBody):
    """Non-streaming endpoint for compatibility."""
    error = ''
    reply = ''
    async with locks[body.session_id]:
        await ensure(body.session_id)
        await set_state(body.session_id, {'selection': body.selection})
        try:
            reply = await asyncio.wait_for(_run_turn(body), ASK_TIMEOUT)
        except asyncio.TimeoutError:
            error = 'JARVIS took too long to answer. Try a narrower question.'
        except Exception as exc:
            error = f'{type(exc).__name__}: {str(exc)[:200]}'
        state = (await ensure(body.session_id)).state
    last = state.get('last_test_run') or {}
    commands = list(state.get('scene_commands', []))
    pending = _s(state.get('pending_approval'))
    if (not pending and not error and state.get('proposed_patch') and state.get('worktree')
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


@app.post('/approve', dependencies=[Depends(auth)])
async def approve(body: ApproveBody):
    # The 2 s pinch-hold in the headset is the only thing that should call this.
    async with locks[body.session_id]:
        state = (await ensure(body.session_id)).state
        pending = state.get('pending_approval', '')
        worktree = state.get('worktree', '')
        await set_state(body.session_id, {'approved': body.approved, 'pending_approval': ''})
    if not body.approved:
        return {'ok': True, 'branch': '', 'commit': '', 'detail': 'Rejected. Nothing was changed.'}
    if not pending:
        return {'ok': False, 'branch': '', 'commit': '', 'detail': 'Nothing was waiting for approval.'}
    return {'branch': '', 'commit': '', **commit_worktree(worktree, 'JARVIS: ' + str(pending)[:120])}


@app.get('/task/{session_id}', dependencies=[Depends(auth)])
async def get_task_state(session_id: str):
    """Get current task state for a session."""
    session = await ensure(session_id)
    state = session.state
    return {
        'session_id': session_id,
        'plan': state.get('plan', {}),
        'findings': list(state.get('findings', [])),
        'result_repository': state.get('result_repository', {}),
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

