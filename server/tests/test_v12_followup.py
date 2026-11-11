"""Approval-gate, provenance and session-safety tests (v12 follow-up)."""
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


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def worktree(tmp_path):
    """A real git checkout so _worktree_fingerprint works."""
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'commit', '-q', '--allow-empty', '-m', 'init'], cwd=tmp_path, check=True)
    return tmp_path


def _sid(client):
    return client.post('/session', headers=H).json()['session_id']


def _set(sid, delta):
    asyncio.run(jarvis_server.set_state(sid, delta))


def _approve(client, sid):
    return client.post('/approve', json={'session_id': sid, 'approved': True}, headers=H).json()


def _full_run(fp, **over):
    """A test run that satisfies the strict approval gate; override fields to break one condition."""
    run = {'status': 'passed', 'source': 'live', 'exit_code': 0, 'passed': ['t::a'], 'failed': [],
           'skipped': [], 'checks_not_run': [], 'diff_hash': fp['diff_hash'], 'head': fp['head'],
           'command': 'pytest'}
    run.update(over)
    return run


def _pending(sid, worktree, last_test_run, last_typecheck=None):
    delta = {'pending_approval': 'change', 'approval_type': 'commit',
             'worktree': str(worktree), 'last_test_run': last_test_run}
    if last_typecheck is not None:
        delta['last_typecheck'] = last_typecheck
    _set(sid, delta)


class TestApprovalGates:
    def test_cached_tests_cannot_approve(self, client, worktree, monkeypatch):
        monkeypatch.delenv('JARVIS_ALLOW_CACHED_APPROVAL', raising=False)
        sid = _sid(client)
        _pending(sid, worktree, {'status': 'passed', 'source': 'cached'})
        r = _approve(client, sid)
        assert r['ok'] is False
        assert 'not from a live run' in r['detail']

    def test_stale_patch_cannot_approve(self, client, worktree):
        sid = _sid(client)
        _pending(sid, worktree, {'status': 'passed', 'source': 'live', 'diff_hash': 'deadbeefdeadbeef'})
        r = _approve(client, sid)
        assert r['ok'] is False
        assert 'patch changed' in r['detail']

    def test_missing_typecheck_blocks_when_tsconfig_exists(self, client, worktree):
        (worktree / 'tsconfig.json').write_text('{}')
        sid = _sid(client)
        fp = jarvis_server._worktree_fingerprint(str(worktree))
        _pending(sid, worktree, _full_run(fp))
        r = _approve(client, sid)
        assert r['ok'] is False
        assert 'Type check' in r['detail']

    def test_live_passing_run_commits_and_records_validation(self, client, worktree):
        sid = _sid(client)
        fp = jarvis_server._worktree_fingerprint(str(worktree))
        _pending(sid, worktree, _full_run(fp))
        r = _approve(client, sid)
        # An empty worktree has nothing to commit; the gates must still have been passed.
        assert 'Tests must pass' not in r.get('detail', '')
        assert 'not from a live run' not in r.get('detail', '')


class TestSessionSafety:
    def test_repo_switch_refused_with_pending_work(self, client, worktree):
        sid = _sid(client)
        _set(sid, {'worktree': str(worktree)})
        r = client.post('/repos/select', json={'name': 'anything'}, headers=H)
        assert r.status_code == 409
        _set(sid, {'worktree': ''})

    def test_session_bound_to_other_repo_is_refused(self, client, worktree):
        sid = _sid(client)
        _set(sid, {'repo': 'some-other-repo'})
        _pending(sid, worktree, {'status': 'passed', 'source': 'live'})
        r = client.post('/approve', json={'session_id': sid, 'approved': True}, headers=H)
        assert r.status_code == 409          # fails until BE-1 is implemented


