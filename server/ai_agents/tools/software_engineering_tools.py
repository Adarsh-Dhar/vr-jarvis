"""
Agent 10 - Software Engineering Tools
The ability to actually work on the project.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import subprocess
import os
import shutil
from google.adk.tools import ToolContext
from ._safe import safe


# File Editing Tools

@safe
def create_file(
    file_path: str,
    content: str,
    tool_context: ToolContext
) -> dict:
    """Create new files."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        path.write_text(content, encoding='utf-8')
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'created': True,
            'size': len(content)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def edit_file(
    file_path: str,
    old_content: str,
    new_content: str,
    tool_context: ToolContext
) -> dict:
    """Modify existing files."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        current_content = path.read_text(encoding='utf-8')
        
        if old_content not in current_content:
            return {
                'status': 'error',
                'error': 'Old content not found in file'
            }
        
        # Replace content
        updated_content = current_content.replace(old_content, new_content, 1)
        path.write_text(updated_content, encoding='utf-8')
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'edited': True,
            'changes': 1
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def apply_patch(
    patch_content: str,
    tool_context: ToolContext
) -> dict:
    """Apply code patches."""
    try:
        # Try git apply first
        result = subprocess.run(
            ['git', 'apply', '-'],
            input=patch_content,
            capture_output=True,
            text=True,
            cwd=str(Path.cwd())
        )
        
        if result.returncode == 0:
            return {
                'status': 'ok',
                'patch_length': len(patch_content),
                'applied': True,
                'method': 'git_apply'
            }
        
        # Fallback to patch command
        result = subprocess.run(
            ['patch', '-p1'],
            input=patch_content,
            capture_output=True,
            text=True,
            cwd=str(Path.cwd())
        )
        
        if result.returncode == 0:
            return {
                'status': 'ok',
                'patch_length': len(patch_content),
                'applied': True,
                'method': 'patch'
            }
        
        return {
            'status': 'error',
            'patch_length': len(patch_content),
            'applied': False,
            'error': result.stderr if result.stderr else 'Patch application failed'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def delete_file(
    file_path: str,
    tool_context: ToolContext
) -> dict:
    """Delete files with appropriate approval."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        # This is a destructive operation - in production, check approval
        path.unlink()
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'deleted': True,
            'note': 'Destructive operation should require approval in production'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def rename_file(
    old_path: str,
    new_path: str,
    tool_context: ToolContext
) -> dict:
    """Rename files."""
    try:
        old = Path(old_path)
        new = Path(new_path)
        
        if not old.is_absolute():
            old = Path.cwd() / old
        if not new.is_absolute():
            new = Path.cwd() / new
        
        if not old.exists():
            return {
                'status': 'error',
                'error': f'Source file not found: {old_path}'
            }
        
        old.rename(new)
        
        return {
            'status': 'ok',
            'old_path': str(old),
            'new_path': str(new),
            'renamed': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def move_file(
    source: str,
    destination: str,
    tool_context: ToolContext
) -> dict:
    """Move files."""
    try:
        src = Path(source)
        dst = Path(destination)
        
        if not src.is_absolute():
            src = Path.cwd() / src
        if not dst.is_absolute():
            dst = Path.cwd() / dst
        
        if not src.exists():
            return {
                'status': 'error',
                'error': f'Source file not found: {source}'
            }
        
        # Create destination directory if needed
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.move(str(src), str(dst))
        
        return {
            'status': 'ok',
            'source': str(src),
            'destination': str(dst),
            'moved': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def create_directory(directory_path: str, tool_context: ToolContext) -> dict:
    """Create directories."""
    try:
        path = Path(directory_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        path.mkdir(parents=True, exist_ok=True)
        
        return {
            'status': 'ok',
            'directory_path': str(path),
            'created': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_and_replace(
    file_pattern: str,
    search: str,
    replace: str,
    tool_context: ToolContext
) -> dict:
    """Perform controlled replacements."""
    try:
        cwd = Path.cwd()
        files_affected = 0
        total_replacements = 0
        
        for file_path in cwd.rglob(file_pattern):
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding='utf-8')
                    new_content = content.replace(search, replace)
                    
                    if new_content != content:
                        file_path.write_text(new_content, encoding='utf-8')
                        count = content.count(search)
                        total_replacements += count
                        files_affected += 1
                except Exception:
                    continue
        
        return {
            'status': 'ok',
            'file_pattern': file_pattern,
            'replacements': total_replacements,
            'files_affected': files_affected
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def format_code(
    file_path: str,
    tool_context: ToolContext,
    formatter: str = 'auto'
) -> dict:
    """Format source code."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        # Determine formatter based on file extension
        ext = path.suffix.lower()
        
        if formatter == 'auto':
            if ext == '.py':
                formatter = 'black'
            elif ext in ['.js', '.ts', '.jsx', '.tsx']:
                formatter = 'prettier'
            elif ext in ['.java']:
                formatter = 'google-java-format'
            else:
                formatter = 'auto'
        
        # Try to run formatter if available
        if formatter == 'black':
            result = subprocess.run(['black', str(path)], capture_output=True, text=True)
            if result.returncode == 0:
                return {
                    'status': 'ok',
                    'file_path': str(path),
                    'formatter': formatter,
                    'formatted': True
                }
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'formatter': formatter,
            'formatted': False,
            'note': f'Formatter {formatter} not available or not configured'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def organize_imports(
    file_path: str,
    tool_context: ToolContext
) -> dict:
    """Organize imports."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        # Try isort for Python files
        if path.suffix == '.py':
            result = subprocess.run(['isort', str(path)], capture_output=True, text=True)
            if result.returncode == 0:
                return {
                    'status': 'ok',
                    'file_path': str(path),
                    'imports_organized': True
                }
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'imports_organized': False,
            'note': 'Import organizer not available'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Terminal and Build Tools

@safe
def execute_command(
    command: str,
    tool_context: ToolContext,
    working_directory: Optional[str] = None
) -> dict:
    """Execute commands in terminal."""
    try:
        cwd = Path(working_directory) if working_directory else Path.cwd()
        
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return {
            'status': 'ok',
            'command': command,
            'working_directory': str(cwd),
            'exit_code': result.returncode,
            'stdout': result.stdout[-5000:] if result.stdout else '',
            'stderr': result.stderr[-5000:] if result.stderr else ''
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Command timed out after 30 seconds'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def execute_script(
    script_path: str,
    tool_context: ToolContext,
    arguments: Optional[List[str]] = None
) -> dict:
    """Execute scripts."""
    try:
        path = Path(script_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'Script not found: {script_path}'
            }
        
        cmd = ['python3', str(path)]
        if arguments:
            cmd.extend(arguments)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return {
            'status': 'ok',
            'script_path': str(path),
            'arguments': arguments,
            'exit_code': result.returncode,
            'output': result.stdout[-5000:] if result.stdout else '',
            'stderr': result.stderr[-5000:] if result.stderr else ''
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Script timed out after 60 seconds'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def install_dependency(
    package_name: str,
    tool_context: ToolContext,
    package_manager: str = 'auto'
) -> dict:
    """Install dependencies."""
    try:
        if package_manager == 'auto':
            # Try to detect package manager
            if Path('requirements.txt').exists() or Path('setup.py').exists() or Path('pyproject.toml').exists():
                package_manager = 'pip'
            elif Path('package.json').exists():
                package_manager = 'npm'
            elif Path('go.mod').exists():
                package_manager = 'go'
            else:
                package_manager = 'pip'
        
        if package_manager == 'pip':
            result = subprocess.run(['pip', 'install', package_name], capture_output=True, text=True)
        elif package_manager == 'npm':
            result = subprocess.run(['npm', 'install', package_name], capture_output=True, text=True)
        elif package_manager == 'go':
            result = subprocess.run(['go', 'get', package_name], capture_output=True, text=True)
        else:
            return {
                'status': 'error',
                'error': f'Unsupported package manager: {package_manager}'
            }
        
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'package_name': package_name,
            'package_manager': package_manager,
            'installed': result.returncode == 0,
            'output': result.stdout[-1000:] if result.stdout else result.stderr[-1000:]
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def remove_dependency(
    package_name: str,
    tool_context: ToolContext,
    package_manager: str = 'auto'
) -> dict:
    """Remove dependencies."""
    try:
        if package_manager == 'auto':
            package_manager = 'pip'
        
        if package_manager == 'pip':
            result = subprocess.run(['pip', 'uninstall', '-y', package_name], capture_output=True, text=True)
        elif package_manager == 'npm':
            result = subprocess.run(['npm', 'uninstall', package_name], capture_output=True, text=True)
        else:
            return {
                'status': 'error',
                'error': f'Unsupported package manager: {package_manager}'
            }
        
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'package_name': package_name,
            'package_manager': package_manager,
            'removed': result.returncode == 0,
            'output': result.stdout[-1000:] if result.stdout else result.stderr[-1000:]
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def run_compiler(
    source_files: List[str],
    tool_context: ToolContext,
    compiler: str = 'auto'
) -> dict:
    """Run compiler."""
    try:
        if not source_files:
            return {
                'status': 'error',
                'error': 'No source files provided'
            }
        
        # Detect language from first file
        first_file = Path(source_files[0])
        ext = first_file.suffix.lower()
        
        if compiler == 'auto':
            if ext == '.py':
                return {
                    'status': 'not_applicable',
                    'message': 'Python is interpreted, not compiled (use python3 to run)'
                }
            elif ext in ['.c', '.h']:
                compiler = 'gcc'
            elif ext in ['.cpp', '.hpp', '.cc']:
                compiler = 'g++'
            elif ext == '.java':
                compiler = 'javac'
            elif ext == '.go':
                compiler = 'go'
            elif ext == '.rs':
                compiler = 'rustc'
            else:
                compiler = 'auto'
        
        # Build command based on compiler
        if compiler == 'gcc':
            cmd = ['gcc'] + source_files + ['-o', 'output']
        elif compiler == 'g++':
            cmd = ['g++'] + source_files + ['-o', 'output']
        elif compiler == 'javac':
            cmd = ['javac'] + source_files
        elif compiler == 'go':
            cmd = ['go', 'build'] + source_files
        elif compiler == 'rustc':
            cmd = ['rustc'] + source_files
        else:
            return {
                'status': 'not_applicable',
                'message': f'Compiler {compiler} not configured'
            }
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()))
        
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'source_files': source_files,
            'compiler': compiler,
            'compiled': result.returncode == 0,
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def run_build(
    tool_context: ToolContext,
    build_config: Optional[str] = None
) -> dict:
    """Run build."""
    try:
        cwd = Path.cwd()
        
        # Detect build system
        if (cwd / 'package.json').exists():
            result = subprocess.run(['npm', 'run', 'build'], capture_output=True, text=True, cwd=str(cwd))
        elif (cwd / 'setup.py').exists() or (cwd / 'pyproject.toml').exists():
            result = subprocess.run(['python3', '-m', 'build'], capture_output=True, text=True, cwd=str(cwd))
        elif (cwd / 'Makefile').exists():
            result = subprocess.run(['make'], capture_output=True, text=True, cwd=str(cwd))
        elif (cwd / 'Cargo.toml').exists():
            result = subprocess.run(['cargo', 'build'], capture_output=True, text=True, cwd=str(cwd))
        else:
            return {
                'status': 'not_applicable',
                'message': 'No build system detected'
            }
        
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'build_config': build_config,
            'build_successful': result.returncode == 0,
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def run_linter(
    file_path: str,
    tool_context: ToolContext,
    linter: str = 'auto'
) -> dict:
    """Run linter."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        ext = path.suffix.lower()
        
        if linter == 'auto':
            if ext == '.py':
                linter = 'pylint'
            elif ext in ['.js', '.ts']:
                linter = 'eslint'
            else:
                linter = 'auto'
        
        if linter == 'pylint':
            result = subprocess.run(['pylint', str(path)], capture_output=True, text=True)
        elif linter == 'eslint':
            result = subprocess.run(['eslint', str(path)], capture_output=True, text=True)
        else:
            return {
                'status': 'not_applicable',
                'message': f'Linter {linter} not available'
            }
        
        # Parse output for issues
        issues = []
        if result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    issues.append({
                        'line': 0,
                        'severity': 'warning',
                        'message': line[:200]
                    })
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'linter': linter,
            'issues': issues[:20],
            'exit_code': result.returncode
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def run_formatter(
    file_path: str,
    tool_context: ToolContext,
    formatter: str = 'auto'
) -> dict:
    """Run formatter."""
    return format_code(file_path, tool_context, formatter)


@safe
def run_type_checker(
    file_path: str,
    tool_context: ToolContext,
    type_checker: str = 'auto'
) -> dict:
    """Run type checker."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        ext = path.suffix.lower()
        
        if type_checker == 'auto':
            if ext == '.py':
                type_checker = 'mypy'
            elif ext in ['.ts', '.tsx']:
                type_checker = 'tsc'
            else:
                type_checker = 'auto'
        
        if type_checker == 'mypy':
            result = subprocess.run(['mypy', str(path)], capture_output=True, text=True)
        elif type_checker == 'tsc':
            result = subprocess.run(['tsc', '--noEmit', str(path)], capture_output=True, text=True)
        else:
            return {
                'status': 'not_applicable',
                'message': f'Type checker {type_checker} not available'
            }
        
        # Parse output for errors
        type_errors = []
        if result.stdout or result.stderr:
            output = result.stdout + result.stderr
            for line in output.splitlines():
                if 'error' in line.lower():
                    type_errors.append({
                        'line': 0,
                        'message': line[:200]
                    })
        
        return {
            'status': 'ok',
            'file_path': str(path),
            'type_checker': type_checker,
            'type_errors': type_errors[:20],
            'exit_code': result.returncode
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_environment(tool_context: ToolContext) -> dict:
    """Inspect environment."""
    try:
        import sys
        import platform
        
        env_info = {
            'os': platform.system(),
            'os_version': platform.version(),
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'architecture': platform.machine(),
            'environment_variables': list(os.environ.keys())[:20]
        }
        
        # Check for Node.js
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                env_info['node_version'] = result.stdout.strip()
        except:
            pass
        
        # Check for Git
        try:
            result = subprocess.run(['git', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                env_info['git_version'] = result.stdout.strip()
        except:
            pass
        
        return {
            'status': 'ok',
            'environment': env_info
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def manage_environment_variables(
    action: str,
    variables: Dict[str, str],
    tool_context: ToolContext
) -> dict:
    """Manage environment variables."""
    try:
        if action == 'set':
            for key, value in variables.items():
                os.environ[key] = value
            return {
                'status': 'ok',
                'action': action,
                'variables': list(variables.keys()),
                'updated': True
            }
        elif action == 'get':
            values = {k: os.environ.get(k) for k in variables.keys()}
            return {
                'status': 'ok',
                'action': action,
                'variables': values
            }
        elif action == 'unset':
            for key in variables.keys():
                os.environ.pop(key, None)
            return {
                'status': 'ok',
                'action': action,
                'variables': list(variables.keys()),
                'updated': True
            }
        else:
            return {
                'status': 'error',
                'error': f'Unknown action: {action}'
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def manage_processes(
    action: str,
    tool_context: ToolContext,
    process_id: Optional[str] = None
) -> dict:
    """Manage processes."""
    try:
        if action == 'list':
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            return {
                'status': 'ok',
                'action': action,
                'processes': result.stdout[-2000:] if result.returncode == 0 else 'Error listing processes'
            }
        elif action == 'kill' and process_id:
            result = subprocess.run(['kill', process_id], capture_output=True, text=True)
            return {
                'status': 'ok' if result.returncode == 0 else 'error',
                'action': action,
                'process_id': process_id,
                'result': 'killed' if result.returncode == 0 else 'failed'
            }
        else:
            return {
                'status': 'error',
                'error': f'Unknown action or missing process_id: {action}'
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def inspect_command_output(
    command_id: str,
    tool_context: ToolContext
) -> dict:
    """Inspect command output."""
    try:
        # Try to find recent command output from subprocess results
        # This is a simplified implementation - production would use command state tracking
        import subprocess
        
        # If command_id looks like a command, try to run it and capture output
        if command_id and not command_id.startswith('cmd_'):
            try:
                result = subprocess.run(
                    command_id,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return {
                    'status': 'ok',
                    'command_id': command_id,
                    'command': command_id,
                    'exit_code': result.returncode,
                    'stdout': result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
                    'stderr': result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
                    'executed': True
                }
            except Exception:
                pass
        
        return {
            'status': 'ok',
            'command_id': command_id,
            'output': None,
            'note': 'Command output tracking requires command state management - provided command_id for reference'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Git Tools (extending existing git_tools.py)

@safe
def git_status(repository_path: str, tool_context: ToolContext) -> dict:
    """Get git status."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(['git', 'status', '--porcelain'], cwd=str(path), capture_output=True, text=True)
        
        modified = []
        untracked = []
        
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line:
                    status = line[0]
                    file = line[3:]
                    if status in ['M', 'M ']:
                        modified.append(file)
                    elif status == '??':
                        untracked.append(file)
        
        # Get current branch
        branch_result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=str(path), capture_output=True, text=True)
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else 'unknown'
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'branch': branch,
            'modified': modified,
            'untracked': untracked
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def git_diff(
    repository_path: str,
    tool_context: ToolContext,
    file_path: Optional[str] = None
) -> dict:
    """Get git diff."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        cmd = ['git', 'diff']
        if file_path:
            cmd.append(file_path)
        
        result = subprocess.run(cmd, cwd=str(path), capture_output=True, text=True)
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'file_path': file_path,
            'diff': result.stdout[-5000:] if result.stdout else '',
            'exit_code': result.returncode
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def git_log(
    repository_path: str,
    tool_context: ToolContext,
    limit: int = 10
) -> dict:
    """Get git log."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(
            ['git', 'log', f'-{limit}', '--pretty=format:%H|%s|%an|%ad', '--date=short'],
            cwd=str(path),
            capture_output=True,
            text=True
        )
        
        commits = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
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
            'repository_path': str(path),
            'commits': commits
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def git_show(
    repository_path: str,
    commit_hash: str,
    tool_context: ToolContext
) -> dict:
    """Show commit details."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(['git', 'show', commit_hash], cwd=str(path), capture_output=True, text=True)
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'commit_hash': commit_hash,
            'details': result.stdout[-5000:] if result.stdout else '',
            'exit_code': result.returncode
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def git_branch(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """List branches."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(['git', 'branch', '-a'], cwd=str(path), capture_output=True, text=True)
        
        branches = []
        current = None
        
        if result.returncode == 0:
            # Get current branch
            current_result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=str(path), capture_output=True, text=True)
            current = current_result.stdout.strip() if current_result.returncode == 0 else None
            
            for line in result.stdout.splitlines():
                branch = line.strip().replace('*', '').strip()
                if branch:
                    branches.append(branch)
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'branches': branches,
            'current': current
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def git_create_branch(
    repository_path: str,
    branch_name: str,
    tool_context: ToolContext
) -> dict:
    """Create branch."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(['git', 'checkout', '-b', branch_name], cwd=str(path), capture_output=True, text=True)
        
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'repository_path': str(path),
            'branch_name': branch_name,
            'created': result.returncode == 0,
            'output': result.stdout if result.stdout else result.stderr
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def git_commit(
    repository_path: str,
    message: str,
    tool_context: ToolContext
) -> dict:
    """Commit changes."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(['git', 'commit', '-m', message], cwd=str(path), capture_output=True, text=True)
        
        # Get commit hash
        hash_result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(path), capture_output=True, text=True)
        commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else None
        
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'repository_path': str(path),
            'message': message,
            'commit_hash': commit_hash,
            'committed': result.returncode == 0
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def git_stash(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Stash changes."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(['git', 'stash'], cwd=str(path), capture_output=True, text=True)
        
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'repository_path': str(path),
            'stashed': result.returncode == 0,
            'output': result.stdout if result.stdout else result.stderr
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def git_revert(
    repository_path: str,
    commit_hash: str,
    tool_context: ToolContext
) -> dict:
    """Revert commit."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(['git', 'revert', '--no-commit', commit_hash], cwd=str(path), capture_output=True, text=True)
        
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'repository_path': str(path),
            'commit_hash': commit_hash,
            'reverted': result.returncode == 0,
            'output': result.stdout if result.stdout else result.stderr
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def git_blame(
    repository_path: str,
    file_path: str,
    line: int,
    tool_context: ToolContext
) -> dict:
    """Get git blame."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(['git', 'blame', '-L', f'{line},{line}', file_path], cwd=str(path), capture_output=True, text=True)
        
        # Parse blame output
        parts = result.stdout.split() if result.returncode == 0 else []
        commit = parts[0] if parts else None
        author = ' '.join(parts[1:3]) if len(parts) > 2 else 'unknown'
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'file_path': file_path,
            'line': line,
            'author': author,
            'commit': commit,
            'output': result.stdout[-500:] if result.stdout else ''
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def git_create_checkpoint(
    repository_path: str,
    label: str,
    tool_context: ToolContext
) -> dict:
    """Create checkpoint."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Create a tag as a checkpoint
        checkpoint_id = f"checkpoint_{int(time.time())}_{label.replace(' ', '_')}"
        result = subprocess.run(['git', 'tag', checkpoint_id], cwd=str(path), capture_output=True, text=True)
        
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'repository_path': str(path),
            'label': label,
            'checkpoint_id': checkpoint_id,
            'created': result.returncode == 0
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Implementation Tools

@safe
def generate_function(
    description: str,
    tool_context: ToolContext,
    signature: Optional[str] = None
) -> dict:
    """Generate function."""
    try:
        # Generate a template based on description analysis
        import re
        
        # Extract key words from description
        desc_lower = description.lower()
        
        if signature:
            code = f"{signature}\n    \"\"\"{description}\"\"\"\n    # Implementation required based on the description\n    pass"
        else:
            # Infer function name from description
            func_name = re.sub(r'[^a-z0-9_]', '_', desc_lower.split()[0] if desc_lower else 'generated_function')
            code = f"def {func_name}():\n    \"\"\"{description}\"\"\"\n    # Implementation required based on the description\n    pass"
        
        return {
            'status': 'ok',
            'description': description,
            'generated_code': code,
            'language': 'python',
            'template': True,
            'note': 'Template generated - full implementation requires LLM integration or manual completion'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_class(
    description: str,
    tool_context: ToolContext,
    class_name: Optional[str] = None
) -> dict:
    """Generate class."""
    try:
        import re
        name = class_name or 'GeneratedClass'
        
        # Generate class template with init method
        code = f"""class {name}:
    \"\"\"{description}\"\"\"
    
    def __init__(self):
        self.name = name
        # Initialize attributes based on description
        
    def method(self):
        \"\"\"Implement method based on description\"\"\"
        pass
"""
        
        return {
            'status': 'ok',
            'description': description,
            'generated_code': code,
            'language': 'python',
            'template': True,
            'note': 'Template generated - full implementation requires LLM integration or manual completion'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_module(
    description: str,
    tool_context: ToolContext,
    module_name: Optional[str] = None
) -> dict:
    """Generate module."""
    try:
        name = module_name or 'generated_module'
        code = f"""# Module: {name}
# Description: {description}

\"\"\"Module for {description}\"\"\"

from typing import Optional, List, Dict, Any


class {name.capitalize()}:
    \"\"\"Main class for {description}\"\"\"
    
    def __init__(self):
        self.config = {{}}
    
    def process(self, data: Any) -> Any:
        \"\"\"Process data based on module purpose\"\"\"
        # Implementation required
        return data


def main():
    \"\"\"Main entry point\"\"\"
    pass


if __name__ == '__main__':
    main()
"""
        
        return {
            'status': 'ok',
            'description': description,
            'generated_code': code,
            'language': 'python',
            'template': True,
            'note': 'Template generated - full implementation requires LLM integration or manual completion'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_api(
    description: str,
    endpoints: List[Dict],
    tool_context: ToolContext
) -> dict:
    """Generate API."""
    try:
        code = f"# API: {description}\n# Endpoints: {len(endpoints)}\n"
        for endpoint in endpoints:
            code += f"# {endpoint}\n"
        
        return {
            'status': 'ok',
            'description': description,
            'generated_code': code,
            'endpoints': endpoints,
            'note': 'Real code generation requires LLM integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_database_model(
    description: str,
    tool_context: ToolContext,
    schema: Optional[Dict] = None
) -> dict:
    """Generate database model."""
    try:
        import re
        model_name = re.sub(r'[^a-zA-Z0-9_]', '', description.split()[0] if description else 'Model')
        model_name = model_name.capitalize()
        
        code = f"""# Database Model: {description}
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime


class {model_name}:
    \"\"\"Model for {description}\"\"\"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<{model_name}(id={{self.id}}, name={{self.name}})>"
"""
        
        if schema:
            code += f"\n# Schema provided: {schema}\n"
        
        return {
            'status': 'ok',
            'description': description,
            'generated_code': code,
            'schema': schema,
            'template': True,
            'note': 'Template generated - full implementation requires LLM integration or manual completion'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_component(
    description: str,
    component_type: str,
    tool_context: ToolContext
) -> dict:
    """Generate component."""
    try:
        import re
        comp_name = re.sub(r'[^a-zA-Z0-9_]', '', description.split()[0] if description else 'Component')
        comp_name = comp_name.capitalize()
        
        code = f"""# Component: {component_type}
# Description: {description}

class {comp_name}:
    \"\"\"{description}\"\"\"
    
    def __init__(self):
        self.state = {{}}
    
    def render(self):
        \"\"\"Render component\"\"\"
        pass
    
    def update(self, data):
        \"\"\"Update component state\"\"\"
        pass
"""
        
        return {
            'status': 'ok',
            'description': description,
            'component_type': component_type,
            'generated_code': code,
            'template': True,
            'note': 'Template generated - full implementation requires LLM integration or manual completion'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def refactor_function(
    function_id: str,
    refactoring_type: str,
    tool_context: ToolContext
) -> dict:
    """Refactor function."""
    try:
        from .navigation_tools import get_symbol_definition
        from .repository_tools import read_file
        
        # Get function definition
        def_result = get_symbol_definition(function_id, tool_context)
        if def_result.get('status') != 'ok':
            return def_result
        
        file_path = def_result['definition']['file']
        
        # Read file
        file_result = read_file(file_path, tool_context)
        if file_result.get('status') != 'ok':
            return file_result
        
        # Analyze function and provide actionable refactoring steps
        content = file_result['content']
        
        # Basic analysis of the function
        line_count = len(content.splitlines())
        complexity_indicators = content.count('if ') + content.count('for ') + content.count('while ')
        
        refactoring_actions = []
        if line_count > 50:
            refactoring_actions.append('Consider splitting function into smaller methods')
        if complexity_indicators > 10:
            refactoring_actions.append('High complexity detected - consider simplifying logic')
        if 'TODO' in content or 'FIXME' in content:
            refactoring_actions.append('Function contains TODO/FIXME comments - address them')
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'refactoring_type': refactoring_type,
            'file_path': file_path,
            'analysis': {
                'line_count': line_count,
                'complexity_indicators': complexity_indicators
            },
            'suggested_actions': refactoring_actions,
            'refactoring_plan': refactoring_plans.get(refactoring_type, 'Generic refactoring'),
            'note': 'Static analysis provided - actual refactoring requires AST manipulation'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def extract_function(
    code_range: Dict,
    function_name: str,
    tool_context: ToolContext
) -> dict:
    """Extract function."""
    try:
        from .repository_tools import read_file
        
        file_path = code_range.get('file')
        start_line = code_range.get('start_line')
        end_line = code_range.get('end_line')
        
        if not file_path or not start_line or not end_line:
            return {
                'status': 'error',
                'error': 'Missing required parameters: file, start_line, end_line'
            }
        
        # Read the file
        file_result = read_file(file_path, tool_context)
        if file_result.get('status') != 'ok':
            return file_result
        
        content = file_result['content']
        lines = content.splitlines()
        
        # Extract the code range
        extracted_code = '\n'.join(lines[start_line-1:end_line])
        
        # Generate a function template
        new_function = f"def {function_name}():\n    # Extracted from lines {start_line}-{end_line}\n    {extracted_code}\n"
        
        return {
            'status': 'ok',
            'function_name': function_name,
            'code_range': code_range,
            'extracted_code': extracted_code,
            'suggested_function': new_function,
            'note': 'Actual extraction requires AST manipulation to preserve context'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def rename_symbol(
    old_name: str,
    new_name: str,
    scope: str,
    tool_context: ToolContext
) -> dict:
    """Rename symbol."""
    try:
        from .navigation_tools import get_symbol_references
        from .repository_tools import search_code
        
        # Find all references to the symbol
        ref_result = get_symbol_references(old_name, tool_context)
        
        if ref_result.get('status') != 'ok':
            return ref_result
        
        references = ref_result.get('references', [])
        
        # For now, provide a plan for renaming
        # Real implementation would use AST manipulation
        rename_plan = {
            'old_name': old_name,
            'new_name': new_name,
            'scope': scope,
            'files_to_modify': list(set([ref['file'] for ref in references])),
            'reference_count': len(references),
            'note': 'Actual renaming requires AST manipulation to ensure accuracy'
        }
        
        return {
            'status': 'ok',
            'rename_plan': rename_plan
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def update_references(
    symbol_id: str,
    new_location: str,
    tool_context: ToolContext
) -> dict:
    """Update references."""
    try:
        from .navigation_tools import get_symbol_references
        
        # Find all references to the symbol
        ref_result = get_symbol_references(symbol_id, tool_context)
        
        if ref_result.get('status') != 'ok':
            return ref_result
        
        references = ref_result.get('references', [])
        
        # For now, provide a plan for updating references
        # Real implementation would update import statements and symbol references
        update_plan = {
            'symbol_id': symbol_id,
            'new_location': new_location,
            'files_to_update': list(set([ref['file'] for ref in references])),
            'reference_count': len(references),
            'note': 'Actual reference updating requires AST manipulation'
        }
        
        return {
            'status': 'ok',
            'update_plan': update_plan
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def implement_interface(
    interface_id: str,
    class_name: str,
    tool_context: ToolContext
) -> dict:
    """Implement interface."""
    try:
        from .navigation_tools import get_symbol_definition
        from .relationship_intelligence_tools import find_interface_implementations
        
        # Get interface definition
        def_result = get_symbol_definition(interface_id, tool_context)
        
        # Check for existing implementations
        impl_result = find_interface_implementations(interface_id, tool_context)
        
        # Analyze interface to extract methods
        interface_methods = []
        if def_result.get('status') == 'ok':
            from .repository_tools import read_file
            file_result = read_file(def_result['definition']['file'], tool_context)
            if file_result.get('status') == 'ok':
                # Simple method extraction from the definition
                import ast
                try:
                    tree = ast.parse(file_result['content'])
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            interface_methods.append(node.name)
                except Exception:
                    pass
        
        # Generate implementation template with methods
        if interface_methods:
            method_stubs = '\n'.join([f"    def {method}(self): pass" for method in interface_methods])
            template = f"class {class_name}:\n    \"\"\"Implementation of {interface_id}\"\"\"\n{method_stubs}\n"
        else:
            template = f"class {class_name}:\n    \"\"\"Implementation of {interface_id}\"\"\"\n    # TODO: Implement required methods\n    pass\n"
        
        return {
            'status': 'ok',
            'interface_id': interface_id,
            'class_name': class_name,
            'interface_methods': interface_methods,
            'template': template,
            'existing_implementations': impl_result.get('implementations', []) if impl_result.get('status') == 'ok' else [],
            'note': 'Template generated with method stubs - full implementation requires interface method signatures'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_documentation(
    element_id: str,
    tool_context: ToolContext,
    format: str = 'markdown'
) -> dict:
    """Generate documentation."""
    try:
        from .code_understanding_tools import generate_code_summary
        
        summary_result = generate_code_summary(element_id, tool_context)
        
        if summary_result.get('status') == 'ok':
            summary = summary_result.get('summary', '')
            key_points = summary_result.get('key_points', [])
            
            if format == 'markdown':
                doc = f"# {element_id}\n\n{summary}\n\n"
                if key_points:
                    doc += "## Key Points\n\n"
                    for point in key_points:
                        doc += f"- {point}\n"
            else:
                doc = summary
        
            return {
                'status': 'ok',
                'element_id': element_id,
                'format': format,
                'documentation': doc
            }
        
        return summary_result
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def apply_architecture_change(
    change_description: str,
    affected_components: List[str],
    tool_context: ToolContext
) -> dict:
    """Apply architecture change."""
    try:
        from .relationship_intelligence_tools import calculate_change_impact
        
        # Analyze impact for each component
        impact_analysis = []
        for component in affected_components:
            impact_result = calculate_change_impact(component, tool_context)
            if impact_result.get('status') == 'ok':
                impact_analysis.append({
                    'component': component,
                    'impact': impact_result.get('impact_level', 'unknown'),
                    'affected_count': impact_result.get('impact_score', 0)
                })
        
        # For now, provide a plan for the architecture change
        # Real implementation would coordinate multi-file changes
        change_plan = {
            'change_description': change_description,
            'affected_components': affected_components,
            'impact_analysis': impact_analysis,
            'steps': [
                'Analyze current architecture',
                'Identify breaking changes',
                'Update affected components',
                'Run tests to verify changes',
                'Document architectural changes'
            ],
            'note': 'Architecture changes require complex multi-file coordination and testing'
        }
        
        return {
            'status': 'ok',
            'change_plan': change_plan
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
