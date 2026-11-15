"""POST /workspace/run: allowlisted argv-only execution inside the session
worktree with SSE output, env scrubbing, timeout and truncation."""
import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import jarvis_server  # noqa: E402
from jarvis_server import app  # noqa: E402

H = {'authorization': 'Bearer test-token'}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def worktree(tmp_path):
    """A real git checkout standing in for the session sandbox worktree."""
    import subprocess
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    (tmp_path / 'app.py').write_text('print("hello from app")\n')
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'add', '-A'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'commit', '-q', '-m', 'init'], cwd=tmp_path, check=True)
    return tmp_path


def _sid(client):
    return client.post('/session', headers=H).json()['session_id']


def _bind(client, worktree):
    sid = _sid(client)
    asyncio.run(jarvis_server.set_state(sid, {'worktree': str(worktree)}))
    return sid


def _run(client, sid, argv, timeout=0):
    return client.post('/workspace/run', headers=H, json={
        'session_id': sid, 'argv': argv, 'timeout': timeout})


def _events(resp):
    """Parse the SSE body into a list of event dicts."""
    out = []
    for raw in resp.text.split('\n'):
        raw = raw.strip()
        if raw.startswith('data:'):
            out.append(json.loads(raw[5:].strip()))
    return out


class TestWorkspaceRun:
    def test_disallowed_command_rejected(self, client, worktree):
        sid = _bind(client, worktree)
        for argv in (['sh', '-c', 'echo hi'], ['rm', '-rf', '/'],
                     ['/bin/bash', '-c', 'x'], ['python; rm -rf /'],
                     [], ['python'] + ['x'] * 40):
            r = _run(client, sid, argv)
            assert r.status_code == 400, argv

    def test_requires_worktree(self, client):
        sid = _sid(client)
        r = _run(client, sid, ['python3', '-c', 'print(1)'])
        assert r.status_code == 409

    def test_streams_output_and_exit_code(self, client, worktree):
        sid = _bind(client, worktree)
        r = _run(client, sid, ['python3', '-c', 'print("hi"); print("bye")'])
        assert r.status_code == 200
        assert r.headers['content-type'].startswith('text/event-stream')
        evs = _events(r)
        outs = ''.join(e.get('out', '') for e in evs)
        assert 'hi' in outs and 'bye' in outs
        assert evs[-1] == {'exit': 0}

    def test_runs_in_worktree_cwd(self, client, worktree):
        sid = _bind(client, worktree)
        r = _run(client, sid,
                 ['python3', '-c', 'import os; print(os.getcwd())'])
        evs = _events(r)
        cwd = ''.join(e.get('out', '') for e in evs).strip()
        assert Path(cwd).resolve() == worktree.resolve()

    def test_nonzero_exit_reported(self, client, worktree):
        sid = _bind(client, worktree)
        r = _run(client, sid, ['python3', '-c', 'import sys; sys.exit(3)'])
        evs = _events(r)
        assert evs[-1] == {'exit': 3}

    def test_timeout_kills_process(self, client, worktree):
        sid = _bind(client, worktree)
        r = _run(client, sid,
                 ['python3', '-c', 'import time; time.sleep(30)'], timeout=1)
        evs = _events(r)
        assert any(e.get('timeout') for e in evs)
        assert not any('exit' in e for e in evs)

    def test_env_scrubs_credentials(self, client, worktree, monkeypatch):
        monkeypatch.setenv('JARVIS_RUN_TEST_TOKEN', 'sekrit')
        monkeypatch.setenv('JARVIS_RUN_TEST_API_KEY', 'sekrit')
        sid = _bind(client, worktree)
        code = ('import os;'
                'print("TOKEN" , "JARVIS_RUN_TEST_TOKEN" in os.environ);'
                'print("KEY", "JARVIS_RUN_TEST_API_KEY" in os.environ);'
                'print("PATH", "PATH" in os.environ)')
        r = _run(client, sid, ['python3', '-c', code])
        evs = _events(r)
        out = ''.join(e.get('out', '') for e in evs)
        assert 'TOKEN False' in out
        assert 'KEY False' in out
        assert 'PATH True' in out

    def test_spawn_failure_reports_error(self, client, worktree, monkeypatch):
        sid = _bind(client, worktree)
        # 'python' missing from PATH inside the scrubbed env is hard to force;
        # instead patch create_subprocess_exec to raise.
        async def _boom(*a, **k):
            raise FileNotFoundError('no such program')
        monkeypatch.setattr(asyncio, 'create_subprocess_exec', _boom)
        r = _run(client, sid, ['python3', '-c', 'print(1)'])
        evs = _events(r)
        assert any('error' in e for e in evs)

    def test_output_truncated(self, client, worktree, monkeypatch):
        monkeypatch.setattr(jarvis_server, '_WS_RUN_MAX_BYTES', 64)
        sid = _bind(client, worktree)
        r = _run(client, sid,
                 ['python3', '-c', 'print("x" * 5000)'])
        evs = _events(r)
        assert any(e.get('truncated') for e in evs)

    def test_refused_while_agent_turn_runs(self, client, worktree):
        sid = _bind(client, worktree)

        async def _hold():
            lock = jarvis_server.locks[sid]
            await lock.acquire()
            return lock

        lock = asyncio.run(_hold())
        try:
            r = _run(client, sid, ['python3', '-c', 'print(1)'])
            assert r.status_code == 409
        finally:
            lock.release()
