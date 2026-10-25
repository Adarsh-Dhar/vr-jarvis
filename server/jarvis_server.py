import asyncio
import json
import os
import uuid
from collections import defaultdict

from fastapi import Depends, FastAPI, Header, HTTPException
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from ai_agents.agent import root_agent

APP, USER = 'jarvis', 'quest'
TOKEN = os.getenv('JARVIS_TOKEN', '')

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


@app.post('/ask', dependencies=[Depends(auth)])
async def ask(body: AskBody):
    async with locks[body.session_id]:
        await ensure(body.session_id)
        if body.selection:
            await set_state(body.session_id, {'selection': body.selection})
        message = types.Content(role='user', parts=[types.Part(text=body.text)])
        reply = ''
        async for event in runner.run_async(user_id=USER, session_id=body.session_id, new_message=message):
            if event.is_final_response() and event.content and event.content.parts:
                reply = ' '.join(p.text for p in event.content.parts if getattr(p, 'text', None))
        state = (await ensure(body.session_id)).state
    return {
        'reply': reply,
        'scene_commands': state.get('scene_commands', []),   # cleared every turn by init_state
        'pending_approval': _s(state.get('pending_approval')),
        'approved': bool(state.get('approved', False)),
        'test_results': _s(state.get('test_results')),
        'evidence': list(state.get('evidence', [])),
    }


@app.post('/approve', dependencies=[Depends(auth)])
async def approve(body: ApproveBody):
    # The 2 s pinch-hold in the headset is the only thing that should call this.
    async with locks[body.session_id]:
        await set_state(body.session_id, {'approved': body.approved, 'pending_approval': ''})
    return {'ok': True}
