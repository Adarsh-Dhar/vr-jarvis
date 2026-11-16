'''API key rotation, tested against a local fake Gemini server (no network, no real keys).'''
import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import errors, types

from ai_agents import api_keys, llm


# ---------- loading ----------

def test_load_keys_order_numeric_and_dedupe():
    env = {'GOOGLE_API_KEY': 'k0', 'GOOGLE_API_KEY_10': 'k10', 'GOOGLE_API_KEY_2': 'k2',
           'GOOGLE_API_KEY_1': 'k1', 'GOOGLE_API_KEY_3': 'k0', 'JARVIS_API_KEYS': 'k2, kx ,'}
    assert api_keys.load_keys(env) == ['k0', 'k1', 'k2', 'k10', 'kx']


def test_load_keys_strips_quotes_and_ignores_empty():
    assert api_keys.load_keys({'GOOGLE_API_KEY': '"abc"', 'GOOGLE_API_KEY_1': '  '}) == ['abc']
    assert api_keys.load_keys({}) == []


# ---------- classification ----------

def _err(cls, code, status, message, details=None):
    body = {'error': {'code': code, 'status': status, 'message': message, **(details or {})}}
    return cls(code, body)


def test_classify_quota_uses_retry_delay():
    e = _err(errors.ClientError, 429, 'RESOURCE_EXHAUSTED', 'quota', {'details': [{'retryDelay': '34s'}]})
    assert api_keys.classify(e) == ('quota', 34.0)


def test_classify_daily_quota_rests_long():
    e = _err(errors.ClientError, 429, 'RESOURCE_EXHAUSTED', 'Quota exceeded: GenerateRequestsPerDayPerProjectPerModel')
    kind, secs = api_keys.classify(e)
    assert kind == 'quota' and secs >= 60


def test_classify_expired_and_forbidden_are_dead():
    assert api_keys.classify(_err(errors.ClientError, 400, 'INVALID_ARGUMENT', 'API key expired. Please renew the API key.'))[0] == 'dead'
    assert api_keys.classify(_err(errors.ClientError, 403, 'PERMISSION_DENIED', 'denied'))[0] == 'dead'


def test_classify_other_errors_do_not_blame_the_key():
    assert api_keys.classify(_err(errors.ServerError, 503, 'UNAVAILABLE', 'overloaded'))[0] == 'other'
    assert api_keys.classify(_err(errors.ClientError, 400, 'INVALID_ARGUMENT', 'bad request body'))[0] == 'other'
    assert api_keys.classify(ValueError('x'))[0] == 'other'


# ---------- pool ----------

def test_pool_sticky_then_moves_on_and_recovers():
    p = api_keys.KeyPool(['a', 'b', 'c'])
    assert p.get() == 'a' and p.get() == 'a'
    p.mark('a', 'quota', 0.2)
    assert p.get() == 'b'
    p.mark('b', 'dead')
    assert p.get() == 'c'
    p.mark('c', 'quota', 0.2)
    assert p.get() is None and p.wait_seconds() > 0
    time.sleep(0.3)
    assert p.get() == 'a'                      # a recovered; b stays dead


def test_pool_all_dead_has_no_wait():
    p = api_keys.KeyPool(['a'])
    p.mark('a', 'dead')
    assert p.get() is None and p.wait_seconds() is None


def test_pool_round_robin_spreads_calls():
    p = api_keys.KeyPool(['a', 'b', 'c'], 'round_robin')
    assert [p.get() for _ in range(4)] == ['a', 'b', 'c', 'a']


def test_status_never_shows_full_key():
    p = api_keys.KeyPool(['secret-key-1234'])
    assert p.status()[0]['key'] == '...1234'


def test_repeated_quota_failures_back_off():
    p = api_keys.KeyPool(['a'])
    p.mark('a', 'quota', 10)
    first = p._until['a'] - time.time()
    p.mark('a', 'quota', 10)
    second = p._until['a'] - time.time()
    assert second > first * 1.5                     # second rest is roughly double
    p.ok('a')
    p.mark('a', 'quota', 10)
    assert p._until['a'] - time.time() < second      # success resets the backoff


def test_backoff_never_shortens_a_daily_rest():
    p = api_keys.KeyPool(['a'])
    p.mark('a', 'quota', 20000)                      # per-day quota: ~5.5h
    p.mark('a', 'quota', 20000)
    assert p._until['a'] - time.time() > 19000


def test_pool_resumes_last_key_after_restart(tmp_path):
    state = str(tmp_path / 'state.json')
    p = api_keys.KeyPool(['a', 'b', 'c'], state_path=state)
    p.mark('a', 'quota', 60)
    assert p.get() == 'b'                       # last used key is 'b'
    p2 = api_keys.KeyPool(['a', 'b', 'c'], state_path=state)
    assert p2.get() == 'b'                      # first pick after "restart" resumes on 'b'
    assert p2.get() == 'b'                      # and keeps using 'b' while it is usable
    p2.mark('b', 'quota', 60)
    assert p2.get() == 'a'                      # once 'b' rests, normal order resumes: GOOGLE_API_KEY first


def test_pool_round_robin_resumes_after_last_key(tmp_path):
    state = str(tmp_path / 'state.json')
    p = api_keys.KeyPool(['a', 'b', 'c'], 'round_robin', state_path=state)
    assert p.get() == 'a' and p.get() == 'b'      # last used key is 'b'
    p2 = api_keys.KeyPool(['a', 'b', 'c'], 'round_robin', state_path=state)
    assert [p2.get() for _ in range(2)] == ['c', 'a']   # rotation continues after 'b'


