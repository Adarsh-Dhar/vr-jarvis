"""Workspace edit routes: /workspace/open, file GET/PUT, line edit, revert,
diff and status. Writes go to a sandbox worktree only, are conflict-checked
with base_hash, deduplicated by request_id and refused while an agent turn
holds the session lock.
"""
import asyncio
import hashlib
import subprocess
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
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    (tmp_path / 'app.py').write_text('def main():\n    return 1\n')
    (tmp_path / 'crlf.txt').write_bytes(b'one\r\ntwo\r\nthree\r\n')
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'add', '-A'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'commit', '-q', '-m', 'init'], cwd=tmp_path, check=True)
    return tmp_path


def _sid(client):
    return client.post('/session', headers=H).json()['session_id']


def _set(sid, delta):
    asyncio.run(jarvis_server.set_state(sid, delta))


def _state(sid):
    async def _get():
        return (await jarvis_server.ensure(sid)).state
    return asyncio.run(_get())


def _bind(client, worktree):
    sid = _sid(client)
    _set(sid, {'worktree': str(worktree)})
    return sid


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _get_file(client, sid, path):
    return client.get('/workspace/file', params={'session_id': sid, 'path': path},
                      headers=H)


def _put(client, sid, path, content, base_hash='', request_id=None):
    return client.put('/workspace/file', headers=H, json={
        'session_id': sid, 'path': path, 'content': content,
        'base_hash': base_hash, 'request_id': request_id})


def _edit(client, sid, path, op, start, text='', end=None, base_hash='',
          request_id=None):
    return client.post('/workspace/edit', headers=H, json={
        'session_id': sid, 'path': path, 'op': op, 'start': start,
        'end': end, 'text': text, 'base_hash': base_hash,
        'request_id': request_id})


class TestWorkspaceOpen:
    def test_open_creates_worktree_without_leaking_path(self, client):
        sid = _sid(client)
        r = client.post('/workspace/open', json={'session_id': sid}, headers=H)
        assert r.status_code == 200
        data = r.json()
        assert data['ok'] is True
        assert data['worktree_name'].startswith('wt-')
        assert '/' not in data['worktree_name']
        assert data['branch'].startswith('jarvis/edit')
        # Second call reuses the existing worktree.
        r2 = client.post('/workspace/open', json={'session_id': sid}, headers=H).json()
        assert r2['worktree_name'] == data['worktree_name']


