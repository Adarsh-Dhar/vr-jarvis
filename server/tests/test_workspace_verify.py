"""Verification and submit routes for human workspace edits:
/workspace/verify runs the deterministic checks directly, /workspace/review
records or runs a review, and /workspace/submit moves a fully verified edit
into the pending_approval flow. All refuse while an agent turn holds the
session lock and in cached-tests mode.
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


def _verify(client, sid, **kw):
    body = {'session_id': sid}
    body.update(kw)
    return client.post('/workspace/verify', json=body, headers=H)


def _submit(client, sid):
    return client.post('/workspace/submit', json={'session_id': sid}, headers=H)


def _status(client, sid):
    return client.get('/workspace/status',
                      params={'session_id': sid}, headers=H).json()


def _fresh_evidence(worktree):
    """State delta that passes every verification_blockers check for `worktree`."""
    fp = jarvis_server._worktree_fingerprint(str(worktree))
    return {
        'last_test_run': {'status': 'passed', 'source': 'live', 'exit_code': 0,
                          'passed': ['tests.test_app::ok'], 'failed': [],
                          'skipped': [], 'checks_not_run': [],
                          'diff_hash': fp['diff_hash'], 'head': fp['head']},
        'last_typecheck': {'status': 'ok', 'typecheck': 'passed',
                           'source': 'live',
                           'diff_hash': fp['diff_hash'], 'head': fp['head']},
        'code_review': {'verdict': 'approve', 'findings': [], 'acceptance': []},
        'security_scan': {'status': 'completed',
                          'diff_hash': fp['diff_hash'], 'findings': []},
    }


class TestWorkspaceVerify:
    def test_verify_records_evidence_keys(self, client, worktree):
        sid = _bind(client, worktree)
        r = _verify(client, sid)
        assert r.status_code == 200
        data = r.json()
        assert data['ok'] is True
        assert 'verification' in data
        st = _state(sid)
        # run_tests reports 'unverified' on a tree with no test runner, but the
        # evidence key is still written; typecheck passes the AST check.
        assert st['last_test_run']
        assert st['last_typecheck'].get('typecheck') == 'passed'
        assert 'security_scan' in st
        assert data['verification']['typecheck'] == 'fresh'

    def test_verify_refused_in_cached_mode(self, client, worktree, monkeypatch):
        monkeypatch.setattr(jarvis_server, 'USE_CACHED_TESTS', True)
        sid = _bind(client, worktree)
        r = _verify(client, sid)
        assert r.status_code == 409
        assert 'cached' in r.json()['detail'].lower()

    def test_verify_refused_while_agent_turn_runs(self, client, worktree):
        sid = _bind(client, worktree)

        async def _hold():
            lock = jarvis_server.locks[sid]
            await lock.acquire()
            return lock

        lock = asyncio.run(_hold())
        try:
            r = _verify(client, sid)
            assert r.status_code == 409
            assert 'agent turn' in r.json()['detail'].lower()
        finally:
            lock.release()

    def test_verify_rejects_unknown_steps(self, client, worktree):
        sid = _bind(client, worktree)
        r = _verify(client, sid, steps=['bogus'])
        assert r.status_code == 400


class TestWorkspaceSubmit:
    def test_submit_blocked_until_all_evidence_fresh(self, client, worktree):
        sid = _bind(client, worktree)
        delta = _fresh_evidence(worktree)
        del delta['code_review']          # review is the missing piece
        _set(sid, delta)
        r = _submit(client, sid)
        assert r.status_code == 409
        assert any('review' in b.lower() for b in r.json()['blockers'])

    def test_submit_blocked_with_no_evidence(self, client, worktree):
        sid = _bind(client, worktree)
        r = _submit(client, sid)
        assert r.status_code == 409
        assert 'No test run' in ' '.join(r.json()['blockers'])

    def test_submit_sets_pending_approval(self, client, worktree):
        sid = _bind(client, worktree)
        _set(sid, _fresh_evidence(worktree))
        r = _submit(client, sid)
        assert r.status_code == 200
        data = r.json()
        assert data['ok'] is True
        assert data['pending_approval']
        assert data['review'].get('branch')
        st = _state(sid)
        assert st['pending_approval'] == data['pending_approval']
        assert st['approved'] is False
        assert st['approval_type'] == 'commit'

    def test_new_edit_makes_evidence_stale_and_blocks_submit(self, client, worktree):
        sid = _bind(client, worktree)
        _set(sid, _fresh_evidence(worktree))
        # A human line edit clears all four evidence keys server-side.
        cur = client.get('/workspace/file',
                         params={'session_id': sid, 'path': 'app.py'},
                         headers=H).json()
        r = client.post('/workspace/edit', headers=H, json={
            'session_id': sid, 'path': 'app.py', 'op': 'replace',
            'start': 2, 'end': 2, 'text': '    return 2',
            'base_hash': cur['hash']})
        assert r.status_code == 200
        ver = _status(client, sid)['verification']
        assert ver['tests'] == 'missing'
        assert ver['typecheck'] == 'missing'
        assert ver['review'] == 'missing'
        assert ver['security'] == 'missing'
        r = _submit(client, sid)
        assert r.status_code == 409

    def test_edit_after_verify_makes_results_stale(self, client, worktree):
        sid = _bind(client, worktree)
        # Fresh evidence, then verify re-runs and records live fingerprints.
        _set(sid, _fresh_evidence(worktree))
        r = _verify(client, sid, steps=['typecheck'])
        assert r.status_code == 200
        assert r.json()['verification']['typecheck'] == 'fresh'
        # Any further worktree write changes the diff hash -> stale again.
        cur = client.get('/workspace/file',
                         params={'session_id': sid, 'path': 'app.py'},
                         headers=H).json()
        client.post('/workspace/edit', headers=H, json={
            'session_id': sid, 'path': 'app.py', 'op': 'replace',
            'start': 1, 'end': 1, 'text': 'def main():  # touched',
            'base_hash': cur['hash']})
        ver = _status(client, sid)['verification']
        assert ver['typecheck'] == 'missing'   # edit cleared the key entirely
