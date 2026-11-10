"""
Lifecycle tests for the /design and /plan endpoints.

Covers the audit findings: open-question resolution, design-state
invalidation (cleared plan/compare must not resurrect from disk),
approval gating, task dependency enforcement, and circular dependency
reporting in generate_implementation_plan.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import jarvis_server  # noqa: E402
from jarvis_server import app  # noqa: E402

H = {'authorization': 'Bearer test-token'}


@pytest.fixture(autouse=True)
def stub_design_llm(monkeypatch):
    """Deterministic requirements/architecture so tests never call a model."""
    monkeypatch.setattr(jarvis_server, 'extract_requirements', lambda text, tool_context=None: {
        'status': 'ok',
        'requirements': {
            'goals': ['g'], 'functional': ['f1', 'f2'], 'non_functional': [],
            'constraints': [], 'assumptions': [],
            'open_questions': ['Q one?', 'Q two?'],
        }})
    monkeypatch.setattr(jarvis_server, 'propose_architecture', lambda req, tool_context=None: {
        'status': 'ok',
        'components': [
            {'id': 'c1', 'name': 'A', 'responsibility': 'ra', 'kind': 'service', 'requirement_ids': []},
            {'id': 'c2', 'name': 'B', 'responsibility': 'rb', 'kind': 'service', 'requirement_ids': []},
        ],
        'relationships': [
            {'id': 'e1', 'src': 'c1', 'dst': 'c2', 'kind': 'calls', 'label': ''},
        ]})


@pytest.fixture
def client():
    return TestClient(app)


def _session(client):
    r = client.post('/session', headers=H)
    assert r.status_code == 200
    return r.json()['session_id']


def _propose(client, sid):
    r = client.post('/design/propose', json={'session_id': sid, 'idea_text': 'an idea'}, headers=H)
    assert r.status_code == 200
    return r.json()


def _edit(client, sid, ops):
    return client.post('/design/%s/edit' % sid, json={'session_id': sid, 'ops': ops}, headers=H)


def _approve(client, sid):
    return client.post('/design/%s/approve' % sid,
                       json={'session_id': sid, 'approved': True, 'approved_by': 'test'}, headers=H)


def _resolve_all_questions(client, sid):
    for q in ('Q one?', 'Q two?'):
        r = _edit(client, sid, [{'op': 'resolve_question', 'question': q}])
        assert r.status_code == 200, r.text


class TestOpenQuestions:
    def test_propose_carries_open_questions(self, client):
        sid = _session(client)
        body = _propose(client, sid)
        assert body['architecture']['status'] == 'draft'
        assert body['architecture']['open_questions'] == ['Q one?', 'Q two?']

    def test_approve_blocked_by_open_questions(self, client):
        sid = _session(client)
        _propose(client, sid)
        r = _approve(client, sid)
        assert r.status_code == 409

    def test_resolve_question_unblocks_approval(self, client):
        sid = _session(client)
        _propose(client, sid)
        _resolve_all_questions(client, sid)
        r = _approve(client, sid)
        assert r.status_code == 200
        assert r.json()['architecture']['status'] == 'approved'

    def test_resolve_syncs_requirements(self, client):
        sid = _session(client)
        _propose(client, sid)
        _resolve_all_questions(client, sid)
        view = client.get('/design/' + sid, headers=H).json()
        assert view['requirements']['open_questions'] == []
        assert view['architecture']['open_questions'] == []

    def test_update_question(self, client):
        sid = _session(client)
        _propose(client, sid)
        r = _edit(client, sid, [{'op': 'update_question', 'question': 'Q one?',
                                 'new_question': 'Q one resolved?'}])
        assert r.status_code == 200
        qs = r.json()['architecture']['open_questions']
        assert qs == ['Q one resolved?', 'Q two?']

    def test_resolve_unknown_question_fails(self, client):
        sid = _session(client)
        _propose(client, sid)
        r = _edit(client, sid, [{'op': 'resolve_question', 'question': 'no such question'}])
        assert r.status_code == 400

    def test_add_question(self, client):
        sid = _session(client)
        _propose(client, sid)
        _resolve_all_questions(client, sid)
        r = _edit(client, sid, [{'op': 'add_question', 'question': 'Q three?'}])
        assert r.status_code == 200
        assert r.json()['architecture']['open_questions'] == ['Q three?']
        assert _approve(client, sid).status_code == 409


class TestPlanLifecycle:
    def _approved_with_plan(self, client):
        sid = _session(client)
        _propose(client, sid)
        _resolve_all_questions(client, sid)
        assert _approve(client, sid).status_code == 200
        r = client.post('/plan/generate', json={'session_id': sid}, headers=H)
        assert r.status_code == 200
        return sid, r.json()

    def test_plan_requires_approved_architecture(self, client):
        sid = _session(client)
        _propose(client, sid)
        r = client.post('/plan/generate', json={'session_id': sid}, headers=H)
        assert r.status_code == 409

    def test_plan_generate_orders_dependencies(self, client):
        sid, plan = self._approved_with_plan(client)
        tasks = {t['id']: t for t in plan['tasks']}
        # c1 calls c2 -> c2's task must come first
        assert tasks['t1']['component_id'] == 'c2'
        assert tasks['t2']['component_id'] == 'c1'
        assert tasks['t2']['depends_on'] == ['t1']

    def test_edit_clears_plan_without_stale_restore(self, client):
        """Regression: a cleared implementation_plan must not resurrect from disk."""
        sid, plan = self._approved_with_plan(client)
        assert plan['tasks']
        r = _edit(client, sid, [{'op': 'add_component', 'name': 'C', 'component_kind': 'service'}])
        assert r.status_code == 200
        view = client.get('/design/' + sid, headers=H).json()
        assert not view['plan'] or not view['plan'].get('tasks'), \
            'stale plan resurrected from disk: %r' % (view['plan'],)
        # and it stays cleared on a second read
        view2 = client.get('/design/' + sid, headers=H).json()
        assert not view2['plan'] or not view2['plan'].get('tasks')

    def test_task_status_dependency_enforced(self, client):
        sid, plan = self._approved_with_plan(client)
        # t2 depends on t1: cannot start t2 first
        r = client.patch('/plan/%s/tasks/t2' % sid, json={'status': 'running'}, headers=H)
        assert r.status_code == 409
        assert client.patch('/plan/%s/tasks/t1' % sid, json={'status': 'running'}, headers=H).status_code == 200
        assert client.patch('/plan/%s/tasks/t1' % sid, json={'status': 'done'}, headers=H).status_code == 200
        assert client.patch('/plan/%s/tasks/t2' % sid, json={'status': 'running'}, headers=H).status_code == 200

    def test_circular_dependencies_reported(self, client):
        sid = _session(client)
        _propose(client, sid)
        _resolve_all_questions(client, sid)
        # create a cycle: c2 -> c1 in addition to c1 -> c2
        r = _edit(client, sid, [{'op': 'add_relationship', 'src': 'c2', 'dst': 'c1',
                                 'kind': 'calls', 'id': 'e2'}])
        assert r.status_code == 200
        assert _approve(client, sid).status_code == 200
        r = client.post('/plan/generate', json={'session_id': sid}, headers=H)
        assert r.status_code == 200
        plan = r.json()
        assert sorted(plan['circular']) == ['c1', 'c2']
        # the task graph itself must stay acyclic: no task depends on itself
        # or on a task that comes later in the list
        pos = {t['id']: i for i, t in enumerate(plan['tasks'])}
        for t in plan['tasks']:
            for d in t['depends_on']:
                assert d != t['id'] and pos[d] < pos[t['id']]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
