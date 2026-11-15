"""IDE link routes: /workspace/open-ide launches the configured IDE command
on the server and /workspace/changes reports a token that moves when files in
the worktree change on disk (e.g. edits made in the IDE)."""
import asyncio
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import jarvis_server  # noqa: E402
from jarvis_server import app  # noqa: E402

H = {'authorization': 'Bearer test-token'}


@pytest.fixture(scope='module')
def client():
    # Module-scoped: JARVIS_MAX_SESSIONS caps total sessions per run, so the
    # whole file shares one TestClient and one session id.
    return TestClient(app)


@pytest.fixture(scope='module')
def sid(client):
    return client.post('/session', headers=H).json()['session_id']


@pytest.fixture
def worktree(tmp_path):
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    (tmp_path / 'app.py').write_text('x = 1\n')
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'add', '-A'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'commit', '-q', '-m', 'init'], cwd=tmp_path, check=True)
    return tmp_path


def _set(sid, delta):
    asyncio.run(jarvis_server.set_state(sid, delta))


def _sid(client):
    return client.post('/session', headers=H).json()['session_id']


def _bind(sid, worktree):
    _set(sid, {'worktree': str(worktree)})
    return sid


class TestOpenIde:
    def test_forbidden_without_env(self, client, sid, worktree, monkeypatch):
        monkeypatch.delenv('JARVIS_IDE_COMMAND', raising=False)
        _bind(sid, worktree)
        r = client.post('/workspace/open-ide',
                        json={'session_id': sid}, headers=H)
        assert r.status_code == 403

    def test_forbidden_for_unknown_command(self, client, sid, worktree, monkeypatch):
        monkeypatch.setenv('JARVIS_IDE_COMMAND', 'vim')
        _bind(sid, worktree)
        r = client.post('/workspace/open-ide',
                        json={'session_id': sid}, headers=H)
        assert r.status_code == 403

    def test_popen_gets_worktree_path(self, client, sid, worktree, monkeypatch):
        monkeypatch.setenv('JARVIS_IDE_COMMAND', 'code')
        calls = []

        class FakePopen:
            def __init__(self, argv, **kwargs):
                calls.append((argv, kwargs))

        monkeypatch.setattr(subprocess, 'Popen', FakePopen)
        _bind(sid, worktree)
        r = client.post('/workspace/open-ide',
                        json={'session_id': sid}, headers=H)
        assert r.status_code == 200 and r.json()['ok'] is True
        assert calls, 'Popen was not called'
        argv, kwargs = calls[0]
        assert argv[0] == 'code'
        assert Path(argv[1]) == worktree.resolve() or argv[1] == str(worktree)
        assert kwargs.get('stdin') is subprocess.DEVNULL

    def test_requires_worktree(self, client, monkeypatch):
        monkeypatch.setenv('JARVIS_IDE_COMMAND', 'code')
        fresh = _sid(client)   # a session with no worktree bound
        r = client.post('/workspace/open-ide',
                        json={'session_id': fresh}, headers=H)
        assert r.status_code == 409


class TestWorkspaceChanges:
    def _changes(self, client, sid):
        return client.get('/workspace/changes',
                          params={'session_id': sid}, headers=H)

    def test_token_stable_then_changes_then_reverts(self, client, sid, worktree):
        _bind(sid, worktree)
        r1 = self._changes(client, sid)
        assert r1.status_code == 200
        t1 = r1.json()['token']
        r2 = self._changes(client, sid)
        assert r2.json()['token'] == t1

        # Simulate an IDE edit on disk.
        (worktree / 'app.py').write_text('x = 2\n')
        r3 = self._changes(client, sid)
        assert r3.status_code == 200
        data = r3.json()
        assert data['token'] != t1
        assert 'app.py' in data['files']

        # Reverting to a clean tree restores the original (empty) token.
        subprocess.run(['git', 'checkout', '--', 'app.py'], cwd=worktree,
                       check=True)
        r4 = self._changes(client, sid)
        assert r4.json()['token'] == t1

    def test_requires_worktree(self, client):
        fresh = _sid(client)
        r = self._changes(client, fresh)
        assert r.status_code == 409
