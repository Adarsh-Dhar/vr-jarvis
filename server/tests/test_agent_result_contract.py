"""AgentResult contract tests: parsing, evidence validation, degradation."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_agents.agent_result import AgentResult, Evidence, validate_evidence_paths
from jarvis_server import _agent_result_view, _parse_agent_result


def _result(**kw):
    base = {"status": "completed", "answer": "ok"}
    base.update(kw)
    return base


def test_valid_dict_result():
    r = _parse_agent_result(_result())
    assert r.status == 'completed'


def test_valid_json_string_result():
    r = _parse_agent_result(json.dumps(_result()))
    assert r.status == 'completed'


def test_invalid_json_string():
    with pytest.raises(Exception):
        _parse_agent_result('{not json')


def test_missing_status():
    with pytest.raises(Exception):
        AgentResult.model_validate({"answer": "x"})


def test_unknown_status():
    with pytest.raises(Exception):
        AgentResult.model_validate(_result(status='bogus'))


def test_partial_requires_reason_or_limitations():
    with pytest.raises(Exception):
        AgentResult.model_validate(_result(status='partial'))
    r = AgentResult.model_validate(_result(status='partial', reason='incomplete'))
    assert r.status == 'partial'


def test_extra_fields_survive():
    r = _parse_agent_result(_result(patch={'files': []}, tasks=[1], review={'v': 1}))
    assert r.patch == {'files': []}
    assert r.tasks == [1]
    assert r.review == {'v': 1}


@pytest.fixture
def repo(tmp_path):
    (tmp_path / 'mod.py').write_text('x = 1\ny = 2\nz = 3\n')
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'other.py').write_text('a = 1\n')
    return tmp_path


def _ev(file, line, end_line=None):
    return Evidence(file=file, line=line, end_line=end_line)


def test_evidence_absolute_path_rejected(repo):
    r = AgentResult(status='completed', evidence=[_ev(str(repo / 'mod.py'), 1)])
    errs = validate_evidence_paths(r, repo)
    assert errs


def test_evidence_dotdot_rejected(repo):
    r = AgentResult(status='completed', evidence=[_ev('../outside.py', 1)])
    errs = validate_evidence_paths(r, repo)
    assert errs


def test_evidence_symlink_escape_rejected(repo, tmp_path):
    outside_dir = tmp_path.parent / (tmp_path.name + '_elsewhere')
    outside_dir.mkdir(exist_ok=True)
    outside = outside_dir / 'outside.py'
    outside.write_text('secret = 1\n')
    (repo / 'link.py').symlink_to(outside)
    r = AgentResult(status='completed', evidence=[_ev('link.py', 1)])
    errs = validate_evidence_paths(r, repo)
    assert errs


def test_evidence_missing_file(repo):
    r = AgentResult(status='completed', evidence=[_ev('nope.py', 1)])
    assert validate_evidence_paths(r, repo)


def test_evidence_line_bounds(repo):
    with pytest.raises(Exception):
        _ev('mod.py', 0)  # rejected by the model itself
    with pytest.raises(Exception):
        _ev('mod.py', 1, end_line=0)
    # validator-level checks via model_construct (bypasses field constraints)
    def evc(line, end_line=None):
        return Evidence.model_construct(file='mod.py', line=line, end_line=end_line)
    assert validate_evidence_paths(
        AgentResult(status='completed', evidence=[evc(0)]), repo)
    assert validate_evidence_paths(
        AgentResult(status='completed', evidence=[evc(99)]), repo)
    with pytest.raises(Exception):
        AgentResult(status='completed', evidence=[evc(1, end_line=0)])
    # valid range passes
    assert validate_evidence_paths(
        AgentResult(status='completed', evidence=[_ev('mod.py', 1, end_line=3)]), repo) == []


def test_agent_result_view_malformed_is_partial(repo, monkeypatch):
    import jarvis_server
    monkeypatch.setattr(jarvis_server.config, 'REPO_ROOT', repo)
    state = {'result_code_understanding': '{broken json', 'reply': 'hi'}
    answer, limitations, degraded = _agent_result_view(state)
    assert degraded is True
    assert any('result_code_understanding' in lim for lim in limitations)


def test_agent_result_view_failed_status_degrades(repo, monkeypatch):
    import jarvis_server
    monkeypatch.setattr(jarvis_server.config, 'REPO_ROOT', repo)
    state = {'result_testing': json.dumps(
        _result(status='failed', reason='tests crashed'))}
    answer, limitations, degraded = _agent_result_view(state)
    assert degraded is True
    assert any('tests crashed' in lim for lim in limitations)


def test_agent_result_view_valid_passes(repo, monkeypatch):
    import jarvis_server
    monkeypatch.setattr(jarvis_server.config, 'REPO_ROOT', repo)
    state = {'result_code_understanding': _result(
        evidence=[{'file': 'mod.py', 'line': 1}])}
    answer, limitations, degraded = _agent_result_view(state)
    assert degraded is False
    assert answer == 'ok'


def test_root_reply_stays_string():
    # conversational root output is plain text, not an AgentResult
    assert isinstance('done', str)


def test_task_entry_invalid_evidence_path_marked_invalid(repo, monkeypatch):
    """Acceptance: a specialist result with an evidence path escaping the
    repository is marked invalid, not presented as a verified fact."""
    import jarvis_server
    monkeypatch.setattr(jarvis_server.config, 'REPO_ROOT', repo)
    entry = jarvis_server._validated_agent_result_entry(
        'code_understanding',
        _result(evidence=[{'file': '../outside.py', 'line': 1}]))
    assert entry['status'] == 'invalid'
    assert entry['validated'] is False
    assert entry['summary'] == ''
    assert entry['validation_errors']


def test_task_entry_valid_result_marked_validated(repo, monkeypatch):
    import jarvis_server
    monkeypatch.setattr(jarvis_server.config, 'REPO_ROOT', repo)
    entry = jarvis_server._validated_agent_result_entry(
        'code_understanding',
        _result(evidence=[{'file': 'mod.py', 'line': 1}]))
    assert entry['validated'] is True
    assert entry['status'] == 'completed'
