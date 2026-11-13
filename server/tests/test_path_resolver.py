"""Centralized path resolver policy tests."""
import pytest
from pathlib import Path

from ai_agents.tools.path_resolver import (
    PathPolicy, PathResolutionError, resolve, resolve_repo_read,
    resolve_repo_write, resolve_worktree_read, resolve_worktree_write)
from ai_agents.tools._common import resolve_in_repo
from ai_agents.tools.software_engineering_tools import _safe_worktree_path


@pytest.fixture
def repo(tmp_path):
    (tmp_path / 'src').mkdir()
    return tmp_path


class _Ctx:
    def __init__(self, state):
        self.state = state


def test_repo_read_stays_inside(repo):
    p = resolve_repo_read('src/a.py', root=repo)
    assert p == (repo / 'src' / 'a.py').resolve()


def test_repo_read_rejects_escape(repo):
    with pytest.raises(PathResolutionError):
        resolve_repo_read('../outside.py', root=repo)
    with pytest.raises(PathResolutionError):
        resolve_repo_read('/etc/passwd', root=repo)


def test_absolute_inside_root_accepted(repo):
    inside = repo / 'src' / 'b.py'
    assert resolve_repo_read(str(inside), root=repo) == inside.resolve()


def test_resolve_in_repo_delegates(repo):
    assert resolve_in_repo('src/a.py', root=repo) == \
        (repo / 'src' / 'a.py').resolve()
    with pytest.raises(ValueError):
        resolve_in_repo('../../x', root=repo)


def test_worktree_write_denies_git_and_node_modules(repo):
    wt = repo / 'wt'
    wt.mkdir()
    for bad in ('.git/config', 'node_modules/pkg/index.js'):
        with pytest.raises(PathResolutionError):
            resolve_worktree_write(bad, root=wt)
    ok = resolve_worktree_write('src/x.py', root=wt)
    assert ok == (wt / 'src' / 'x.py').resolve()


def test_worktree_requires_state_or_root(repo):
    with pytest.raises(PathResolutionError):
        resolve_worktree_read('a.py')  # no tool_context, no root
    ctx = _Ctx({'worktree': str(repo)})
    assert resolve_worktree_read('a.py', tool_context=ctx) == \
        (repo / 'a.py').resolve()


def test_safe_worktree_path_matches_policy(repo):
    wt = repo / 'wt'
    wt.mkdir()
    assert _safe_worktree_path('f.py', wt) == (wt / 'f.py').resolve()
    with pytest.raises(ValueError):
        _safe_worktree_path('.git/HEAD', wt)
    with pytest.raises(ValueError):
        _safe_worktree_path('../escape.py', wt)


def test_vr_root_policy(repo, monkeypatch):
    import ai_agents.config as config
    monkeypatch.setattr(config, 'REPO_ROOT', str(repo))
    monkeypatch.setattr(config, 'REPOSITORY_DIR', repo.parent)
    p = resolve('src/a.py', PathPolicy.VR_ROOT)
    assert p == (repo / 'src' / 'a.py').resolve()
    with pytest.raises(PathResolutionError):
        resolve('/etc/hostname', PathPolicy.VR_ROOT)
