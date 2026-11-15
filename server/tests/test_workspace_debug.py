"""Debugger routes: /workspace/debug/* runs a worktree .py script under
debugpy and exposes breakpoints/stepping/variables over HTTP."""
import asyncio
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import jarvis_server  # noqa: E402
from jarvis_server import app  # noqa: E402

pytestmark = pytest.mark.skipif(importlib.util.find_spec('debugpy') is None,
                                reason='debugpy is not installed')

H = {'authorization': 'Bearer test-token'}

SCRIPT = 'x = 1\ny = x + 1\nprint(y)\n'


@pytest.fixture(scope='module')
def client():
    # Module-scoped: JARVIS_MAX_SESSIONS caps total sessions per run.
    return TestClient(app)


@pytest.fixture(scope='module')
def sid(client):
    return client.post('/session', headers=H).json()['session_id']


@pytest.fixture
def worktree(tmp_path):
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    (tmp_path / 'script.py').write_text(SCRIPT)
    (tmp_path / 'other.py').write_text('import time\ntime.sleep(30)\n')
    (tmp_path / 'notes.txt').write_text('plain\n')
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'add', '-A'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'commit', '-q', '-m', 'init'], cwd=tmp_path, check=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _cleanup_debug_sessions():
    yield
    for s in list(jarvis_server._debug_sessions):
        jarvis_server._ws_debug_stop(s)


def _sid(client):
    return client.post('/session', headers=H).json()['session_id']


def _bind(sid, worktree):
    asyncio.run(jarvis_server.set_state(sid, {'worktree': str(worktree)}))
    return sid


def _start(client, sid, script='script.py', breakpoints=None):
    return client.post('/workspace/debug/start', headers=H, json={
        'session_id': sid, 'script': script, 'args': [],
        'breakpoints': breakpoints or []})


def _state(client, sid):
    return client.get('/workspace/debug/state',
                      params={'session_id': sid}, headers=H)


def _control(client, sid, action):
    return client.post('/workspace/debug/control', headers=H,
                       json={'session_id': sid, 'action': action})


def _wait_status(client, sid, wanted, timeout=40):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = _state(client, sid)
        last = r.json()
        if last.get('status') == wanted:
            return last
        time.sleep(0.4)
    raise AssertionError('status never became %r; last=%r' % (wanted, last))


class TestDebugSession:
    def test_breakpoint_stop_variables_continue(self, client, sid, worktree):
        _bind(sid, worktree)
        r = _start(client, sid, breakpoints=[{'path': 'script.py', 'line': 2}])
        assert r.status_code == 200 and r.json()['ok'] is True

        st = _wait_status(client, sid, 'stopped')
        assert st['file'].endswith('script.py')
        assert st['line'] == 2
        names = {v['name']: v['value'] for v in st['variables']}
        assert names.get('x') == '1'

        r = _control(client, sid, 'continue')
        assert r.status_code == 200
        st = _wait_status(client, sid, 'exited')
        # The program's stdout can land a beat after the exited event.
        deadline = time.time() + 10
        while time.time() < deadline and not any('2' in l for l in st['output']):
            time.sleep(0.3)
            st = _state(client, sid).json()
        assert any('2' in line for line in st['output'])

    def test_step_over(self, client, sid, worktree):
        _bind(sid, worktree)
        _start(client, sid, breakpoints=[{'path': 'script.py', 'line': 2}])
        _wait_status(client, sid, 'stopped')
        r = _control(client, sid, 'next')
        assert r.status_code == 200
        # Stepping over line 2 lands on line 3, still paused.
        st = _wait_status(client, sid, 'stopped')
        assert st['line'] == 3
        names = {v['name']: v['value'] for v in st['variables']}
        assert names.get('y') == '2'
        r = _control(client, sid, 'continue')
        assert r.status_code == 200
        st = _wait_status(client, sid, 'exited')
        assert st['status'] == 'exited'

    def test_script_outside_worktree_rejected(self, client, sid, worktree):
        _bind(sid, worktree)
        r = _start(client, sid, script='../outside.py')
        assert r.status_code == 400

    def test_non_python_rejected(self, client, sid, worktree):
        _bind(sid, worktree)
        r = _start(client, sid, script='notes.txt')
        assert r.status_code == 400

    def test_missing_script_rejected(self, client, sid, worktree):
        _bind(sid, worktree)
        r = _start(client, sid, script='nope.py')
        assert r.status_code == 400

    def test_second_start_stops_first(self, client, sid, worktree):
        _bind(sid, worktree)
        _start(client, sid, script='script.py',
               breakpoints=[{'path': 'script.py', 'line': 2}])
        _wait_status(client, sid, 'stopped')
        first = jarvis_server._debug_sessions[sid]
        r = _start(client, sid, script='other.py')
        assert r.status_code == 200
        assert jarvis_server._debug_sessions[sid] is not first
        assert first.finished

    def test_control_without_session_409(self, client, sid, worktree):
        _bind(sid, worktree)
        r = _control(client, sid, 'continue')
        assert r.status_code == 409

    def test_idle_timeout_kills_process(self, client, sid, worktree, monkeypatch):
        import ai_agents.runtime.debug_session as ds_mod
        monkeypatch.setattr(ds_mod, '_IDLE_SECONDS', 1)
        _bind(sid, worktree)
        r = _start(client, sid, script='other.py')   # sleeps 30s, no breakpoints
        assert r.status_code == 200
        st = _wait_status(client, sid, 'exited', timeout=30)
        assert st['status'] == 'exited'

    def test_state_without_session(self, client, sid, worktree):
        _bind(sid, worktree)
        st = _state(client, sid).json()
        assert st['status'] == 'none'
