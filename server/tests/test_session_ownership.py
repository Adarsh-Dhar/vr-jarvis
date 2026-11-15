"""Per-user ownership of saved sessions, designs and history, plus retention."""
import asyncio
import os
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('JARVIS_SESSION_BACKEND', 'memory')

import jarvis_server  # noqa: E402
from jarvis_server import app  # noqa: E402
from ai_agents.tools import architecture_tools as at  # noqa: E402

ALICE = {'authorization': 'Bearer test-token', 'x-jarvis-user': 'alice'}
BOB = {'authorization': 'Bearer test-token', 'x-jarvis-user': 'bob'}
DEFAULT = {'authorization': 'Bearer test-token'}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    # jarvis_server may already be imported with the sqlite backend (test
    # collection is alphabetical), so give each test a fresh in-memory session
    # service and drop this test's ids from the shared tracking tables —
    # session_last_used is capped at MAX_SESSIONS for the whole pytest process.
    from google.adk.sessions import InMemorySessionService
    monkeypatch.setattr(jarvis_server, 'sessions', InMemorySessionService())
    before = set(jarvis_server.session_last_used) | set(jarvis_server.session_owner)
    monkeypatch.setattr(at, 'DESIGN_DIR', tmp_path / 'design')
    monkeypatch.setattr(jarvis_server, 'extract_requirements', lambda text, tool_context=None: {
        'status': 'ok', 'requirements': {
            'goals': ['g'], 'functional': ['f1'], 'non_functional': [],
            'constraints': [], 'assumptions': [], 'open_questions': []}})
    monkeypatch.setattr(jarvis_server, 'propose_architecture', lambda req, tool_context=None: {
        'status': 'ok',
        'components': [{'id': 'c1', 'name': 'AliceSecret', 'responsibility': 'r',
                        'kind': 'service', 'requirement_ids': []},
                       {'id': 'c2', 'name': 'B', 'responsibility': 'r',
                        'kind': 'service', 'requirement_ids': []}],
        'relationships': [{'id': 'e1', 'src': 'c1', 'dst': 'c2', 'kind': 'calls', 'label': ''}]})
    yield
    new_sids = ((set(jarvis_server.session_last_used) | set(jarvis_server.session_owner))
                - before)
    for sid in new_sids:
        jarvis_server.session_last_used.pop(sid, None)
        jarvis_server.session_owner.pop(sid, None)
        jarvis_server.locks.pop(sid, None)


@pytest.fixture
def client():
    return TestClient(app)


def _new(client, headers):
    r = client.post('/session', headers=headers)
    assert r.status_code == 200
    return r.json()['session_id']


def _alice_with_design(client):
    sid = _new(client, ALICE)
    r = client.post('/design/propose', json={'session_id': sid, 'idea_text': 'x'}, headers=ALICE)
    assert r.status_code == 200, r.text
    return sid


def test_design_file_records_owner(client):
    sid = _alice_with_design(client)
    assert at.design_owner(sid) == 'alice'


def test_other_user_cannot_read_design(client):
    sid = _alice_with_design(client)
    r = client.get('/design/%s' % sid, headers=BOB)
    assert r.status_code == 404 and 'AliceSecret' not in r.text
    assert client.get('/design/%s' % sid, headers=ALICE).status_code == 200


def test_other_user_cannot_edit_compare_approve_or_plan(client):
    sid = _alice_with_design(client)
    calls = [
        client.post('/design/%s/edit' % sid, json={'session_id': sid, 'ops': []}, headers=BOB),
        client.post('/design/%s/compare' % sid, json={'session_id': sid}, headers=BOB),
        client.post('/design/%s/approve' % sid,
                    json={'session_id': sid, 'approved': True, 'approved_by': 'bob'}, headers=BOB),
        client.post('/plan/generate', json={'session_id': sid}, headers=BOB),
        client.get('/task/%s' % sid, headers=BOB),
    ]
    assert [c.status_code for c in calls] == [404] * len(calls)


