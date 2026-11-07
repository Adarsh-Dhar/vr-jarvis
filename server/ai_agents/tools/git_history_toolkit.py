"""
Specialist Toolkit C - Git and Development History
Understand how a codebase evolved.
"""

from typing import Optional, List, Dict, Any
from ._common import repo_root, resolve_in_repo
from pathlib import Path
import subprocess
from google.adk.tools import ToolContext
from ._safe import safe


@safe
def find_introducing_commit(
    symbol_id: str,
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Find the commit that introduced a behavior."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)

        result = subprocess.run(
            ['git', 'log', '-S', symbol_id, '--format=%H', '--'],
            cwd=str(path),
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            commit_hash = result.stdout.strip().splitlines()[0]

            detail_result = subprocess.run(
                ['git', 'show', '--format=%H%x00%s%x00%an%x00%ad', commit_hash],
                cwd=str(path),
                capture_output=True,
                text=True
            )

            if detail_result.returncode == 0:
                parts = detail_result.stdout.strip().split('\x00')
                return {
                    'status': 'ok',
                    'symbol_id': symbol_id,
                    'commit_hash': commit_hash,
                    'message': parts[1] if len(parts) > 1 else '',
                    'author': parts[2] if len(parts) > 2 else '',
                    'date': parts[3] if len(parts) > 3 else ''
                }

        return {
            'status': 'not_found',
            'symbol_id': symbol_id,
            'message': 'Commit not found'
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


@safe
def trace_function_history(
    function_id: str,
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Trace history of a function using git log -L."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        # Parse function_id to get file and function name
        if ':' in function_id:
            file_part, func_name = function_id.split(':', 1)
        else:
            return {
                'status': 'error',
                'error': 'Function ID must be in format file:function'
            }
        
        # Use git log -L to trace function history
        result = subprocess.run(
            ['git', 'log', '-L', f':{func_name}:{file_part}', '--format=%H|%s|%an|%ad'],
            cwd=str(path),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            commits = []
            for line in result.stdout.strip().splitlines():
                parts = line.split('|')
                if len(parts) >= 4:
                    commits.append({
                        'hash': parts[0],
                        'message': parts[1],
                        'author': parts[2],
                        'date': parts[3]
                    })
            
            return {
                'status': 'ok',
                'function_id': function_id,
                'commits': commits,
                'commit_count': len(commits)
            }
        
        return {
            'status': 'error',
            'error': 'Git log failed or no history found'
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


@safe
def find_regression_commit(
    test_or_symbol: str,
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Find the commit that introduced a regression or symbol."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        # Use git bisect to find regression (simplified version)
        # For now, just return the last few commits touching the symbol
        result = subprocess.run(
            ['git', 'log', '--oneline', '-S', test_or_symbol, '-10'],
            cwd=str(path),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            commits = []
            for line in result.stdout.strip().splitlines():
                if line:
                    parts = line.split(' ', 1)
                    commits.append({
                        'hash': parts[0],
                        'message': parts[1] if len(parts) > 1 else ''
                    })
            
            return {
                'status': 'ok',
                'test_or_symbol': test_or_symbol,
                'candidate_commits': commits,
                'note': 'Simplified - full regression detection requires git bisect'
            }
        
        return {
            'status': 'not_found',
            'message': 'No commits found'
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def _load_recent_commit_hashes(path: Path, limit: int = 20) -> list:
    """Load the last N commit hashes from git log."""
    result = subprocess.run(
        ['git', 'log', f'-{limit}', '--format=%H'],
        cwd=str(path),
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def _load_commit_metadata(path: Path, commit_hash: str) -> dict:
    """Load metadata for a single commit."""
    result = subprocess.run(
        [
            'git', 'show', '-s',
            '--format=%H%x00%P%x00%an%x00%aI%x00%s',
            commit_hash
        ],
        cwd=str(path),
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        return {}

    parts = result.stdout.strip().split('\x00', 4)
    if len(parts) < 5:
        return {}

    return {
        'hash': parts[0],
        'parent_hashes': parts[1],
        'author': parts[2],
        'date': parts[3],
        'message': parts[4]
    }


def _load_commit_files(path: Path, commit_hash: str) -> dict:
    """Load file changes and stats for a single commit."""
    # Get name-status
    files_result = subprocess.run(
        ['git', 'diff-tree', '--root', '--no-commit-id', '--name-status', '-r', '-M', '-z', commit_hash],
        cwd=str(path),
        capture_output=True,
        text=False,
        check=False
    )

    changed_files = {}
    if files_result.returncode == 0:
        tokens = files_result.stdout.decode('utf-8', errors='replace').split('\x00')
        i = 0
        while i < len(tokens):
            status = tokens[i]
            i += 1

            if not status:
                continue

            if status.startswith(('R', 'C')):
                if i + 1 < len(tokens):
                    old_path = tokens[i]
                    new_path = tokens[i + 1]
                    i += 2
                    changed_files[new_path] = {
                        'status': 'renamed' if status.startswith('R') else 'copied',
                        'old_path': old_path,
                        'additions': 0,
                        'deletions': 0
                    }
            else:
                if i < len(tokens):
                    file_path = tokens[i]
                    i += 1
                    status_map = {
                        'A': 'added',
                        'M': 'modified',
                        'D': 'deleted',
                        'T': 'type_changed'
                    }
                    changed_files[file_path] = {
                        'status': status_map.get(status, 'unknown'),
                        'old_path': None,
                        'additions': 0,
                        'deletions': 0
                    }

    # Get numstat
    numstat_result = subprocess.run(
        ['git', 'diff-tree', '--root', '--no-commit-id', '--numstat', '-r', '-M', '-z', commit_hash],
        cwd=str(path),
        capture_output=True,
        text=False,
        check=False
    )

    if numstat_result.returncode == 0:
        tokens = numstat_result.stdout.decode('utf-8', errors='replace').split('\x00')
        i = 0
        while i < len(tokens):
            record = tokens[i]
            i += 1

            if not record:
                continue

            parts_record = record.split('\t', 2)
            if len(parts_record) < 3:
                continue

            additions_str, deletions_str, file_path = parts_record

            if file_path == '':
                if i + 1 < len(tokens):
                    old_path = tokens[i]
                    new_path = tokens[i + 1]
                    i += 2
                    file_path = new_path
            else:
                new_path = file_path

            additions = 0 if additions_str == '-' else int(additions_str)
            deletions = 0 if deletions_str == '-' else int(deletions_str)

            if new_path in changed_files:
                changed_files[new_path]['additions'] = additions
                changed_files[new_path]['deletions'] = deletions

    return changed_files


def _load_recent_commits(path: Path, graph, limit: int = 20) -> list:
    """Load recent commits with full structure."""
    commit_hashes = _load_recent_commit_hashes(path, limit)
    commits = []

    for commit_hash in commit_hashes:
        metadata = _load_commit_metadata(path, commit_hash)
        if not metadata:
            continue

        # Store first parent hash for ordinary history navigation
        parent_hashes = metadata['parent_hashes'].split()
        first_parent = parent_hashes[0] if parent_hashes else None

        changed_files = _load_commit_files(path, commit_hash)

        # Convert to list format
        files_list = []
        total_additions = 0
        total_deletions = 0

        for file_path, file_info in changed_files.items():
            files_list.append({
                'path': file_path,
                'old_path': file_info['old_path'],
                'status': file_info['status'],
                'additions': file_info['additions'],
                'deletions': file_info['deletions'],
                'mapped_node_ids': []
            })
            total_additions += file_info['additions']
            total_deletions += file_info['deletions']

        # Map to graph nodes - include ALL matching nodes
        mapped_node_ids = []
        for file_info in files_list:
            file_path = file_info['path']
            norm_commit_path = file_path
            for node_id, node in graph._nodes.items():
                node_file = node.get('file', '')
                if node_file:
                    if norm_commit_path in node_file or node_file in norm_commit_path:
                        if node_id not in mapped_node_ids:
                            mapped_node_ids.append(node_id)
                        if node_id not in file_info['mapped_node_ids']:
                            file_info['mapped_node_ids'].append(node_id)

        commits.append({
            'hash': metadata['hash'],
            'parent_hash': first_parent,
            'message': metadata['message'],
            'author': metadata['author'],
            'date': metadata['date'],
            'additions': total_additions,
            'deletions': total_deletions,
            'file_count': len(files_list),
            'files': files_list,
            'mapped_node_ids': mapped_node_ids,
            'mapping_status': 'partial' if mapped_node_ids else 'file_level'
        })

    return commits


@safe
def visualize_git_history(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Visualize git history with recent commits and file changes.

    Uses robust Git record parsing to avoid delimiter issues.
    Retrieves commit metadata and file changes separately.
    """
    try:
        from .visualization_spatial_tools import _emit_command
        from ..intelligence.graph_engine.codegraph import codegraph

        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)

        graph = codegraph.load_current_graph()

        # Use the testable helpers
        commits = _load_recent_commits(path, graph, limit=20)

        # Emit history panel command with full structured commits
        _emit_command(tool_context, 'show_history_panel',
                     summary=f"{len(commits)} recent commits",
                     commits=commits)

        return {
            'status': 'ok',
            'repository_path': str(path),
            'commits': commits,
            'commit_count': len(commits)
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


@safe
def analyze_commit_impact(
    commit_hash: str,
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze the impact of a commit with structured data."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)

        # Get commit diff with structured data
        result = subprocess.run(
            ['git', 'show', '--numstat', '--format=', commit_hash],
            cwd=str(path),
            capture_output=True,
            text=True
        )

        files_changed = []
        additions = 0
        deletions = 0

        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line:
                    parts = line.split()
                    if len(parts) >= 3:
                        file_path = parts[2]
                        adds = int(parts[0]) if parts[0].isdigit() else 0
                        dels = int(parts[1]) if parts[1].isdigit() else 0
                        files_changed.append({
                            'path': file_path,
                            'additions': adds,
                            'deletions': dels
                        })
                        additions += adds
                        deletions += dels

        return {
            'status': 'ok',
            'commit_hash': commit_hash,
            'repository_path': str(path),
            'files_changed': files_changed,
            'file_count': len(files_changed),
            'total_additions': additions,
            'total_deletions': deletions
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_file_history(
    file_path: str,
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Trace the history of a file."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        result = subprocess.run(
            ['git', 'log', '--follow', '--format=%H|%s|%an|%ad', '--', file_path],
            cwd=str(path),
            capture_output=True,
            text=True
        )
        
        history = []
        for line in result.stdout.splitlines():
            parts = line.split('|')
            if len(parts) >= 4:
                history.append({
                    'hash': parts[0],
                    'message': parts[1],
                    'author': parts[2],
                    'date': parts[3]
                })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'repository_path': str(path),
            'history': history
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
