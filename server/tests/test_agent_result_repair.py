'''Repair of near-miss specialist output (see agent_result.coerce_agent_result).'''
import json

import pytest

from ai_agents.agent_result import AgentResult, coerce_agent_result

GOOD = {'status': 'completed', 'answer': 'ok', 'findings': [], 'evidence': []}


def _res(raw):
    value, notes = coerce_agent_result(raw)
    return AgentResult.model_validate(value if isinstance(value, dict) else json.loads(value)), notes


def test_valid_json_is_untouched():
    raw = json.dumps(GOOD)
    assert coerce_agent_result(raw) == (raw, [])
    assert coerce_agent_result(dict(GOOD)) == (GOOD, [])


def test_json_in_code_fence():
    r, notes = _res('Here you go:\n```json\n' + json.dumps(GOOD) + '\n```')
    assert r.status == 'completed' and r.answer == 'ok' and notes


def test_json_after_prose_without_fence():
    r, notes = _res('The repository is a backend. ' + json.dumps({'status': 'completed', 'answer': 'x'}))
    assert r.answer == 'x' and 'JSON found inside surrounding text' in notes


def test_string_findings_are_wrapped_not_rejected():
    """Real failure from the recorded demo: findings.0 'Input should be an object'."""
    r, notes = _res(json.dumps({'status': 'completed', 'answer': 'a',
                                'findings': ['It uses auth middleware.', 'It deletes accounts.']}))
    assert r.findings == [{'text': 'It uses auth middleware.'}, {'text': 'It deletes accounts.'}]
    assert any('wrapped' in n for n in notes)


def test_plain_prose_is_kept_as_partial_answer():
    """Real failure from the recorded demo: 'Invalid JSON ... This repository is a **N...'."""
    r, notes = _res('This repository is a **Node.js** service for account deletion.')
    assert r.status == 'partial' and 'Node.js' in r.answer
    assert r.limitations and notes == ['prose reply wrapped']


def test_broken_json_still_fails_closed():
    for bad in ('{broken json', '{not json', 'text {oops'):
        value, notes = coerce_agent_result(bad)
        assert value == bad and notes == []
        with pytest.raises(Exception):
            AgentResult.model_validate_json(value)


def test_unusable_evidence_is_dropped_never_invented():
    r, notes = _res(json.dumps({'status': 'completed', 'answer': 'a', 'evidence': [
        'routes/account.ts',                                   # bare string: no line
        {'file': 'a.ts'},                                      # no line
        {'file': 'b.ts', 'line': 'x'},                         # bad line
        {'path': 'c.ts', 'start': '7', 'end': '9', 'description': 'd'},   # repairable
        {'file': 'd.ts', 'line': 3}]}))
    assert [(e.file, e.line, e.end_line) for e in r.evidence] == [('c.ts', 7, 9), ('d.ts', 3, None)]
    assert any('3 evidence entries' in lim for lim in r.limitations)


def test_status_aliases_and_missing_status():
    assert _res(json.dumps({'status': 'Success', 'answer': 'a'}))[0].status == 'completed'
    r, _ = _res(json.dumps({'answer': 'a'}))
    assert r.status == 'partial' and r.limitations
    value, _ = coerce_agent_result(json.dumps({'status': 'banana', 'answer': 'a'}))
    with pytest.raises(Exception):
        AgentResult.model_validate(value if isinstance(value, dict) else json.loads(value))


def test_partial_without_reason_gets_one():
    r, _ = _res(json.dumps({'status': 'partial', 'answer': 'a', 'findings': ['x']}))
    assert r.limitations


def test_extra_fields_survive_repair():
    r, _ = _res(json.dumps({'status': 'completed', 'answer': 'a', 'findings': ['x'], 'patch': {'files': []}}))
    assert r.patch == {'files': []}


def test_non_string_inputs_pass_through():
    assert coerce_agent_result(None) == (None, [])
    assert coerce_agent_result('') == ('', [])
    assert coerce_agent_result(5) == (5, [])


def test_boundary_callback_repairs_and_records(tmp_path, monkeypatch):
    import ai_agents.config as config
    from ai_agents.agents.base import _result_contract_callback
    monkeypatch.setattr(config, 'REPO_ROOT', tmp_path)
    (tmp_path / 'a.py').write_text('x = 1\ny = 2\n')

    class Ctx:
        agent_name = 'specialist'
        def __init__(self, state): self.state = state
    state = {'result_x': '```json\n' + json.dumps({'status': 'completed', 'answer': 'a',
              'findings': ['f'], 'evidence': [{'file': 'a.py', 'line': 2}]}) + '\n```'}
    _result_contract_callback('result_x')(Ctx(state))
    out = json.loads(state['result_x'])
    assert out['status'] == 'completed' and out['findings'] == [{'text': 'f'}]
    assert not state.get('specialist_validation_errors')
    assert state['specialist_repairs'][0]['key'] == 'result_x'


def test_boundary_callback_still_rejects_evidence_outside_repo(tmp_path, monkeypatch):
    import ai_agents.config as config
    from ai_agents.agents.base import _result_contract_callback
    monkeypatch.setattr(config, 'REPO_ROOT', tmp_path)

    class Ctx:
        agent_name = 's'
        def __init__(self, state): self.state = state
    state = {'result_x': json.dumps({'status': 'completed', 'answer': 'a',
                                     'evidence': [{'file': '../etc/passwd', 'line': 1}]})}
    _result_contract_callback('result_x')(Ctx(state))
    assert json.loads(state['result_x'])['status'] == 'failed'
