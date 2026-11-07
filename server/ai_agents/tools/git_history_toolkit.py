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

        # Get last 20 commits with metadata (robust parsing - avoid delimiter issues)
        result = subprocess.run(
            ['git', 'log', '-20', '--format=%H%x00%s%x00%an%x00%ad%x00'],
            cwd=str(path),
            capture_output=True,
            text=True
        )

        commits = []
        if result.returncode == 0:
            for commit_block in result.stdout.strip().split('\x00\x00'):
                if not commit_block:
                    continue
                parts = commit_block.split('\x00')
                if len(parts) >= 4:
                    commit_hash = parts[0]
                    message = parts[1]
                    author = parts[2]
                    date = parts[3]

                    # Get file changes for this commit separately
                    files_result = subprocess.run(
                        ['git', 'show', '--numstat', '--format=', commit_hash],
                        cwd=str(path),
                        capture_output=True,
                        text=True
                    )

                    changed_files = []
                    additions = 0
                    deletions = 0

                    if files_result.returncode == 0:
                        for line in files_result.stdout.strip().splitlines():
                            if line:
                                file_parts = line.split()
                                if len(file_parts) >= 3:
                                    file_path = file_parts[2]
                                    adds = int(file_parts[0]) if file_parts[0].isdigit() else 0
                                    dels = int(file_parts[1]) if file_parts[1].isdigit() else 0
                                    changed_files.append({
                                        'path': file_path,
                                        'additions': adds,
                                        'deletions': dels
                                    })
                                    additions += adds
                                    deletions += dels

                    commits.append({
                        'hash': commit_hash,
                        'message': message,
                        'author': author,
                        'date': date,
                        'files': changed_files,
                        'additions': additions,
                        'deletions': deletions,
                        'file_count': len(changed_files)
                    })

        # Map commits to current graph nodes (best-effort)
        for commit in commits:
            commit['mapped_nodes'] = []
            commit['mapped_files'] = []
            for file_info in commit['files']:
                file_path = file_info['path']
                # Try to find matching graph nodes
                for node_id, node in graph._nodes.items():
                    if node.get('file') == file_path:
                        commit['mapped_nodes'].append(node_id)
                        break
                if file_path not in commit['mapped_files']:
                    commit['mapped_files'].append(file_path)

        # Emit history panel command
        from .visualization_spatial_tools import _emit_command
        _emit_command(tool_context, 'show_history_panel',
                     summary=commits[0]['message'] if commits else "No commits",
                     node_ids=[c['hash'] for c in commits],
                     keep_ids=[f for c in commits for f in c.get('mapped_files', [])])

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
