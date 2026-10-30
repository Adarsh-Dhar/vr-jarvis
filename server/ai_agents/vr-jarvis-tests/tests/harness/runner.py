'''Run an agent tree through the real ADK Runner and capture everything a test needs to assert on.'''
import asyncio
import time
import uuid
from dataclasses import dataclass, field

from google.adk.agents.run_config import RunConfig
from google.adk.runners import InMemoryRunner
from google.genai import types

from .pkg import mod

DEFAULT_STATE = mod('state').DEFAULT_STATE

APP = 'ai_agents'


@dataclass
class Trace:
    text: str = ''
    final_text: str = ''
    events: list = field(default_factory=list)
    calls: list = field(default_factory=list)      # (agent, tool, args)
    results: list = field(default_factory=list)    # (agent, tool, response)
    authors: list = field(default_factory=list)    # unique, in order
    state: dict = field(default_factory=dict)
    latency_s: float = 0.0
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0

    def tools(self, agent=None):
        return [t for a, t, _ in self.calls if agent is None or a == agent]

    def count(self, tool):
        return sum(1 for _, t, _ in self.calls if t == tool)

    @property
    def scene(self):
        return self.state.get('scene_commands', [])


def fresh_tree(root, llm=None):
    '''Clone an agent tree so tests never mutate the shared module-level agents.'''
    tree = root.clone()
    if llm is not None:
        _swap(tree, llm)
    return tree


def _swap(agent, llm):
    if hasattr(agent, 'model'):
        agent.model = llm
    for sub in getattr(agent, 'sub_agents', []) or []:
        _swap(sub, llm)


class Session:
    '''One user session. Call say() once per user turn.'''

    def __init__(self, root, state=None, user='u1', run_config=None, app=APP):
        self.root = root
        self.app = app
        self.user = user
        self.run_config = run_config
        self.initial = {**DEFAULT_STATE, **(state or {})}
        self.runner = InMemoryRunner(agent=root, app_name=app)
        self.session_id = None

    async def start(self):
        s = await self.runner.session_service.create_session(
            app_name=self.app, user_id=self.user, state=self.initial)
        self.session_id = s.id
        return self

    async def get_state(self):
        s = await self.runner.session_service.get_session(
            app_name=self.app, user_id=self.user, session_id=self.session_id)
        return dict(s.state)

    async def say(self, text, state_delta=None):
        if self.session_id is None:
            await self.start()
        msg = types.Content(role='user', parts=[types.Part(text=text)])
        tr = Trace(text=text)
        t0 = time.perf_counter()
        kw = {'run_config': self.run_config} if self.run_config else {}
        if state_delta:
            kw['state_delta'] = state_delta
        async for ev in self.runner.run_async(user_id=self.user, session_id=self.session_id,
                                              new_message=msg, **kw):
            tr.events.append(ev)
            if ev.author not in tr.authors and ev.author != 'user':
                tr.authors.append(ev.author)
            for fc in ev.get_function_calls() or []:
                tr.calls.append((ev.author, fc.name, dict(fc.args or {})))
            for fr in ev.get_function_responses() or []:
                tr.results.append((ev.author, fr.name, fr.response))
            if ev.content and ev.content.role == 'model' and not ev.partial:
                tr.llm_calls += 1
            um = getattr(ev, 'usage_metadata', None)
            if um:
                tr.tokens_in += getattr(um, 'prompt_token_count', 0) or 0
                tr.tokens_out += getattr(um, 'candidates_token_count', 0) or 0
            if ev.is_final_response() and ev.content and ev.content.parts:
                txt = ''.join(p.text or '' for p in ev.content.parts)
                if txt:
                    tr.final_text = txt
        tr.latency_s = time.perf_counter() - t0
        tr.state = await self.get_state()
        return tr


async def run_turn(root, text, state=None, run_config=None, state_delta=None, timeout=60):
    s = Session(root, state=state, run_config=run_config, user='u-' + uuid.uuid4().hex[:6])
    await s.start()
    return await asyncio.wait_for(s.say(text, state_delta=state_delta), timeout=timeout)


def limited(n):
    return RunConfig(max_llm_calls=n)
