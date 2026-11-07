"""
Git history toolkit tests.

Tests the actual production history parser using a temporary Git repository.
The fixture must have:
- A new file
- A modified file
- A deleted file
- A renamed file
- A filename containing spaces
- Multiple commits with different messages
"""

import pytest
import subprocess
import tempfile
import os
from pathlib import Path
from ai_agents.tools.git_history_toolkit import (
    visualize_git_history,
    _load_recent_commit_hashes,
    _load_commit_metadata,
    _load_commit_files,
    _load_recent_commits
)


def create_test_repo(tmpdir):
    """Create a temporary Git repository with test commits."""
    repo_path = Path(tmpdir) / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=str(repo_path), check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=str(repo_path), check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=str(repo_path), check=True)

    # Commit 1: Initial files
    (repo_path / "auth.py").write_text("""
def authenticate(username, password):
    return username == "admin" and password == "secret"

def login(user):
    return authenticate(user.username, user.password)
""")

    (repo_path / "users.py").write_text("""
def get_user(user_id):
    return {"id": user_id, "name": "John"}

def update_user(user_id, data):
    return True
""")

    (repo_path / "README.md").write_text("# Test Repo\n")

    subprocess.run(['git', 'add', '.'], cwd=str(repo_path), check=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=str(repo_path), check=True)

    # Commit 2: Modify auth.py and add session.py
    (repo_path / "auth.py").write_text("""
def authenticate(username, password):
    return username == "admin" and password == "secret"

def login(user):
    return authenticate(user.username, user.password)

def logout(user):
    return True
""")

    (repo_path / "session.py").write_text("""
def create_session(user_id):
    return {"session_id": "abc123", "user_id": user_id}
""")

    subprocess.run(['git', 'add', '.'], cwd=str(repo_path), check=True)
    subprocess.run(['git', 'commit', '-m', 'Add session management'], cwd=str(repo_path), check=True)

    # Commit 3: Delete users.py, rename README.md to README.txt, add file with spaces
    (repo_path / "users.py").unlink()

    # Rename README.md to README.txt
    (repo_path / "README.md").rename(repo_path / "README.txt")

    # Add file with spaces in name
    (repo_path / "config file.py").write_text("""
DEBUG = True
DATABASE_URL = "postgresql://localhost/db"
""")

    subprocess.run(['git', 'add', '-A'], cwd=str(repo_path), check=True)
    subprocess.run(['git', 'commit', '-m', 'Refactor: remove users, rename README, add config'], cwd=str(repo_path), check=True)

    return str(repo_path)


def test_visualize_git_history_basic(repo_path, mock_tool_context):
    """Test basic git history visualization."""
    result = visualize_git_history(repo_path, mock_tool_context)

    assert result['status'] == 'ok'
    assert result['commit_count'] == 3
    assert len(result['commits']) == 3

    # Check commits are in reverse chronological order (newest first)
    commits = result['commits']
    assert commits[0]['message'] == 'Refactor: remove users, rename README, add config'
    assert commits[1]['message'] == 'Add session management'
    assert commits[2]['message'] == 'Initial commit'


def test_visualize_git_history_commit_structure(repo_path, mock_tool_context):
    """Test that commits have the correct structure."""
    result = visualize_git_history(repo_path, mock_tool_context)
    assert result['status'] == 'ok'

    commit = result['commits'][0]  # Most recent commit

    # Check required fields
    assert 'hash' in commit
    assert 'parent_hash' in commit
    assert 'message' in commit
    assert 'author' in commit
    assert 'date' in commit
    assert 'additions' in commit
    assert 'deletions' in commit
    assert 'file_count' in commit
    assert 'files' in commit
    assert 'mapped_node_ids' in commit
    assert 'mapping_status' in commit

    # Check files structure
    assert isinstance(commit['files'], list)
    for file_info in commit['files']:
        assert 'path' in file_info
        assert 'old_path' in file_info
        assert 'status' in file_info
        assert 'additions' in file_info
        assert 'deletions' in file_info
        assert 'mapped_node_ids' in file_info


def test_visualize_git_history_file_statuses(repo_path, mock_tool_context):
    """Test that file statuses are correctly parsed."""
    result = visualize_git_history(repo_path, mock_tool_context)
    assert result['status'] == 'ok'

    # Check third commit (most recent) for deleted and renamed files
    commit = result['commits'][0]
    files = {f['path']: f for f in commit['files']}

    # Check for deleted file
    assert 'users.py' in files
    assert files['users.py']['status'] == 'deleted'

    # Check for renamed file
    assert 'README.txt' in files
    assert files['README.txt']['status'] == 'renamed'
    assert files['README.txt']['old_path'] == 'README.md'

    # Check for added file with spaces
    assert 'config file.py' in files
    assert files['config file.py']['status'] == 'added'


def test_visualize_git_history_additions_deletions(repo_path, mock_tool_context):
    """Test that additions and deletions are correctly calculated."""
    result = visualize_git_history(repo_path, mock_tool_context)
    assert result['status'] == 'ok'

    # Check that totals are present and reasonable
    commit = result['commits'][0]
    assert commit['additions'] >= 0
    assert commit['deletions'] >= 0
    assert commit['file_count'] == len(commit['files'])


def test_visualize_git_history_commit_hashes(repo_path, mock_tool_context):
    """Test that commit hashes are retrieved correctly."""
    result = visualize_git_history(repo_path, mock_tool_context)
    assert result['status'] == 'ok'

    for commit in result['commits']:
        assert len(commit['hash']) == 40  # SHA-1 hash length
        # Root commits have no parent hash (None is valid)
        # Non-root commits should have a parent hash
        if commit['parent_hash'] is not None:
            assert len(commit['parent_hash']) == 40 or commit['parent_hash'] == ''