def test_other_user_cannot_read_design_versions(client):
    sid = _alice_with_design(client)
    at.save_design(sid, {'architecture': {'revision': 2, 'components': []}})
    at.save_design(sid, {'architecture': {'revision': 3, 'components': []}})
    assert client.get('/design/%s/versions' % sid, headers=ALICE).status_code == 200
    assert client.get('/design/%s/versions' % sid, headers=BOB).status_code == 404
    assert client.get('/design/%s/versions/1' % sid, headers=BOB).status_code == 404


def test_owner_is_sticky_across_saves(client):
    sid = _alice_with_design(client)
    at.save_design(sid, {'architecture': {'revision': 9}})     # provider says default user
    assert at.design_owner(sid) == 'alice'


def test_legacy_ownerless_design_belongs_to_default_user(client):
    at.DESIGN_DIR.mkdir(parents=True, exist_ok=True)
    (at.DESIGN_DIR / 'legacy1.json').write_text('{"architecture": {"revision": 1}}')
    assert at.design_owner('legacy1') == ''
    assert client.get('/design/legacy1', headers=DEFAULT).status_code == 200
    assert client.get('/design/legacy1', headers=ALICE).status_code == 404


def test_session_lists_are_per_user(client):
    sa, sb = _new(client, ALICE), _new(client, BOB)
    la = [s['session_id'] for s in client.get('/sessions', headers=ALICE).json()['sessions']]
    lb = [s['session_id'] for s in client.get('/sessions', headers=BOB).json()['sessions']]
    assert sa in la and sb not in la
    assert sb in lb and sa not in lb


def test_cannot_resume_history_or_delete_foreign_session(client):
    sa = _alice_with_design(client)
    assert client.post('/session/%s/resume' % sa, headers=BOB).status_code == 404
    assert client.get('/session/%s/history' % sa, headers=BOB).status_code == 404
    assert client.delete('/session/%s' % sa, headers=BOB).status_code == 404
    assert at.design_owner(sa) == 'alice'                       # design file untouched
    assert client.get('/design/%s' % sa, headers=ALICE).status_code == 200


def test_delete_removes_design_file_and_history(client):
    sid = _alice_with_design(client)
    at.save_design(sid, {'architecture': {'revision': 2}})
    assert client.delete('/session/%s' % sid, headers=ALICE).status_code == 200
    assert at.design_owner(sid) is None
    assert at.list_design_versions(sid) == []


def test_retention_deletes_only_old_sessions_of_that_user(client, monkeypatch):
    monkeypatch.setattr(jarvis_server, 'SESSION_RETENTION_DAYS', 30.0)
    old, fresh = _alice_with_design(client), _new(client, ALICE)
    bob_old = _new(client, BOB)
    store = jarvis_server.sessions.sessions[jarvis_server.APP]
    store['alice'][old].last_update_time = time.time() - 40 * 86400
    store['bob'][bob_old].last_update_time = time.time() - 40 * 86400
    assert asyncio.run(jarvis_server._retention_sweep('alice')) == 1
    la = [s['session_id'] for s in client.get('/sessions', headers=ALICE).json()['sessions']]
    assert old not in la and fresh in la
    assert at.design_owner(old) is None                          # design data reaped too
    assert bob_old in store['bob']                               # other user's session untouched


def test_retention_keeps_sessions_with_live_work(client, monkeypatch):
    monkeypatch.setattr(jarvis_server, 'SESSION_RETENTION_DAYS', 30.0)
    sid = _new(client, ALICE)
    sess = jarvis_server.sessions.sessions[jarvis_server.APP]['alice'][sid]
    sess.last_update_time = time.time() - 40 * 86400
    sess.state['pending_approval'] = {'x': 1}
    assert asyncio.run(jarvis_server._retention_sweep('alice')) == 0
    assert sid in jarvis_server.sessions.sessions[jarvis_server.APP]['alice']


def test_startup_registers_every_users_sessions(client):
    sa, sb = _new(client, ALICE), _new(client, BOB)
    for sid in (sa, sb):
        jarvis_server.session_last_used.pop(sid, None)
        jarvis_server.session_owner.pop(sid, None)
    asyncio.run(jarvis_server._register_persisted_sessions())
    assert jarvis_server.session_owner[sa] == 'alice'
    assert jarvis_server.session_owner[sb] == 'bob'
    assert sa in jarvis_server.session_last_used and sb in jarvis_server.session_last_used
