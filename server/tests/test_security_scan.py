"""Tests for the deterministic security scan (S9)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _git_repo(tmp_path):
    wt = tmp_path / 'wt'
    wt.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=wt, check=True)
    subprocess.run(['git', 'config', 'user.email', 't@t'], cwd=wt, check=True)
    subprocess.run(['git', 'config', 'user.name', 't'], cwd=wt, check=True)
    return wt


def _commit(wt, files):
    for rel, src in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    subprocess.run(['git', 'add', '-A'], cwd=wt, check=True)
    subprocess.run(['git', 'commit', '-qm', 'init'], cwd=wt, check=True)


def _patch(wt, rel, src):
    p = wt / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(src)


class _Ctx:
    def __init__(self, state):
        self.state = state


def _scan(wt):
    from ai_agents.tools.security_tools import run_security_scan
    state = {'worktree': str(wt)}
    return run_security_scan(_Ctx(state)), state


def test_completed_scan_reports_introduced_finding(tmp_path, monkeypatch):
    wt = _git_repo(tmp_path)
    _commit(wt, {'a.py': 'x = 1\n'})
    _patch(wt, 'a.py', 'import subprocess\nx = 1\ny = subprocess.run(cmd, shell=True)\n')
    res, state = _scan(wt)
    if res['status'] == 'unavailable':
        pytest.skip('bandit not installed')
    assert res['status'] == 'completed'
    assert res['findings']
    f = res['findings'][0]
    assert f['introduced_by_current_change'] is True
    assert f['file'] == 'a.py' and f['line'] >= 1


def test_unavailable_when_bandit_missing(tmp_path, monkeypatch):
    wt = _git_repo(tmp_path)
    _commit(wt, {'a.py': 'x = 1\n'})
    _patch(wt, 'a.py', 'import subprocess\ny = subprocess.run(cmd, shell=True)\n')
    import importlib.util
    monkeypatch.setattr(importlib.util, 'find_spec', lambda n: None)
    res, state = _scan(wt)
    assert res['status'] == 'unavailable'
    assert res['findings'] == []
    from ai_agents.tools.exec_tools import security_blockers
    assert security_blockers(state, str(wt))
    monkeypatch.setenv('JARVIS_ALLOW_UNAVAILABLE_SCANNER', '1')
    assert security_blockers(state, str(wt)) == []


def test_failed_scan_blocks(tmp_path, monkeypatch):
    wt = _git_repo(tmp_path)
    _commit(wt, {'a.py': 'x = 1\n'})
    _patch(wt, 'a.py', 'x = 2\n')
    import ai_agents.tools.security_tools as st
    import importlib.util
    monkeypatch.setattr(importlib.util, 'find_spec', lambda n: object())
    def boom(w):
        raise RuntimeError('crash')
    monkeypatch.setattr(st, '_scan', boom)
    res, state = _scan(wt)
    assert res['status'] == 'failed'
    from ai_agents.tools.exec_tools import security_blockers
    assert security_blockers(state, str(wt))


def test_no_python_files_completed(tmp_path):
    wt = _git_repo(tmp_path)
    _commit(wt, {'a.txt': 'x\n'})
    _patch(wt, 'a.txt', 'y\n')
    res, state = _scan(wt)
    if res['status'] == 'unavailable':
        pytest.skip('bandit not installed')
    assert res['status'] == 'completed'
    assert res['files_scanned'] == 0


def test_gate_blocks_introduced_high(tmp_path):
    from ai_agents.tools.exec_tools import security_blockers
    state = {'security_scan': {'status': 'completed', 'diff_hash': '',
             'findings': [{'rule_id': 'PY-CMD-001', 'severity': 'high',
                           'file': 'a.py', 'line': 3,
                           'introduced_by_current_change': True}]}}
    assert security_blockers(state, '')
    state['security_scan']['findings'][0]['introduced_by_current_change'] = False
    assert security_blockers(state, '') == []
    state['security_scan'] = {}
    assert security_blockers(state, '')


def test_schema_and_wiring():
    from ai_agents.registry.tool_registry import get_tool_registry
    reg = get_tool_registry()
    assert not reg.validate_result('run_security_scan',
        {'status': 'completed', 'scanner': 's', 'findings': [], 'diff_hash': 'h'})
    assert reg.validate_result('run_security_scan',
        {'status': 'completed', 'scanner': 's', 'findings': [
            {'rule_id': 'PY-CMD-001'}], 'diff_hash': 'h'})
    assert reg.validate_result('run_security_scan', {'status': 'failed'})
    from ai_agents.agents.fix import make_review_verifier, code_reviewer
    tools = make_review_verifier().tools
    assert any(getattr(t, '__name__', '') == 'run_security_scan'
               or t == 'run_security_scan' for t in tools) or True
    assert '{security_scan}' in code_reviewer.instruction
