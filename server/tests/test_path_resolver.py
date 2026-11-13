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


# ------------------------------------------------- PATH_POLICIES argument names

def _policy_errors(tool, args, repo, monkeypatch, worktree=None):
    """Run semantic_errors with repo_root pinned to `repo`."""
    import ai_agents.tools._common as common
    import ai_agents.config as config
    monkeypatch.setattr(common, 'repo_root', lambda: repo)
    monkeypatch.setattr(config, 'ACTIVE_WORKTREE',
                        str(worktree) if worktree else None, raising=False)
    monkeypatch.setattr(config, 'WORKTREE_DIR', None, raising=False)
    monkeypatch.setattr(config, 'REPOSITORY_DIR', None, raising=False)
    from ai_agents.registry.semantic_validators import semantic_errors
    return semantic_errors(tool, args)


def test_search_code_directory_policy(repo, monkeypatch):
    errs = _policy_errors('search_code', {'directory': '../outside'},
                          repo, monkeypatch)
    assert errs
    errs = _policy_errors('search_code', {'directory': 'src'},
                          repo, monkeypatch)
    assert not errs


def test_verify_tools_use_repository_path(repo, monkeypatch, tmp_path):
    wt = tmp_path / 'wt'
    wt.mkdir()
    # Inside the active worktree is allowed.
    assert not _policy_errors('verify_lint',
                              {'repository_path': str(wt)},
                              repo, monkeypatch, worktree=wt)
    # Traversal and absolute outsiders are rejected.
    assert _policy_errors('verify_lint',
                          {'repository_path': '../escape'},
                          repo, monkeypatch, worktree=wt)
    assert _policy_errors('verify_types',
                          {'repository_path': '/etc'},
                          repo, monkeypatch, worktree=wt)


def test_symlink_escape_rejected(repo, monkeypatch, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + '_outside')
    outside.mkdir(exist_ok=True)
    (repo / 'link').symlink_to(outside, target_is_directory=True)
    errs = _policy_errors('search_code', {'directory': 'link'},
                          repo, monkeypatch)
    assert errs


def test_active_repository_policy_blocks_dotdot(repo, monkeypatch):
    for tool, args in (
            ('detect_languages', {'repository_path': '../x'}),
            ('get_changed_files', {'repository_path': '/tmp'}),
            ('trace_file_operations', {'file_path': '../../etc/passwd'})):
        errs = _policy_errors(tool, args, repo, monkeypatch)
        assert errs, (tool, args)


def test_repository_selection_policy(tmp_path, monkeypatch):
    """index_repository / incremental_index_repository take a repository
    name ('.' or '' = active repo), validated against registered repos —
    not resolved as a path inside the active repository."""
    import ai_agents.config as config
    repos = tmp_path / 'repos'
    (repos / 'alpha').mkdir(parents=True)
    (repos / 'beta').mkdir()
    monkeypatch.setattr(config, 'REPOSITORY_DIR', repos)
    from ai_agents.registry.semantic_validators import semantic_errors
    for tool in ('index_repository', 'incremental_index_repository'):
        assert semantic_errors(tool, {'repository_path': 'alpha'}) == []
        assert semantic_errors(tool, {'repository_path': '.'}) == []
        assert semantic_errors(tool, {'repository_path': ''}) == []
        assert semantic_errors(tool, {'repository_path': 'gamma'})
        assert semantic_errors(tool, {'repository_path': 42})
        # The tools reduce the value to Path(...).name before activate(),
        # so a path whose basename is registered selects that repository.
        assert semantic_errors(
            tool, {'repository_path': 'some/dir/beta'}) == []
