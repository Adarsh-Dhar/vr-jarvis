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
            ['git', 'log', '-S', '--format=%H', '--', symbol_id],
            cwd=str(path),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            commit_hash = result.stdout.strip().splitlines()[0]
            
            detail_result = subprocess.run(
                ['git', 'show', '--format=%H|%s|%an|%ad', commit_hash],
                cwd=str(path),
                capture_output=True,
                text=True
            )
            
            if detail_result.returncode == 0:
                parts = detail_result.stdout.strip().split('|')
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
    """Visualize git history with churn and author overlays."""
    try:
        from .visualization_spatial_tools import _emit_command
        from ..intelligence.graph_engine.codegraph import codegraph
        
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        graph = codegraph.load_current_graph()
        
        # Get git log for churn calculation
        result = subprocess.run(
            ['git', 'log', '--numstat', '--format='],
            cwd=str(path),
            capture_output=True,
            text=True
        )
        
        file_churn = {}
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line:
                    parts = line.split()
                    if len(parts) >= 3 and parts[0] != '-':
                        file_path = parts[2]
                        additions = int(parts[0]) if parts[0].isdigit() else 0
                        deletions = int(parts[1]) if parts[1].isdigit() else 0
                        file_churn[file_path] = additions + deletions
        
        # Add churn to graph nodes
        node_ids_with_churn = []
        for node_id, node in graph._nodes.items():
            file_path = node.get('file', '')
            if file_path in file_churn:
                node_ids_with_churn.append(node_id)
        
        # Highlight high-churn files
        _emit_command(tool_context, 'highlight_path', node_ids=node_ids_with_churn)
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'file_churn': file_churn,
            'high_churn_files': len(node_ids_with_churn)
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


@safe
def analyze_commit_impact(
    commit_hash: str,
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Analyze the impact of a commit."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        # Get commit diff
        result = subprocess.run(
            ['git', 'show', '--stat', commit_hash],
            cwd=str(path),
            capture_output=True,
            text=True
        )
        
        return {
            'status': 'ok',
            'commit_hash': commit_hash,
            'repository_path': str(path),
            'impact': result.stdout[-500:] if result.stdout else ''
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