class TestWorkspaceFile:
    def test_get_prefers_worktree_and_reports_hash(self, client, worktree):
        sid = _bind(client, worktree)
        r = _get_file(client, sid, 'app.py')
        assert r.status_code == 200
        data = r.json()
        assert data['source'] == 'worktree'
        assert data['content'] == 'def main():\n    return 1\n'
        assert data['hash'] == _sha(data['content'])
        assert data['truncated'] is False

    def test_get_falls_back_to_main_checkout(self, client, worktree):
        sid = _sid(client)  # no worktree bound
        r = _get_file(client, sid, 'package.json')
        assert r.status_code == 200
        data = r.json()
        assert data['source'] == 'main'
        assert 'hash' in data and 'content' in data

    def test_get_rejects_escape(self, client, worktree):
        sid = _bind(client, worktree)
        r = _get_file(client, sid, '../outside.txt')
        assert r.status_code == 400

    def test_write_new_file_succeeds(self, client, worktree):
        sid = _bind(client, worktree)
        r = _put(client, sid, 'new.py', 'x = 1\n')
        assert r.status_code == 200
        data = r.json()
        assert data['ok'] is True
        assert data['hash'] == _sha('x = 1\n')
        assert (worktree / 'new.py').read_text() == 'x = 1\n'
        assert data['checked'] is True       # .py files get a compile() check
        assert data['verification'] == 'stale'
        assert 'symbols' in data

    def test_write_reports_python_syntax_errors(self, client, worktree):
        sid = _bind(client, worktree)
        r = _put(client, sid, 'bad.py', 'def broken(:\n')
        assert r.status_code == 200
        errs = r.json()['syntax_errors']
        assert errs and errs[0]['line'] == 1

    def test_overwrite_with_correct_hash(self, client, worktree):
        sid = _bind(client, worktree)
        cur = _get_file(client, sid, 'app.py').json()
        r = _put(client, sid, 'app.py', 'def main():\n    return 2\n',
                 base_hash=cur['hash'])
        assert r.status_code == 200 and r.json()['ok'] is True
        assert (worktree / 'app.py').read_text() == 'def main():\n    return 2\n'

    def test_stale_base_hash_conflicts_and_writes_nothing(self, client, worktree):
        sid = _bind(client, worktree)
        before = (worktree / 'app.py').read_text()
        r = _put(client, sid, 'app.py', 'hacked\n', base_hash='deadbeef')
        assert r.status_code == 409
        data = r.json()
        assert data['conflict'] is True
        assert data['current_hash'] == _sha(before)
        assert data['current_content'] == before
        assert (worktree / 'app.py').read_text() == before

    def test_rejected_paths(self, client, worktree):
        sid = _bind(client, worktree)
        for path in ('../escape.py', '.git/config', 'node_modules/pkg/index.js'):
            r = _put(client, sid, path, 'x\n')
            assert r.status_code == 400, path
        assert not (worktree.parent / 'escape.py').exists()

    def test_oversize_write_rejected(self, client, worktree, monkeypatch):
        monkeypatch.setattr(jarvis_server.config, 'MAX_EDIT_BYTES', 16)
        sid = _bind(client, worktree)
        r = _put(client, sid, 'big.py', 'x' * 100)
        assert r.status_code == 413

    def test_duplicate_request_id_applies_once(self, client, worktree):
        sid = _bind(client, worktree)
        body_hash = _sha('first\n')
        r1 = _put(client, sid, 'dup.py', 'first\n', request_id='req-1')
        assert r1.status_code == 200 and r1.json()['ok'] is True
        # Retry with the same request_id but different content must not apply.
        r2 = _put(client, sid, 'dup.py', 'second\n', base_hash=body_hash,
                  request_id='req-1')
        assert r2.status_code == 200
        assert r2.json().get('duplicate') is True
        assert (worktree / 'dup.py').read_text() == 'first\n'

    def test_edit_refused_while_agent_turn_runs(self, client, worktree):
        sid = _bind(client, worktree)

        async def _hold():
            lock = jarvis_server.locks[sid]
            await lock.acquire()
            return lock

        lock = asyncio.run(_hold())
        try:
            r = _put(client, sid, 'app.py', 'x\n')
            assert r.status_code == 409
            assert 'agent turn' in r.json()['detail'].lower()
        finally:
            lock.release()


