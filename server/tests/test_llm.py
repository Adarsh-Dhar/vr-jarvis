'''Retry and pacing for model calls, tested against a local fake Gemini server (no network, no API key needed).'''
import asyncio
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ai_agents import llm


class _Fake(BaseHTTPRequestHandler):
    hits = []
    fail_first = 0

    def log_message(self, *args):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0) or 0))
        _Fake.hits.append(time.monotonic())
        if len(_Fake.hits) <= _Fake.fail_first:
            body, code = json.dumps({'error': {'code': 503, 'message': 'The model is overloaded.', 'status': 'UNAVAILABLE'}}).encode(), 503
        else:
            body, code = json.dumps({'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'hello'}]}, 'finishReason': 'STOP'}],
                                     'usageMetadata': {'promptTokenCount': 1, 'candidatesTokenCount': 1, 'totalTokenCount': 2}}).encode(), 200
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY', 'dummy')
    _Fake.hits.clear()
    server = HTTPServer(('127.0.0.1', 0), _Fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % server.server_address[1]
    server.shutdown()


async def _ask(model, name='t'):
    agent = LlmAgent(name=name, model=model, instruction='Say hello.')
    sessions = InMemorySessionService()
    await sessions.create_session(app_name='a', user_id='u', session_id='s')
    runner = Runner(agent=agent, app_name='a', session_service=sessions)
    reply = ''
    async for ev in runner.run_async(user_id='u', session_id='s', new_message=types.Content(role='user', parts=[types.Part(text='hi')])):
        if ev.is_final_response() and ev.content:
            reply = ''.join(p.text or '' for p in ev.content.parts)
    return reply


def test_a_plain_model_fails_on_the_first_503(fake):
    _Fake.fail_first = 2
    with pytest.raises(Exception, match='503'):
        asyncio.run(_ask(Gemini(model='m', base_url=fake, retry_options=None)))
    assert len(_Fake.hits) == 1


def test_make_model_retries_through_503s(fake, monkeypatch):
    monkeypatch.setattr(llm.RETRY, 'attempts', 3)
    monkeypatch.setattr(llm.RETRY, 'initial_delay', 0.05)
    _Fake.fail_first = 2
    assert asyncio.run(_ask(llm.make_model('m', base_url=fake))) == 'hello'
    assert len(_Fake.hits) == 3


def test_retry_gives_up_after_the_configured_attempts(fake, monkeypatch):
    monkeypatch.setattr(llm.RETRY, 'initial_delay', 0.01)
    _Fake.fail_first = 100
    with pytest.raises(Exception, match='503'):
        asyncio.run(_ask(llm.make_model('m', base_url=fake)))
    assert len(_Fake.hits) == llm.RETRY.attempts


def test_pacing_spaces_simultaneous_calls(fake, monkeypatch):
    monkeypatch.setenv('JARVIS_LLM_RPM', '120')        # one call every 0.5 s
    _Fake.fail_first = 0
    model = llm.make_model('m', base_url=fake)

    async def run():
        await asyncio.gather(*[_ask(model, 'a%d' % i) for i in range(4)])
    asyncio.run(run())
    gaps = [b - a for a, b in zip(_Fake.hits, _Fake.hits[1:])]
    assert len(_Fake.hits) == 4 and all(g >= 0.35 for g in gaps), gaps


def test_stats_count_every_model_call(fake):
    _Fake.fail_first = 0
    before = llm.stats['requests']
    asyncio.run(_ask(llm.make_model('m', base_url=fake)))
    assert llm.stats['requests'] == before + 1
