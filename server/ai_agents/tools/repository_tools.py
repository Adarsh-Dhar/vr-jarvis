"""
Repository Access Tools - Shared Superpowers (Part A)
These tools allow agents to discover, load, explore, and monitor repositories.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import os
import subprocess
from datetime import datetime
from google.adk.tools import ToolContext
from ._safe import safe


# Language detection by file extension
LANGUAGE_MAP = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.jsx': 'javascript',
    '.java': 'java',
    '.kt': 'kotlin',
    '.go': 'go',
    '.rs': 'rust',
    '.cpp': 'cpp',
    '.c': 'c',
    '.h': 'c',
    '.hpp': 'cpp',
    '.cs': 'csharp',
    '.php': 'php',
    '.rb': 'ruby',
    '.swift': 'swift',
    '.scala': 'scala',
    '.lua': 'lua',
    '.r': 'r',
    '.m': 'objective-c',
    '.sh': 'shell',
    '.sql': 'sql',
    '.html': 'html',
    '.css': 'css',
    '.scss': 'scss',
    '.sass': 'sass',
    '.less': 'less',
    '.json': 'json',
    '.xml': 'xml',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.toml': 'toml',
    '.md': 'markdown',
    '.txt': 'text',
}


@safe
def list_repositories(tool_context: ToolContext) -> dict:
    """Discover all available repositories in the workspace."""
    try:
        # Get workspace from tool context or use current directory
        workspace = Path.cwd()
        repositories = []
        
        # Scan for .git directories to find repositories
        for root, dirs, files in os.walk(workspace):
            if '.git' in dirs:
                repo_path = Path(root)
                # Detect primary language by checking file extensions
                languages = set()
                for file in repo_path.rglob('*'):
                    if file.is_file():
                        ext = file.suffix.lower()
                        if ext in LANGUAGE_MAP:
                            languages.add(LANGUAGE_MAP[ext])
                
                repositories.append({
                    'path': str(repo_path),
                    'name': repo_path.name,
                    'language': list(languages)[0] if languages else 'unknown'
                })
                # Don't traverse into nested git repos
                dirs.remove('.git')
        
        return {
            'status': 'ok',
            'repositories': repositories
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def open_repository(repository_path: str, tool_context: ToolContext) -> dict:
    """Load a repository for analysis."""
    try:
        repo_path = Path(repository_path)
        if not repo_path.exists():
            return {
                'status': 'error',
                'error': f'Repository path does not exist: {repository_path}'
            }
        
        # Get git information if available
        branch = 'unknown'
        commit = 'unknown'
        languages = set()
        
        if (repo_path / '.git').exists():
            try:
                # Get current branch
                result = subprocess.run(
                    ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    branch = result.stdout.strip()
                
                # Get current commit
                result = subprocess.run(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    commit = result.stdout.strip()
            except Exception:
                pass
        
        # Detect languages
        for file in repo_path.rglob('*'):
            if file.is_file():
                ext = file.suffix.lower()
                if ext in LANGUAGE_MAP:
                    languages.add(LANGUAGE_MAP[ext])
        
        return {
            'status': 'ok',
            'repository': {
                'path': str(repo_path),
                'branch': branch,
                'commit': commit,
                'languages': list(languages)
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def list_files(
    tool_context: ToolContext,
    directory: str = '.',
    recursive: bool = True,
    pattern: Optional[str] = None
) -> dict:
    """Explore directory and file structures."""
    try:
        dir_path = Path(directory)
        if not dir_path.is_absolute():
            dir_path = Path.cwd() / dir_path
        
        if not dir_path.exists():
            return {
                'status': 'error',
                'error': f'Directory does not exist: {directory}'
            }
        
        files = []
        
        if recursive:
            for item in dir_path.rglob('*'):
                if pattern is None or pattern in item.name:
                    files.append({
                        'path': str(item.relative_to(dir_path)),
                        'type': 'directory' if item.is_dir() else 'file',
                        'size': item.stat().st_size if item.is_file() else 0
                    })
        else:
            for item in dir_path.iterdir():
                if pattern is None or pattern in item.name:
                    files.append({
                        'path': str(item.relative_to(dir_path)),
                        'type': 'directory' if item.is_dir() else 'file',
                        'size': item.stat().st_size if item.is_file() else 0
                    })
        
        return {
            'status': 'ok',
            'directory': str(dir_path),
            'files': files
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def read_file(file_path: str, tool_context: ToolContext) -> dict:
    """Read source files."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File does not exist: {file_path}'
            }
        
        if not path.is_file():
            return {
                'status': 'error',
                'error': f'Path is not a file: {file_path}'
            }
        
        # Read file content with error handling for encoding
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Try with different encoding
            content = path.read_text(encoding='latin-1')
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'content': content
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def read_file_range(
    file_path: str,
    start_line: int,
    end_line: int,
    tool_context: ToolContext
) -> dict:
    """Read specific line ranges from a file."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File does not exist: {file_path}'
            }
        
        # Read file and extract line range
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding='latin-1').splitlines()
        
        # Adjust for 1-based indexing
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        
        content_lines = lines[start_idx:end_idx]
        content = '\n'.join(content_lines)
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'start_line': start_line,
            'end_line': end_line,
            'content': content
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_files(
    tool_context: ToolContext,
    pattern: str,
    directory: str = '.',
    file_extension: Optional[str] = None
) -> dict:
    """Search files by name, extension or pattern."""
    try:
        dir_path = Path(directory)
        if not dir_path.is_absolute():
            dir_path = Path.cwd() / dir_path
        
        if not dir_path.exists():
            return {
                'status': 'error',
                'error': f'Directory does not exist: {directory}'
            }
        
        matches = []
        
        for item in dir_path.rglob('*'):
            if item.is_file():
                # Check file extension filter
                if file_extension:
                    if not item.suffix.lower().lstrip('.') == file_extension.lower():
                        continue
                
                # Check pattern in filename
                if pattern.lower() in item.name.lower():
                    matches.append({
                        'path': str(item.relative_to(dir_path)),
                        'name': item.name
                    })
        
        return {
            'status': 'ok',
            'pattern': pattern,
            'matches': matches
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_code(
    tool_context: ToolContext,
    query: str,
    file_pattern: Optional[str] = None
) -> dict:
    """Search source code across repositories."""
    try:
        # Use grep to search for code patterns
        cwd = Path.cwd()
        matches = []
        
        # Build grep command
        cmd = ['grep', '-rn', '--include=*.py', '--include=*.js', '--include=*.ts', '--include=*.java', '--include=*.go', '--include=*.rs', query, str(cwd)]
        
        if file_pattern:
            cmd = ['grep', '-rn', f'--include={file_pattern}', query, str(cwd)]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    file_path = parts[0]
                    line_num = parts[1]
                    snippet = parts[2].strip()
                    matches.append({
                        'file': file_path,
                        'line': int(line_num),
                        'snippet': snippet
                    })
        
        return {
            'status': 'ok',
            'query': query,
            'matches': matches
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_symbols(
    tool_context: ToolContext,
    symbol_name: str,
    symbol_type: Optional[str] = None
) -> dict:
    """Search functions, classes, variables and types."""
    try:
        # This is a placeholder - real implementation would use AST parsing or tree-sitter
        # For now, use grep to find symbol definitions
        cwd = Path.cwd()
        matches = []
        
        # Build patterns for different symbol types
        patterns = {
            'function': [r'def\s+\w+', r'function\s+\w+', r'fn\s+\w+'],
            'class': [r'class\s+\w+'],
            'variable': [r'\w+\s*=', r'let\s+\w+', r'const\s+\w+', r'var\s+\w+'],
        }
        
        search_patterns = patterns.get(symbol_type, patterns['function']) if symbol_type else patterns['function']
        
        for pattern in search_patterns:
            cmd = ['grep', '-rn', pattern, str(cwd)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if symbol_name.lower() in line.lower():
                        parts = line.split(':', 2)
                        if len(parts) >= 2:
                            file_path = parts[0]
                            line_num = parts[1]
                            matches.append({
                                'name': symbol_name,
                                'type': symbol_type or 'unknown',
                                'file': file_path,
                                'line': int(line_num)
                            })
        
        return {
            'status': 'ok',
            'symbol_name': symbol_name,
            'matches': matches
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_file_metadata(file_path: str, tool_context: ToolContext) -> dict:
    """Retrieve size, language, timestamps and other metadata."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File does not exist: {file_path}'
            }
        
        stat = path.stat()
        ext = path.suffix.lower()
        language = LANGUAGE_MAP.get(ext, 'unknown')
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'size': stat.st_size,
            'language': language,
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_repository_metadata(repository_path: str, tool_context: ToolContext) -> dict:
    """Retrieve branches, remotes, languages and project information."""
    try:
        repo_path = Path(repository_path)
        if not repo_path.is_absolute():
            repo_path = Path.cwd() / repo_path
        
        if not repo_path.exists():
            return {
                'status': 'error',
                'error': f'Repository path does not exist: {repository_path}'
            }
        
        branches = []
        remotes = []
        languages = {}
        
        # Get git information if available
        if (repo_path / '.git').exists():
            try:
                # Get branches
                result = subprocess.run(
                    ['git', 'branch', '-a'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    branches = [b.strip().replace('*', '').strip() for b in result.stdout.splitlines()]
                
                # Get remotes
                result = subprocess.run(
                    ['git', 'remote'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    remotes = result.stdout.strip().splitlines()
            except Exception:
                pass
        
        # Detect languages by file extension
        total_files = 0
        for file in repo_path.rglob('*'):
            if file.is_file():
                total_files += 1
                ext = file.suffix.lower()
                if ext in LANGUAGE_MAP:
                    lang = LANGUAGE_MAP[ext]
                    languages[lang] = languages.get(lang, 0) + 1
        
        # Convert to percentages
        if total_files > 0:
            languages = {lang: count / total_files for lang, count in languages.items()}
        
        return {
            'status': 'ok',
            'repository_path': str(repo_path),
            'branches': branches,
            'remotes': remotes,
            'languages': languages
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def watch_repository(repository_path: str, tool_context: ToolContext) -> dict:
    """Detect file additions, deletions and modifications."""
    try:
        repo_path = Path(repository_path)
        if not repo_path.is_absolute():
            repo_path = Path.cwd() / repo_path
        
        if not repo_path.exists():
            return {
                'status': 'error',
                'error': f'Repository path does not exist: {repository_path}'
            }
        
        # This is a placeholder - real implementation would use watchdog or fsnotify
        # For now, just return success
        return {
            'status': 'ok',
            'repository_path': str(repo_path),
            'watching': True,
            'note': 'Real file watching requires watchdog library integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_changed_files(
    tool_context: ToolContext,
    since_revision: str,
    repository_path: Optional[str] = None
) -> dict:
    """Identify modifications since a particular revision."""
    try:
        repo_path = Path(repository_path) if repository_path else Path.cwd()
        if not repo_path.is_absolute():
            repo_path = Path.cwd() / repo_path
        
        if not (repo_path / '.git').exists():
            return {
                'status': 'error',
                'error': f'Not a git repository: {repo_path}'
            }
        
        # Get changed files using git diff
        result = subprocess.run(
            ['git', 'diff', '--name-status', since_revision],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        
        changed_files = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.split('\t')
                if len(parts) >= 2:
                    status = parts[0]
                    path = parts[1]
                    changed_files.append({
                        'path': path,
                        'status': status
                    })
        
        return {
            'status': 'ok',
            'since_revision': since_revision,
            'changed_files': changed_files
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