def test_pool_state_falls_back_to_first_key_when_last_is_gone(tmp_path):
    state = str(tmp_path / 'state.json')
    p = api_keys.KeyPool(['a', 'b'], state_path=state)
    p.mark('a', 'quota', 60)
    assert p.get() == 'b'
    p2 = api_keys.KeyPool(['a', 'x'], state_path=state)   # 'b' was removed from .env
    assert p2.get() == 'a'


# ---------- end to end through the model wrapper ----------

class _Fake(BaseHTTPRequestHandler):
    behaviour = {}      # key -> 'ok' | 'quota' | 'expired' | 'overload'
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0) or 0))
        key = self.headers.get('x-goog-api-key', '')
        _Fake.seen.append(key)
        mode = _Fake.behaviour.get(key, 'ok')
        if mode == 'quota':
            body, code = {'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED', 'message': 'quota', 'details': [{'retryDelay': '30s'}]}}, 429
        elif mode == 'expired':
            body, code = {'error': {'code': 400, 'status': 'INVALID_ARGUMENT', 'message': 'API key expired. Please renew the API key.'}}, 400
        elif mode == 'overload':
            body, code = {'error': {'code': 503, 'status': 'UNAVAILABLE', 'message': 'overloaded'}}, 503
        else:
            body, code = {'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'hello from ' + key}]}, 'finishReason': 'STOP'}],
                          'usageMetadata': {'promptTokenCount': 1, 'candidatesTokenCount': 1, 'totalTokenCount': 2}}, 200
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def fake(monkeypatch):
    for k in list(__import__('os').environ):
        if k.startswith('GOOGLE_API_KEY'):
            monkeypatch.delenv(k)
    monkeypatch.setenv('JARVIS_LLM_RPM', '0')
    _Fake.behaviour, _Fake.seen = {}, []
    server = HTTPServer(('127.0.0.1', 0), _Fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api_keys.reset()
    yield 'http://127.0.0.1:%d' % server.server_address[1]
    server.shutdown()
    api_keys.reset()


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


def _keys(monkeypatch, *keys):
    for i, k in enumerate(keys):
        monkeypatch.setenv('GOOGLE_API_KEY' if i == 0 else 'GOOGLE_API_KEY_%d' % i, k)
    api_keys.reset()


def test_single_key_behaves_as_before(fake, monkeypatch):
    _keys(monkeypatch, 'only')
    assert asyncio.run(_ask(llm.make_model('m', base_url=fake))) == 'hello from only'


def test_moves_to_next_key_on_quota_and_sticks(fake, monkeypatch):
    _keys(monkeypatch, 'k0', 'k1', 'k2')
    _Fake.behaviour = {'k0': 'quota'}
    model = llm.make_model('m', base_url=fake)
    assert asyncio.run(_ask(model)) == 'hello from k1'
    assert asyncio.run(_ask(model, 'u')) == 'hello from k1'
    assert _Fake.seen == ['k0', 'k1', 'k1']            # k0 tried once, then rested


def test_expired_key_is_dropped_for_good(fake, monkeypatch):
    _keys(monkeypatch, 'k0', 'k1')
    _Fake.behaviour = {'k0': 'expired'}
    model = llm.make_model('m', base_url=fake)
    assert asyncio.run(_ask(model)) == 'hello from k1'
    assert api_keys.get_pool().status()[0]['state'] == 'dead'


def test_cascades_through_several_bad_keys(fake, monkeypatch):
    _keys(monkeypatch, 'k0', 'k1', 'k2')
    _Fake.behaviour = {'k0': 'quota', 'k1': 'expired'}
    assert asyncio.run(_ask(llm.make_model('m', base_url=fake))) == 'hello from k2'


def test_all_keys_out_of_quota_fails_fast(fake, monkeypatch):
    _keys(monkeypatch, 'k0', 'k1')
    _Fake.behaviour = {'k0': 'quota', 'k1': 'quota'}
    monkeypatch.setenv('JARVIS_KEY_MAX_WAIT', '5')
    with pytest.raises(Exception, match='out of quota'):
        asyncio.run(_ask(llm.make_model('m', base_url=fake)))


def test_all_keys_expired_says_so(fake, monkeypatch):
    _keys(monkeypatch, 'k0', 'k1')
    _Fake.behaviour = {'k0': 'expired', 'k1': 'expired'}
    with pytest.raises(Exception, match='invalid or expired'):
        asyncio.run(_ask(llm.make_model('m', base_url=fake)))


def test_overload_does_not_burn_a_key(fake, monkeypatch):
    _keys(monkeypatch, 'k0', 'k1')
    _Fake.behaviour = {'k0': 'overload'}
    with pytest.raises(Exception, match='503'):
        asyncio.run(_ask(llm.make_model('m', base_url=fake)))
    assert api_keys.get_pool().status()[0]['state'] == 'ready'


def test_with_client_rotates_for_direct_calls(monkeypatch):
    for k in list(__import__('os').environ):
        if k.startswith('GOOGLE_API_KEY'):
            monkeypatch.delenv(k)
    _keys(monkeypatch, 'k0', 'k1')
    calls = []

    def fn(client):
        key = client._api_client.api_key
        calls.append(key)
        if key == 'k0':
            raise _err(errors.ClientError, 429, 'RESOURCE_EXHAUSTED', 'quota')
        return 'ok ' + key
    assert api_keys.with_client(fn) == 'ok k1'
    assert calls == ['k0', 'k1']
    api_keys.reset()