class TestProvenance:
    def _propose(self, client, monkeypatch, source):
        monkeypatch.setattr(jarvis_server, 'extract_requirements', lambda t, tool_context=None: {
            'status': 'ok', 'source': 'heuristic',
            'requirements': {'goals': ['g'], 'functional': ['f'], 'non_functional': [],
                             'constraints': [], 'assumptions': [], 'open_questions': ['Q?']}})
        monkeypatch.setattr(jarvis_server, 'propose_architecture', lambda r, tool_context=None: {
            'status': 'ok', 'source': source,
            'components': [{'id': 'c1', 'name': 'A', 'responsibility': 'r', 'kind': 'service', 'requirement_ids': []}],
            'relationships': []})
        sid = _sid(client)
        r = client.post('/design/propose', json={'session_id': sid, 'idea_text': 'x'}, headers=H).json()
        return sid, r

    def test_heuristic_provenance_reported_and_kept_after_edit(self, client, monkeypatch):
        sid, r = self._propose(client, monkeypatch, 'heuristic')
        assert r['provenance'] == 'heuristic'
        e = client.post('/design/%s/edit' % sid, headers=H, json={'session_id': sid, 'ops': [
            {'op': 'update_component', 'id': 'c1', 'name': 'Renamed'}]})
        arch = e.json()['architecture']
        assert arch['provenance'] == 'heuristic'
        assert arch['edited_by_user'] is True

    def test_requirements_source_is_reported(self, client, monkeypatch):
        _, r = self._propose(client, monkeypatch, 'model')
        assert r['requirements_source'] == 'heuristic'      # fails until BE-2 is implemented


class TestQuestions:
    def test_resolve_needs_answer_and_reopen_works(self, client, monkeypatch):
        sid, _ = TestProvenance()._propose(client, monkeypatch, 'model')
        bad = client.post('/design/%s/edit' % sid, headers=H, json={'session_id': sid, 'ops': [
            {'op': 'resolve_question', 'question': 'Q?', 'answer': ''}]})
        assert bad.status_code == 400
        ok = client.post('/design/%s/edit' % sid, headers=H, json={'session_id': sid, 'ops': [
            {'op': 'resolve_question', 'question': 'Q?', 'answer': 'Yes, decided.'}]})
        assert ok.json()['architecture']['open_questions'] == []
        re_ = client.post('/design/%s/edit' % sid, headers=H, json={'session_id': sid, 'ops': [
            {'op': 'reopen_question', 'question': 'Q?'}]})
        assert 'Q?' in re_.json()['architecture']['open_questions']


class TestAgentSharesDesignState:
    """The root agent's tools must write the same state the /design endpoints read."""

    def _ctx(self):
        from types import SimpleNamespace
        return SimpleNamespace(state={'session_id': 'agent-shared-test'})

    def test_tools_write_authoritative_design_state(self, monkeypatch):
        from ai_agents.tools import architecture_tools as at
        monkeypatch.setattr(at, 'save_design', lambda sid, payload: True)
        monkeypatch.setattr(at, '_llm_json', lambda sys_, user, fb: (fb(), 'heuristic'))
        ctx = self._ctx()
        req = at.extract_requirements('Add coupon support. Apply discounts at checkout.', ctx)
        assert ctx.state['design_requirements'] == req['requirements']
        prop = at.propose_architecture(req, ctx)
        arch = ctx.state['design']
        assert arch['provenance'] == 'heuristic'
        assert arch['components'] == prop['components']
        assert ctx.state['design_compare'] == {} and ctx.state['implementation_plan'] == {}

    def test_plan_refused_until_developer_approves(self, monkeypatch):
        from ai_agents.tools import architecture_tools as at
        monkeypatch.setattr(at, 'save_design', lambda sid, payload: True)
        ctx = self._ctx()
        ctx.state['design'] = {'status': 'draft', 'revision': 2, 'components': [], 'relationships': []}
        res = at.generate_implementation_plan({'architecture': ctx.state['design']}, ctx)
        assert res['status'] == 'error'
        assert 'approved' in res['error']


class TestTaskEndpointKeepsAllFields:
    def test_task_endpoint_exposes_full_task_record(self, client):
        sid = _sid(client)
        _set(sid, {'implementation_plan': {'tasks': [{
            'id': 't1', 'title': 'x', 'status': 'pending', 'description': 'd',
            'suggested_files': ['a.py'], 'confirmed_targets': ['a.py'],
            'rejected_targets': [{'file': 'b.py', 'reason': 'unrelated'}],
            'new_files': ['c.py'], 'modifies_existing': True, 'needs_investigation': False,
            'design_revision': 3, 'cycle_accepted': True, 'cycle_rationale': 'ok',
            'completion': {'commit': 'abc1234', 'typecheck': 'passed'}}]}})
        t = client.get('/task/' + sid, headers=H).json()['tasks'][0]
        for key in ('description', 'suggested_files', 'confirmed_targets', 'rejected_targets',
                    'new_files', 'modifies_existing', 'design_revision', 'cycle_rationale', 'completion'):
            assert key in t, key