def test_visualize_git_history_show_history_panel(repo_path, mock_tool_context):
    """Test that show_history_panel command includes full structured commits."""
    result = visualize_git_history(repo_path, mock_tool_context)
    assert result['status'] == 'ok'

    # Check that scene_commands were emitted
    assert 'scene_commands' in mock_tool_context.state
    commands = mock_tool_context.state['scene_commands']

    # Find the show_history_panel command
    history_cmd = None
    for cmd in commands:
        if cmd.get('type') == 'show_history_panel':
            history_cmd = cmd
            break

    assert history_cmd is not None, "show_history_panel command not found"
    assert 'commits' in history_cmd
    assert len(history_cmd['commits']) == 3

    # Verify commits structure matches Python JSON names
    commit = history_cmd['commits'][0]
    assert 'hash' in commit
    assert 'parent_hash' in commit
    assert 'message' in commit
    assert 'author' in commit
    assert 'date' in commit
    assert 'additions' in commit
    assert 'deletions' in commit
    assert 'file_count' in commit
    assert 'files' in commit
    assert 'mapped_node_ids' in commit
    assert 'mapping_status' in commit


def test_visualize_git_history_graph_mapping(repo_path, mock_tool_context):
    """Test that graph node mapping is included (may be empty in test repo)."""
    result = visualize_git_history(repo_path, mock_tool_context)
    assert result['status'] == 'ok'

    # mapping_status should indicate whether mapping was done
    for commit in result['commits']:
        assert 'mapping_status' in commit
        # In test repo, there may be no graph nodes, so status should be 'file_level'
        # or similar
        assert commit['mapping_status'] in ['partial', 'file_level', 'none']


def test_visualize_git_history_empty_repo(tmpdir, mock_tool_context):
    """Test behavior with an empty repository (no commits)."""
    repo_path = Path(tmpdir) / "empty_repo"
    repo_path.mkdir()

    # Initialize git repo but no commits
    subprocess.run(['git', 'init'], cwd=str(repo_path), check=True)

    result = visualize_git_history(str(repo_path), mock_tool_context)

    # Should handle gracefully - either ok with 0 commits or error
    assert result['status'] in ['ok', 'error']
    if result['status'] == 'ok':
        assert result['commit_count'] == 0
        assert len(result['commits']) == 0


def test_visualize_git_history_filename_with_spaces(repo_path, mock_tool_context):
    """Test that filenames with spaces are handled correctly."""
    result = visualize_git_history(repo_path, mock_tool_context)
    assert result['status'] == 'ok'

    # Find the commit that added the file with spaces
    found = False
    for commit in result['commits']:
        for file_info in commit['files']:
            if 'config file.py' in file_info['path']:
                found = True
                assert file_info['status'] == 'added'
                break
        if found:
            break

    assert found, "File with spaces not found in git history"


def test_load_recent_commit_hashes(repo_path, mock_tool_context):
    """Test _load_recent_commit_hashes helper."""
    path = Path(repo_path)
    hashes = _load_recent_commit_hashes(path, limit=20)

    assert len(hashes) == 3
    assert all(len(h) == 40 for h in hashes)  # SHA-1 hashes


def test_load_commit_metadata(repo_path, mock_tool_context):
    """Test _load_commit_metadata helper."""
    path = Path(repo_path)
    hashes = _load_recent_commit_hashes(path, limit=1)

    assert len(hashes) > 0
    metadata = _load_commit_metadata(path, hashes[0])

    assert 'hash' in metadata
    assert 'parent_hashes' in metadata
    assert 'author' in metadata
    assert 'date' in metadata
    assert 'message' in metadata
    assert metadata['message'] == 'Refactor: remove users, rename README, add config'


def test_load_commit_files(repo_path, mock_tool_context):
    """Test _load_commit_files helper."""
    path = Path(repo_path)
    hashes = _load_recent_commit_hashes(path, limit=1)

    assert len(hashes) > 0
    files = _load_commit_files(path, hashes[0])

    assert isinstance(files, dict)
    assert len(files) > 0

    # Check for renamed file
    assert 'README.txt' in files
    assert files['README.txt']['status'] == 'renamed'
    assert files['README.txt']['old_path'] == 'README.md'

    # Check for deleted file
    assert 'users.py' in files
    assert files['users.py']['status'] == 'deleted'

    # Check for file with spaces
    assert 'config file.py' in files
    assert files['config file.py']['status'] == 'added'


def test_load_recent_commits(repo_path, mock_tool_context):
    """Test _load_recent_commits helper."""
    path = Path(repo_path)

    # Create a mock graph
    class MockGraph:
        def __init__(self):
            self._nodes = {}

    mock_graph = MockGraph()

    commits = _load_recent_commits(path, mock_graph, limit=20)

    assert len(commits) == 3
    assert commits[0]['message'] == 'Refactor: remove users, rename README, add config'
    assert commits[1]['message'] == 'Add session management'
    assert commits[2]['message'] == 'Initial commit'

    # Check structure
    for commit in commits:
        assert 'hash' in commit
        assert 'parent_hash' in commit
        assert 'message' in commit
        assert 'author' in commit
        assert 'date' in commit
        assert 'additions' in commit
        assert 'deletions' in commit
        assert 'file_count' in commit
        assert 'files' in commit
        assert 'mapped_node_ids' in commit
        assert 'mapping_status' in commit


@pytest.fixture
def repo_path(tmpdir):
    """Fixture to create a test repository."""
    return create_test_repo(tmpdir)


@pytest.fixture
def mock_tool_context():
    """Fixture to create a mock tool context."""
    class MockToolContext:
        def __init__(self):
            self.state = {}

    return MockToolContext()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
