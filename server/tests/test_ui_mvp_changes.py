"""Tests for the UI-completion changes: design rejection, relationship labels,
and the server-side authoritative diff / validated-change identity in /ask responses."""

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import jarvis_server  # noqa: E402
from jarvis_server import app, _build_ask_response, _worktree_review  # noqa: E402
from ai_agents.tools.exec_tools import _worktree_fingerprint  # noqa: E402
from test_design_lifecycle import (  # noqa: E402,F401
    stub_design_llm, client, H, _session, _propose, _edit, _approve, _resolve_all_questions)


def _approved_with_plan(client):
    sid = _session(client)
    _propose(client, sid)
    _resolve_all_questions(client, sid)
    r = _approve(client, sid)
    assert r.status_code == 200, r.text
    assert r.json()['plan']['tasks'], 'approval must generate the plan'
    return sid


class TestDesignReject:
    def test_reject_returns_to_draft_and_clears_plan(self, client):
        sid = _approved_with_plan(client)
        r = client.post('/design/%s/approve' % sid,
                        json={'session_id': sid, 'approved': False}, headers=H)
        assert r.status_code == 200
        assert r.json()['architecture']['status'] == 'draft'
        assert r.json()['architecture']['approved_by'] == ''
        view = client.get('/design/' + sid, headers=H).json()
        assert not view['plan'] or not view['plan'].get('tasks'), 'rejected design left an approved plan behind'
        # and it does not resurrect from disk on a second read
        view2 = client.get('/design/' + sid, headers=H).json()
        assert not view2['plan'] or not view2['plan'].get('tasks')

    def test_plan_cannot_be_generated_after_reject(self, client):
        sid = _approved_with_plan(client)
        client.post('/design/%s/approve' % sid, json={'session_id': sid, 'approved': False}, headers=H)
        r = client.post('/plan/generate', json={'session_id': sid}, headers=H)
        assert r.status_code == 409


class TestRelationshipLabel:
    def test_label_edit_persists_and_invalidates_plan(self, client):
        sid = _approved_with_plan(client)
        r = _edit(client, sid, [{'op': 'update_relationship', 'id': 'e1', 'label': 'sends orders'}])
        assert r.status_code == 200, r.text
        rels = {x['id']: x for x in r.json()['architecture']['relationships']}
        assert rels['e1']['label'] == 'sends orders'
        assert rels['e1']['kind'] == 'calls', 'label edit must not change the kind'
        view = client.get('/design/' + sid, headers=H).json()
        assert not view['plan'] or not view['plan'].get('tasks'), 'editing the design must invalidate the plan'

    def test_unknown_relationship_is_rejected(self, client):
        sid = _session(client)
        _propose(client, sid)
        r = _edit(client, sid, [{'op': 'update_relationship', 'id': 'nope', 'label': 'x'}])
        assert r.status_code == 400


def _git(d, *a):
    return subprocess.run(['git', *a], cwd=d, capture_output=True, text=True)


@pytest.fixture
def worktree(tmp_path):
    d = str(tmp_path)
    _git(d, 'init', '-q')
    _git(d, 'config', 'user.email', 't@t')
    _git(d, 'config', 'user.name', 't')
    (tmp_path / 'a.py').write_text('x = 1\n' * 2000)
    _git(d, 'add', '.')
    _git(d, 'commit', '-qm', 'init')
    (tmp_path / 'a.py').write_text('x = 2\n' * 2000)       # large change
    (tmp_path / 'new.py').write_text('print(1)\n')          # new file
    return d


@pytest.fixture(autouse=True)
def empty_graph(monkeypatch):
    """_build_ask_response resolves evidence against the graph index; these tests need none."""
    import ai_agents.tools.graph_tools as gt
    monkeypatch.setattr(gt, '_graph', lambda: {'nodes': {}, 'edges': []})


class TestAuthoritativeDiff:
    def test_review_reports_full_diff_files_and_fingerprint(self, worktree):
        r = _worktree_review({'worktree': worktree})
        assert set(r['files']) == {'a.py', 'new.py'}
        assert r['additions'] == 2001 and r['deletions'] == 2000
        assert len(r['diff']) > 5000, 'must not be cut at the old 5000-char limit'
        assert r['diff_hash'] == _worktree_fingerprint(worktree)['diff_hash']

    def test_no_worktree_gives_empty(self):
        assert _worktree_review({}) == {}
        assert _worktree_review({'worktree': '/definitely/not/here'}) == {}

    def test_ask_response_replaces_model_copied_diff_with_real_one(self, worktree):
        state = {
            'worktree': worktree, 'proposed_patch': {'x': 1}, 'active_task_id': 't7',
            'scene_commands': [{'type': 'highlight_path', 'node_ids': ['n1']},
                               {'type': 'show_ghost_diff', 'node_id': 'n1', 'diff': '--- truncated by the model'}],
            'last_test_run': {'status': 'passed', 'source': 'live',
                              'diff_hash': _worktree_fingerprint(worktree)['diff_hash']},
        }
        resp = _build_ask_response('ok', '', state)
        ghosts = [c for c in resp['scene_commands'] if c['type'] == 'show_ghost_diff']
        assert len(ghosts) == 1, 'exactly one ghost diff command'
        assert 'truncated by the model' not in ghosts[0]['diff']
        assert ghosts[0]['node_id'] == 'n1', 'keeps the node the model chose'
        assert any(c['type'] == 'highlight_path' for c in resp['scene_commands']), 'other commands are kept'
        v = resp['validated']
        assert v['task_id'] == 't7' and set(v['files']) == {'a.py', 'new.py'}
        assert v['diff_hash'] == resp['test_run']['diff_hash'], 'tests ran on exactly this diff'

    def test_changed_tree_after_tests_is_detectable(self, worktree):
        old_hash = _worktree_fingerprint(worktree)['diff_hash']
        Path(worktree, 'a.py').write_text('x = 3\n' * 2000)   # edit after the tests ran
        state = {'worktree': worktree, 'proposed_patch': {'x': 1},
                 'last_test_run': {'status': 'passed', 'source': 'live', 'diff_hash': old_hash}}
        resp = _build_ask_response('ok', '', state)
        assert resp['validated']['diff_hash'] != resp['test_run']['diff_hash']

    def test_response_without_worktree_is_unchanged(self):
        resp = _build_ask_response('hi', '', {})
        assert 'validated' not in resp
        assert resp['scene_commands'] == []
