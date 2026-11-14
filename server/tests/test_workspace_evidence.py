"""Evidence invalidation: every human workspace write must clear all four
verification keys (last_test_run, last_typecheck, code_review, security_scan)
so the /approve commit gate cannot accept stale evidence.
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
from ai_agents.tools.exec_tools import verification_blockers  # noqa: E402

H = {'authorization': 'Bearer test-token'}

EVIDENCE_KEYS = ('last_test_run', 'last_typecheck', 'code_review',
                 'security_scan')


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def worktree(tmp_path):
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    (tmp_path / 'app.py').write_text('x = 1\n')
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


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _bind(client, worktree):
    sid = _sid(client)
    _set(sid, {'worktree': str(worktree)})
    return sid


def _fake_fresh_evidence(worktree):
    """Evidence records that would satisfy the gate for the CURRENT diff."""
    fp = jarvis_server._worktree_fingerprint(str(worktree))
    return {
        'last_test_run': {'status': 'passed', 'source': 'live', 'exit_code': 0,
                          'passed': ['t::a'], 'failed': [], 'skipped': [],
                          'checks_not_run': [], 'command': 'pytest',
                          'diff_hash': fp['diff_hash'], 'head': fp['head']},
        'last_typecheck': {'typecheck': 'passed', 'source': 'live',
                           'command': 'ast', 'exit_code': 0,
                           'diff_hash': fp['diff_hash'], 'head': fp['head']},
        'code_review': {'verdict': 'approve', 'findings': [], 'acceptance': []},
        'security_scan': {'status': 'completed', 'scanner': 'test',
                          'findings': [], 'diff_hash': fp['diff_hash']},
    }


class TestEvidenceClearedOnWrite:
    def test_put_clears_all_four_keys(self, client, worktree):
        sid = _bind(client, worktree)
        _set(sid, _fake_fresh_evidence(worktree))
        r = client.put('/workspace/file', headers=H, json={
            'session_id': sid, 'path': 'app.py', 'content': 'x = 2\n',
            'base_hash': _sha('x = 1\n')})
        assert r.status_code == 200 and r.json()['ok'] is True
        state = _state(sid)
        for key in EVIDENCE_KEYS:
            assert not state.get(key), key
        blockers = verification_blockers(state, str(worktree))
        assert blockers  # nothing recorded -> gate must refuse

    def test_line_edit_clears_all_four_keys(self, client, worktree):
        sid = _bind(client, worktree)
        _set(sid, _fake_fresh_evidence(worktree))
        cur = client.get('/workspace/file',
                         params={'session_id': sid, 'path': 'app.py'},
                         headers=H).json()
        r = client.post('/workspace/edit', headers=H, json={
            'session_id': sid, 'path': 'app.py', 'op': 'replace', 'start': 1,
            'text': 'y = 2\n', 'base_hash': cur['hash']})
        assert r.status_code == 200 and r.json()['ok'] is True
        state = _state(sid)
        for key in EVIDENCE_KEYS:
            assert not state.get(key), key

    def test_second_edit_keeps_evidence_cleared(self, client, worktree):
        """Editing again after fresh evidence exists must stale it again."""
        sid = _bind(client, worktree)
        # First edit.
        client.put('/workspace/file', headers=H, json={
            'session_id': sid, 'path': 'app.py', 'content': 'x = 2\n',
            'base_hash': _sha('x = 1\n')})
        # Pretend verification ran on the new diff.
        _set(sid, _fake_fresh_evidence(worktree))
        state = _state(sid)
        assert state.get('last_test_run', {}).get('status') == 'passed'
        # Second edit invalidates it.
        cur = client.get('/workspace/file',
                         params={'session_id': sid, 'path': 'app.py'},
                         headers=H).json()
        r = client.put('/workspace/file', headers=H, json={
            'session_id': sid, 'path': 'app.py', 'content': 'x = 3\n',
            'base_hash': cur['hash']})
        assert r.status_code == 200
        state = _state(sid)
        for key in EVIDENCE_KEYS:
            assert not state.get(key), key

    def test_status_reports_missing_verification(self, client, worktree):
        sid = _bind(client, worktree)
        client.put('/workspace/file', headers=H, json={
            'session_id': sid, 'path': 'app.py', 'content': 'x = 2\n',
            'base_hash': _sha('x = 1\n')})
        s = client.get('/workspace/status',
                       params={'session_id': sid}, headers=H).json()
        assert s['verification'] == {'tests': 'missing',
                                     'typecheck': 'missing',
                                     'review': 'missing',
                                     'security': 'missing'}

    def test_status_reports_stale_after_out_of_band_change(self, client,
                                                            worktree):
        """An IDE writing into the worktree directly shows up as a changed
        diff_hash, which makes recorded evidence stale on next poll."""
        sid = _bind(client, worktree)
        client.put('/workspace/file', headers=H, json={
            'session_id': sid, 'path': 'app.py', 'content': 'x = 2\n',
            'base_hash': _sha('x = 1\n')})
        _set(sid, _fake_fresh_evidence(worktree))
        # Simulate an IDE edit that bypasses the API.
        (worktree / 'app.py').write_text('x = 3\n')
        s = client.get('/workspace/status',
                       params={'session_id': sid}, headers=H).json()
        assert s['verification']['tests'] == 'stale'
        assert s['verification']['typecheck'] == 'stale'
        assert s['verification']['security'] == 'stale'
