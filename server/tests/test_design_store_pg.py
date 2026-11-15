"""Design store on a real database. Runs only when JARVIS_TEST_DESIGN_DB is set, e.g.
   JARVIS_TEST_DESIGN_DB=postgresql+psycopg2://jarvis:jarvis@localhost:5432/jarvis pytest tests/test_design_store_pg.py
"""
import os
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
URL = os.getenv('JARVIS_TEST_DESIGN_DB')
pytestmark = pytest.mark.skipif(not URL, reason='JARVIS_TEST_DESIGN_DB not set')

from ai_agents.tools import architecture_tools as at  # noqa: E402
from ai_agents.tools import design_store as ds  # noqa: E402


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setenv('JARVIS_DESIGN_DB', URL)
    monkeypatch.setattr(at, '_owner_provider', lambda: 'alice')
    yield
    monkeypatch.setenv('JARVIS_DESIGN_DB', URL)
    for sid in ('t_a', 't_b', 't_race'):
        at.delete_design_data(sid)


def test_roundtrip_owner_and_history():
    assert at.design_owner('t_a') is None and at.load_design('t_a') == {}
    assert at.save_design('t_a', {'architecture': {'revision': 1, 'components': []}})
    assert at.design_owner('t_a') == 'alice'
    at._owner_provider = lambda: 'bob'                       # owner is sticky
    at.save_design('t_a', {'architecture': {'revision': 2}})
    at.save_design('t_a', {'architecture': {'revision': 3}})
    assert at.design_owner('t_a') == 'alice'
    assert at.load_design('t_a')['architecture']['revision'] == 3
    assert [v['revision'] for v in at.list_design_versions('t_a')] == [1, 2]
    assert at.load_design_version('t_a', 1)['architecture']['revision'] == 1
    assert at.load_design_version('t_a', 99) == {}


def test_same_revision_does_not_archive():
    at.save_design('t_b', {'architecture': {'revision': 1}})
    at.save_design('t_b', {'architecture': {'revision': 1, 'x': 1}})
    assert at.list_design_versions('t_b') == []


def test_delete_removes_everything():
    at.save_design('t_b', {'architecture': {'revision': 1}})
    at.save_design('t_b', {'architecture': {'revision': 2}})
    at.delete_design_data('t_b')
    assert at.design_owner('t_b') is None and at.list_design_versions('t_b') == []


def test_concurrent_saves_do_not_lose_history():
    at.save_design('t_race', {'architecture': {'revision': 1}})
    errs = []
    def w(n):
        try:
            assert at.save_design('t_race', {'architecture': {'revision': n}})
        except Exception as e:
            errs.append(e)
    ts = [threading.Thread(target=w, args=(n,)) for n in range(2, 10)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs
    revs = [v['revision'] for v in at.list_design_versions('t_race')]
    assert 1 in revs and len(revs) == 8        # 9 saves -> 8 archived, one live


def test_failure_returns_false(monkeypatch):
    monkeypatch.setenv('JARVIS_DESIGN_DB', 'postgresql+psycopg2://x:y@127.0.0.1:1/none')
    assert at.save_design('t_a', {'architecture': {'revision': 1}}) is False
    assert at.load_design('t_a') == {}
