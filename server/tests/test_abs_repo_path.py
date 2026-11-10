import pytest
from ai_agents import config
from ai_agents.tools._common import abs_repo_path


def test_resolves_against_selected_repo(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'; (repo / 'pkg').mkdir(parents=True)
    (repo / 'pkg' / 'a.py').write_text('def f():\n    return 1\n')
    monkeypatch.setattr(config, 'REPO_ROOT', repo)
    assert abs_repo_path('pkg/a.py') == (repo / 'pkg' / 'a.py').resolve()


def test_rejects_escape(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'; repo.mkdir()
    monkeypatch.setattr(config, 'REPO_ROOT', repo)
    with pytest.raises(ValueError):
        abs_repo_path('../outside.py')
