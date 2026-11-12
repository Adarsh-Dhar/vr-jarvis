"""Tests for the runtime tracing subsystem (Phase 3)."""
import json
import time
from pathlib import Path

import pytest


class _Ctx:
    def __init__(self, state):
        self.state = state


def _tools():
    from ai_agents.tools import runtime_tools as rt
    return rt.start_runtime_trace, rt.stop_runtime_trace, rt.get_runtime_trace


def _wait(trace_id, get, ctx, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = get(trace_id, ctx)
        if res.get('status') not in ('running', None):
            return res
        time.sleep(0.05)
    return get(trace_id, ctx)


@pytest.fixture
def traced_repo(tmp_path):
    wt = tmp_path / 'wt'
    wt.mkdir()
    (wt / 'service.py').write_text(
        'def normalize(v):\n    return v.strip().lower()\n')
    (wt / 'app.py').write_text(
        'from service import normalize\n\n\n'
        'def handle(raw):\n'
        '    return normalize(raw)\n\n\n'
        'handle(" X ")\n')
    (wt / 'boom.py').write_text('raise ValueError("boom")\n')
    (wt / 'handled.py').write_text(
        'def f():\n'
        '    try:\n'
        '        raise KeyError("k")\n'
        '    except KeyError:\n'
        '        return 1\n'
        'f()\n')
    (wt / 'sleep.py').write_text('import time\ntime.sleep(60)\n')
    return wt


def _run(ctx_state, command, **kw):
    start, stop, get = _tools()
    ctx = _Ctx(ctx_state)
    res = start(command, ctx, **kw)
    if res.get('status') != 'ok':
        return res, ctx
    tid = res['trace_id']
    ctx.state.setdefault('trace_sessions', {})[tid] = ctx_state['worktree']
    return tid, ctx


def test_call_and_return_recorded(traced_repo):
    state = {'worktree': str(traced_repo)}
    tid, ctx = _run(state, ['app.py'])
    _, _, get = _tools()
    res = _wait(tid, get, ctx)
    assert res['status'] in ('completed', 'failed')
    kinds = {(e['kind'], e['function']) for e in res['events']}
    assert any(k == 'call' and 'normalize' in f for k, f in kinds)
    assert any(k == 'return' and 'normalize' in f for k, f in kinds)
    seqs = [e['sequence'] for e in res['events']]
    assert seqs == sorted(seqs)


def test_exception_events(traced_repo):
    state = {'worktree': str(traced_repo)}
    tid, ctx = _run(state, ['handled.py'])
    _, _, get = _tools()
    res = _wait(tid, get, ctx)
    excs = [e for e in res['events'] if e['kind'] == 'exception']
    assert excs and all('exception_type' in e for e in excs)
    tid2, ctx = _run(state, ['boom.py'])
    res2 = _wait(tid2, get, ctx)
    assert res2['status'] == 'failed'
    assert res2['exit_code'] != 0


def test_call_edges_and_locations(traced_repo):
    state = {'worktree': str(traced_repo)}
    tid, ctx = _run(state, ['app.py'])
    _, _, get = _tools()
    res = _wait(tid, get, ctx)
    assert {'source': 'handle', 'target': 'normalize'} in res['call_edges']
    for e in res['events']:
        p = traced_repo / e['file']
        assert p.is_file()
        n = len(p.read_text().splitlines())
        if e['function'] == '<module>':
            assert 0 <= e['line'] <= n
        else:
            assert 1 <= e['line'] <= n + 2


def test_stop_and_timeout(traced_repo):
    state = {'worktree': str(traced_repo)}
    start, stop, get = _tools()
    ctx = _Ctx(state)
    res = start(['sleep.py'], ctx, timeout_seconds=60)
    tid = res['trace_id']
    ctx.state['trace_sessions'] = {tid: str(traced_repo)}
    out = stop(tid, ctx)
    assert out['trace_status'] in ('stopped', 'completed', 'failed')
    # timeout path through the manager directly
    from ai_agents.runtime import trace_manager as tm
    t2 = tm.start(str(traced_repo), ['sleep.py'], timeout_s=1)
    deadline = time.time() + 10
    while time.time() < deadline:
        r = tm.get(t2['trace_id'])
        if r['status'] == 'timed_out':
            break
        time.sleep(0.1)
    assert tm.get(t2['trace_id'])['status'] == 'timed_out'


def test_session_isolation_and_containment(traced_repo, tmp_path):
    outside = tmp_path / 'outside.py'
    outside.write_text('print(1)\n')
    state = {'worktree': str(traced_repo)}
    start, stop, get = _tools()
    ctx = _Ctx(state)
    bad = start(['../outside.py'], ctx)
    assert bad['status'] == 'error'
    # unknown trace_id for this session
    res = get('trace_nonexistent', ctx)
    assert res['status'] == 'not_found'


def test_no_sensitive_data(traced_repo):
    (traced_repo / 'secret.py').write_text(
        "password = 'hunter2'\napi_key = 'sk-123'\n"
        "def f(api_key='sk-123'):\n    return api_key\nf()\n")
    state = {'worktree': str(traced_repo)}
    tid, ctx = _run(state, ['secret.py'])
    _, _, get = _tools()
    res = _wait(tid, get, ctx)
    blob = json.dumps(res)
    assert 'hunter2' not in blob and 'sk-123' not in blob


def test_registry_level_and_guard():
    from ai_agents.registry.tool_registry import get_tool_registry
    reg = get_tool_registry()
    assert reg.get('start_runtime_trace').level == 'execute'
    assert reg.get('get_runtime_trace').level == 'read'
