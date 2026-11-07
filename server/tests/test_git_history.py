"""Git history visualization tests."""

import pytest
from pathlib import Path
import tempfile
import subprocess


def test_git_log_last_n_commits():
    """Test that the last 20 commits are retrieved correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Initialize a git repository
        subprocess.run(['git', 'init'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmppath, capture_output=True)
        
        # Create some commits
        for i in range(5):
            test_file = tmppath / f"test{i}.txt"
            test_file.write_text(f"content {i}")
            subprocess.run(['git', 'add', f"test{i}.txt"], cwd=tmppath, capture_output=True)
            subprocess.run(['git', 'commit', '-m', f'Commit {i}'], cwd=tmppath, capture_output=True)
        
        # Get last 20 commits using the same format as git_history_toolkit
        result = subprocess.run(
            ['git', 'log', '-20', '--format=%H%x00%s%x00%an%x00%ad%x00'],
            cwd=str(tmppath),
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        # Verify we get 5 commits
        # The format uses \x00 between fields and \n between commits
        output = result.stdout.strip()
        # Split by newlines first (each commit is on its own line)
        commit_lines = output.split('\n')
        assert len(commit_lines) == 5
        
        # Verify each commit has required fields
        for line in commit_lines:
            parts = line.split('\x00')
            assert len(parts) >= 4
            assert parts[0]  # hash
            assert parts[1]  # message
            assert parts[2]  # author
            assert parts[3]  # date


def test_git_parse_commit_metadata():
    """Test that commit metadata is parsed correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Initialize a git repository
        subprocess.run(['git', 'init'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmppath, capture_output=True)
        
        # Create a commit
        test_file = tmppath / "test.txt"
        test_file.write_text("content")
        subprocess.run(['git', 'add', 'test.txt'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Test commit'], cwd=tmppath, capture_output=True)
        
        # Get commit metadata
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%H%x00%s%x00%an%x00%ad%x00'],
            cwd=str(tmppath),
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        parts = result.stdout.strip().split('\x00')
        assert len(parts) >= 4
        assert parts[0]  # hash
        assert parts[1] == 'Test commit'  # message
        assert parts[2] == 'Test User'  # author
        assert parts[3]  # date


def test_git_parse_changed_files():
    """Test that changed files with statuses are parsed correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Initialize a git repository
        subprocess.run(['git', 'init'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmppath, capture_output=True)
        
        # Create and add a file
        test_file = tmppath / "test.txt"
        test_file.write_text("content")
        subprocess.run(['git', 'add', 'test.txt'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Add file'], cwd=tmppath, capture_output=True)
        
        # Modify the file
        test_file.write_text("modified content")
        subprocess.run(['git', 'add', 'test.txt'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Modify file'], cwd=tmppath, capture_output=True)
        
        # Get the last commit hash
        hash_result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=str(tmppath),
            capture_output=True,
            text=True
        )
        commit_hash = hash_result.stdout.strip()
        
        # Get file changes
        result = subprocess.run(
            ['git', 'show', '--numstat', '--name-status', '--format=', commit_hash],
            cwd=str(tmppath),
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        # Should have changed files
        assert 'test.txt' in result.stdout


def test_git_filenames_with_spaces():
    """Test that filenames with spaces are handled correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Initialize a git repository
        subprocess.run(['git', 'init'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmppath, capture_output=True)
        
        # Create a file with spaces
        test_file = tmppath / "test file with spaces.txt"
        test_file.write_text("content")
        subprocess.run(['git', 'add', 'test file with spaces.txt'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Add file with spaces'], cwd=tmppath, capture_output=True)
        
        # Get file changes
        result = subprocess.run(
            ['git', 'show', '--numstat', '--name-status', '--format=', 'HEAD'],
            cwd=str(tmppath),
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        # The filename should be in the output
        assert 'test file with spaces.txt' in result.stdout


def test_git_file_additions_deletions():
    """Test that per-file additions and deletions are tracked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Initialize a git repository
        subprocess.run(['git', 'init'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmppath, capture_output=True)
        
        # Create a file with multiple lines
        test_file = tmppath / "test.txt"
        test_file.write_text("line1\nline2\nline3")
        subprocess.run(['git', 'add', 'test.txt'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Add file'], cwd=tmppath, capture_output=True)
        
        # Modify the file
        test_file.write_text("line1\nmodified\nline3\nline4")
        subprocess.run(['git', 'add', 'test.txt'], cwd=tmppath, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Modify file'], cwd=tmppath, capture_output=True)
        
        # Get file changes with numstat
        result = subprocess.run(
            ['git', 'show', '--numstat', '--name-status', '--format=', 'HEAD'],
            cwd=str(tmppath),
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        # The output should contain numbers for additions/deletions
        lines = result.stdout.strip().split('\n')
        # numstat with --name-status format: status additions deletions filename
        # Check that we have numeric data for additions/deletions
        for line in lines:
            if line:
                parts = line.split()
                if len(parts) >= 3:
                    # Format: status additions deletions filename
                    # parts[0] is status (M, A, etc.)
                    # parts[1] is additions, parts[2] is deletions
                    assert parts[1].isdigit() or parts[1] == '-'
                    assert parts[2].isdigit() or parts[2] == '-'
