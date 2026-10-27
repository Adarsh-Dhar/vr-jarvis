'''Layer 1: the root agent must not replay every old tool result on each turn.'''
from types import SimpleNamespace

import pytest
from google.genai import types

from tests.harness.pkg import mod

cb = mod('callbacks')
pytestmark = pytest.mark.skipif(not hasattr(cb, 'trim_history'),
                                reason='callbacks.trim_history not installed (see the hardening overlay)')


def text(role, t):
    return types.Content(role=role, parts=[types.Part(text=t)])


def call():
    return types.Content(role='model', parts=[types.Part(function_call=types.FunctionCall(name='x', args={}))])


def response():
    return types.Content(role='user', parts=[types.Part(function_response=types.FunctionResponse(name='x', response={'big': 'y' * 5000}))])


def run(contents):
    req = SimpleNamespace(contents=list(contents))
    assert cb.trim_history(None, req) is None
    return req.contents


def test_old_tool_traffic_and_context_noise_are_dropped_but_the_current_turn_is_kept():
    old = [text('user', 'earlier question'), call(), response(),
           text('user', 'For context: [investigator_agent] called tool `get_callers` with parameters {}'),
           text('user', 'For context: [investigate_scene] said: Two paths depend on this code.'),
           text('model', 'Two paths depend on this code.')]
    now = [text('user', 'What breaks if I change this?'), call(), response()]
    out = run(old + now)
    assert out[-3:] == now, 'the current turn, including its own tool calls, must be untouched'
    kept = out[:-3]
    assert all(not any(p.function_call or p.function_response for p in c.parts) for c in kept)
    assert not any('called tool' in (c.parts[0].text or '') for c in kept)
    assert any('said:' in (c.parts[0].text or '') for c in kept)


def test_history_length_is_capped():
    many = [text('user' if i % 2 == 0 else 'model', 'turn %d' % i) for i in range(100)]
    out = run(many + [text('user', 'latest')])
    assert len(out) <= cb.MAX_HISTORY + 1 and out[-1].parts[0].text == 'latest'


def test_empty_request_is_safe():
    assert run([]) == []