class TestWorkspaceLineEdit:
    def _edit_ok(self, client, sid, worktree, path, op, start, text='', end=None):
        cur = _get_file(client, sid, path).json()
        return _edit(client, sid, path, op, start, text=text, end=end,
                     base_hash=cur['hash'])

    def test_replace_middle_line(self, client, worktree):
        sid = _bind(client, worktree)
        (worktree / 'f.txt').write_text('a\nb\nc\n')
        r = self._edit_ok(client, sid, worktree, 'f.txt', 'replace', 2, 'B\n')
        assert r.status_code == 200
        assert (worktree / 'f.txt').read_text() == 'a\nB\nc\n'
        assert r.json()['lines'] == 3

    def test_replace_first_and_last_lines(self, client, worktree):
        sid = _bind(client, worktree)
        (worktree / 'f.txt').write_text('a\nb\nc\n')
        r = self._edit_ok(client, sid, worktree, 'f.txt', 'replace', 1,
                          'A\nB\n', end=3)
        assert r.status_code == 200
        assert (worktree / 'f.txt').read_text() == 'A\nB\n'

    def test_insert_after(self, client, worktree):
        sid = _bind(client, worktree)
        (worktree / 'f.txt').write_text('a\nc\n')
        r = self._edit_ok(client, sid, worktree, 'f.txt', 'insert_after', 1,
                          'b\n')
        assert r.status_code == 200
        assert (worktree / 'f.txt').read_text() == 'a\nb\nc\n'

    def test_delete_line(self, client, worktree):
        sid = _bind(client, worktree)
        (worktree / 'f.txt').write_text('a\nb\nc\n')
        r = self._edit_ok(client, sid, worktree, 'f.txt', 'delete', 2, end=2)
        assert r.status_code == 200
        assert (worktree / 'f.txt').read_text() == 'a\nc\n'

    def test_out_of_range_rejected(self, client, worktree):
        sid = _bind(client, worktree)
        (worktree / 'f.txt').write_text('a\nb\n')
        cases = [
            ('delete', 0, None),    # start below 1
            ('delete', 4, None),    # start past end of 2-line file
            ('delete', 2, 3),       # end past last line
            ('delete', 2, 1),       # end before start
            ('delete', 1, 0),       # end below start
            ('replace', 1, 5),      # replace range past end
        ]
        for op, start, end in cases:
            r = self._edit_ok(client, sid, worktree, 'f.txt', op, start, end=end)
            assert r.status_code == 400, (op, start, end)
        assert (worktree / 'f.txt').read_text() == 'a\nb\n'

    def test_crlf_preserved(self, client, worktree):
        sid = _bind(client, worktree)
        r = self._edit_ok(client, sid, worktree, 'crlf.txt', 'replace', 2,
                          'TWO\r\n')
        assert r.status_code == 200
        data = (worktree / 'crlf.txt').read_bytes()
        assert data == b'one\r\nTWO\r\nthree\r\n'

    def test_edit_stale_hash_conflicts(self, client, worktree):
        sid = _bind(client, worktree)
        (worktree / 'f.txt').write_text('a\nb\n')
        r = _edit(client, sid, 'f.txt', 'delete', 1, end=1, base_hash='nope')
        assert r.status_code == 409
        assert (worktree / 'f.txt').read_text() == 'a\nb\n'


class TestWorkspaceRevert:
    def test_revert_restores_head_version(self, client, worktree):
        sid = _bind(client, worktree)
        _put(client, sid, 'app.py', 'def main():\n    return 99\n',
             base_hash=_sha('def main():\n    return 1\n'))
        assert 'return 99' in (worktree / 'app.py').read_text()
        r = client.post('/workspace/revert', headers=H,
                        json={'session_id': sid, 'path': 'app.py'})
        assert r.status_code == 200
        assert (worktree / 'app.py').read_text() == 'def main():\n    return 1\n'
        assert r.json()['hash'] == _sha('def main():\n    return 1\n')

    def test_revert_deletes_untracked_file(self, client, worktree):
        sid = _bind(client, worktree)
        _put(client, sid, 'untracked.py', 'x = 1\n')
        r = client.post('/workspace/revert', headers=H,
                        json={'session_id': sid, 'path': 'untracked.py'})
        assert r.status_code == 200
        assert not (worktree / 'untracked.py').exists()
        assert r.json()['hash'] == ''

    def test_revert_requires_worktree(self, client):
        sid = _sid(client)
        r = client.post('/workspace/revert', headers=H,
                        json={'session_id': sid, 'path': 'app.py'})
        assert r.status_code == 409


class TestWorkspaceDiffAndStatus:
    def test_diff_and_status_reflect_edits(self, client, worktree):
        sid = _bind(client, worktree)
        _put(client, sid, 'app.py', 'def main():\n    return 2\n',
             base_hash=_sha('def main():\n    return 1\n'))
        d = client.get('/workspace/diff',
                       params={'session_id': sid}, headers=H).json()
        assert d['ok'] is True and d['worktree'] is True
        assert 'app.py' in d['files']
        assert 'return 2' in d['diff']
        assert d['diff_hash']
        s = client.get('/workspace/status',
                       params={'session_id': sid}, headers=H).json()
        assert s['dirty'] is True
        assert s['files'] == ['app.py'] or 'app.py' in s['files']
        assert s['diff_hash'] == d['diff_hash']
        assert s['verification'] == {'tests': 'missing', 'typecheck': 'missing',
                                     'review': 'missing', 'security': 'missing'}

    def test_status_without_worktree(self, client):
        sid = _sid(client)
        s = client.get('/workspace/status',
                       params={'session_id': sid}, headers=H).json()
        assert s['worktree'] is False and s['dirty'] is False
