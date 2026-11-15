"""Credential scrub for child processes.

JARVIS runs test/typecheck/git helpers as subprocesses. Those children must
never inherit secrets like GOOGLE_API_KEY or JARVIS_TOKEN — a judge could
otherwise edit a test file in VR, press VERIFY, and read the key from output.
"""
import os
import sys

from ai_agents.tools.exec_tools import _clean_env, _run


def test_clean_env_strips_credentials(monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY', 'supersecret')
    monkeypatch.setenv('JARVIS_TOKEN', 'tok123')
    monkeypatch.setenv('MY_DB_PASSWORD', 'pw')
    env = _clean_env()
    assert 'GOOGLE_API_KEY' not in env
    assert 'JARVIS_TOKEN' not in env
    assert 'MY_DB_PASSWORD' not in env
    # Non-secret variables still pass through.
    assert env.get('PATH') == os.environ.get('PATH')


def test_run_child_cannot_print_api_key(monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY', 'supersecret-value')
    rc, out, err = _run(
        [sys.executable, '-c',
         'import os; print(os.environ.get("GOOGLE_API_KEY", "<unset>"))'],
        os.getcwd())
    assert rc == 0
    assert 'supersecret-value' not in out
    assert 'supersecret-value' not in err
