"""Live diagnostics: /workspace/diagnostics runs pyright on a single worktree
file and returns {line, severity, message} items for the VR line markers."""
import asyncio
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import jarvis_server  # noqa: E402
from ai_agents.tools.exec_tools import _pyright_argv  # noqa: E402
from jarvis_server import app  # noqa: E402

H = {'authorization': 'Bearer test-token'}
needs_pyright = pytest.mark.skipif(_pyright_argv() is None,
                                   reason='pyright is not installed')


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
    (tmp_path / 'good.py').write_text('x: int = 1\n')
    (tmp_path / 'bad.py').write_text('x: int = "no"\ny = x + 1\n')
    (tmp_path / 'notes.txt').write_text('plain text\n')
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'add', '-A'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'commit', '-q', '-m', 'init'], cwd=tmp_path, check=True)
    return tmp_path


def _sid(client):
    return client.post('/session', headers=H).json()['session_id']


def _bind(sid, worktree):
    asyncio.run(jarvis_server.set_state(sid, {'worktree': str(worktree)}))
    return sid


def _diag(client, sid, path):
    return client.get('/workspace/diagnostics',
                      params={'session_id': sid, 'path': path}, headers=H)


@needs_pyright
class TestDiagnostics:
    def test_type_error_line_reported(self, client, sid, worktree):
        _bind(sid, worktree)
        r = _diag(client, sid, 'bad.py')
        assert r.status_code == 200
        data = r.json()
        assert data['ok'] is True and data['supported'] is True
        assert data['items'], 'expected at least one diagnostic'
        item = data['items'][0]
        assert item['line'] == 1
        assert item['severity'] in ('error', 'warning')
        assert item['message']

    def test_clean_file_has_no_items(self, client, sid, worktree):
        _bind(sid, worktree)
        r = _diag(client, sid, 'good.py')
        assert r.status_code == 200
        data = r.json()
        assert data['supported'] is True
        assert all(i['severity'] != 'error' for i in data['items'])


class TestDiagnosticsGuards:
    def test_path_escape_rejected(self, client, sid, worktree):
        _bind(sid, worktree)
        for path in ('../outside.py', 'sub/../../outside.py'):
            r = _diag(client, sid, path)
            assert r.status_code == 400, path

    def test_missing_file_rejected(self, client, sid, worktree):
        _bind(sid, worktree)
        r = _diag(client, sid, 'nope.py')
        assert r.status_code == 400

    def test_non_python_unsupported(self, client, sid, worktree):
        _bind(sid, worktree)
        r = _diag(client, sid, 'notes.txt')
        assert r.status_code == 200
        data = r.json()
        assert data['supported'] is False and data['items'] == []

    def test_requires_worktree(self, client):
        fresh = _sid(client)
        r = _diag(client, fresh, 'x.py')
        assert r.status_code == 409
