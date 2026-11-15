"""Saved sessions: list, history, resume, delete, and design revision history."""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('JARVIS_SESSION_BACKEND', 'memory')

import jarvis_server  # noqa: E402
from jarvis_server import app  # noqa: E402
from ai_agents.tools import architecture_tools as at  # noqa: E402

H = {'authorization': 'Bearer test-token'}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(at, 'DESIGN_DIR', tmp_path / 'design')
    return TestClient(app)


def _new(client):
    r = client.post('/session', headers=H)
    assert r.status_code == 200
    return r.json()['session_id']


def test_new_session_is_listed(client):
    sid = _new(client)
    rows = client.get('/sessions', headers=H).json()['sessions']
    assert sid in [r['session_id'] for r in rows]


def test_resume_known_session(client):
    sid = _new(client)
    r = client.post('/session/%s/resume' % sid, headers=H)
    assert r.status_code == 200 and r.json()['session_id'] == sid


def test_resume_unknown_session_is_404_and_not_created(client):
    r = client.post('/session/doesnotexist/resume', headers=H)
    assert r.status_code == 404
    ids = [x['session_id'] for x in client.get('/sessions', headers=H).json()['sessions']]
    assert 'doesnotexist' not in ids


def test_history_of_fresh_session_is_empty(client):
    sid = _new(client)
    r = client.get('/session/%s/history' % sid, headers=H)
    assert r.status_code == 200 and r.json()['messages'] == []


def test_delete_removes_session(client):
    sid = _new(client)
    assert client.delete('/session/%s' % sid, headers=H).status_code == 200
    assert client.post('/session/%s/resume' % sid, headers=H).status_code == 404


def test_design_revisions_are_archived(client):
    sid = 'abc123'
    at.save_design(sid, {'architecture': {'revision': 1, 'components': []}})
    at.save_design(sid, {'architecture': {'revision': 2, 'components': []}})
    assert [v['revision'] for v in at.list_design_versions(sid)] == [1]
    assert at.load_design_version(sid, 1)['architecture']['revision'] == 1
    assert at.load_design(sid)['architecture']['revision'] == 2
