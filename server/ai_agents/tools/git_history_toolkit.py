"""
Specialist Toolkit C - Git and Development History
Understand how a codebase evolved.
"""

from typing import Optional, List, Dict, Any
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
            path = Path.cwd() / path
        
        # Use git blame to find introducing commit
        result = subprocess.run(
            ['git', 'log', '-S', '--format=%H', '--', symbol_id],
            cwd=str(path),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            commit_hash = result.stdout.strip().splitlines()[0]
            
            # Get commit details
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
                    'repository_path': str(path),
                    'commit': {
                        'hash': parts[0],
                        'message': parts[1],
                        'author': parts[2],
                        'date': parts[3]
                    }
                }
        
        return {
            'status': 'not_found',
            'symbol_id': symbol_id,
            'repository_path': repository_path,
            'message': 'Could not find introducing commit'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


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
            path = Path.cwd() / path
        
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
            path = Path.cwd() / path
        
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
