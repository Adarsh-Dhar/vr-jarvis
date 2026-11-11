"""
Agent 10 - Software Engineering Tools
The ability to actually work on the project.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import subprocess
import os
import shutil
import time
from google.adk.tools import ToolContext
from ._safe import safe
from ._common import heuristic, repo_root, resolve_in_repo


def _safe_worktree_path(file_path, worktree):
    """Resolve file_path inside the sandbox worktree. Rejects escapes, .git, and node_modules (which is a
    symlink to the MAIN checkout's node_modules, so a write there would leave the sandbox)."""
    path = resolve_in_repo(file_path, root=Path(worktree))
    rel = path.resolve().relative_to(Path(worktree).resolve())
    if rel.parts and rel.parts[0] in ('.git', 'node_modules'):
        raise ValueError('Path is not writable in the sandbox: ' + str(file_path))
    return path


def _verification_stale(tool_context):
    """Any change to the worktree invalidates earlier test/typecheck/review evidence."""
    tool_context.state['last_test_run'] = {}
    tool_context.state['last_typecheck'] = {}
    tool_context.state['code_review'] = {}


# File Editing Tools

@safe
def edit_file(
    file_path: str,
    old_content: str,
    new_content: str,
    tool_context: ToolContext
) -> dict:
    """Modify existing files in the worktree. Requires create_worktree to be called first."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
        
        path = _safe_worktree_path(file_path, worktree)
        
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
        _verification_stale(tool_context)
        
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
    """Apply code patches in the worktree. Requires create_worktree to be called first."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
        
        from .git_tools import _bad_diff_path
        bad = _bad_diff_path(patch_content)
        if bad:
            return {'status': 'error', 'error': 'Patch touches a path that is not allowed: ' + bad}
        result = subprocess.run(
            ['git', 'apply', '--whitespace=nowarn', '-'],
            input=patch_content,
            capture_output=True,
            text=True,
            cwd=worktree
        )
        if result.returncode == 0:
            _verification_stale(tool_context)
            return {
                'status': 'ok',
                'patch_length': len(patch_content),
                'applied': True,
                'method': 'git_apply'
            }
        # No `patch -p1` fallback: it applies hunks partially and bypasses the path check.
        
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
def search_and_replace(
    file_pattern: str,
    search: str,
    replace: str,
    tool_context: ToolContext
) -> dict:
    """Perform controlled replacements in the worktree. Requires create_worktree to be called first."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
        
        cwd = Path(worktree)
        files_affected = 0
        total_replacements = 0
        
        if Path(file_pattern).is_absolute() or '..' in Path(file_pattern).parts:
            return {'status': 'error', 'error': 'file_pattern must be relative and stay inside the worktree.'}
        root = cwd.resolve()
        for file_path in cwd.rglob(file_pattern):
            if file_path.is_file() and not file_path.is_symlink():
                try:
                    rel = file_path.resolve().relative_to(root)
                except ValueError:
                    continue
                if rel.parts and rel.parts[0] in ('.git', 'node_modules'):
                    continue
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
        
        if files_affected:
            _verification_stale(tool_context)
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
    """Format source code in the worktree. Requires create_worktree to be called first."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
        
        path = _safe_worktree_path(file_path, worktree)
        
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
                _verification_stale(tool_context)
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
    """Organize imports in the worktree. Requires create_worktree to be called first."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
        
        path = _safe_worktree_path(file_path, worktree)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        # Try isort for Python files
        if path.suffix == '.py':
            result = subprocess.run(['isort', str(path)], capture_output=True, text=True)
            if result.returncode == 0:
                _verification_stale(tool_context)
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


@safe
def record_task_targets(
    confirmed_targets: Optional[List[str]] = None,
    rejected_targets: Optional[List[Dict[str, str]]] = None,
    tool_context: ToolContext = None
) -> dict:
    """Record which files the coding agent actually confirmed or rejected for
    the active plan task. suggested_files in the task are only hints; call this
    after inspecting the source so the task record reflects reality. Requires
    an active_task in session state (set when the ask came via WORK ON IT)."""
    state = getattr(tool_context, 'state', None) or {}
    if not state.get('active_task_id') and not state.get('active_task'):
        return {'status': 'error',
                'error': 'No active plan task. record_task_targets only applies '
                         'to asks sent with a task_id (WORK ON IT).'}
    confirmed = [str(f) for f in (confirmed_targets or [])]
    rejected = [{'file': str(r.get('file') or ''), 'reason': str(r.get('reason') or '')}
                for r in (rejected_targets or []) if isinstance(r, dict)]
    state['task_targets'] = {'confirmed_targets': confirmed,
                             'rejected_targets': rejected}
    return {'status': 'ok', 'confirmed_targets': confirmed,
            'rejected_targets': rejected}


# Terminal and Build Tools

@safe
def git_status(repository_path: str, tool_context: ToolContext) -> dict:
    """Get git status."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
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
            path = resolve_in_repo(path)
        
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
def git_branch(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """List branches."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
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
@heuristic('Skeleton only, not a behaviour-grounded implementation.')
def generate_function(
    description: str,
    tool_context: ToolContext,
    signature: Optional[str] = None
) -> dict:
    """Generate function template in the worktree. Requires create_worktree to be called first."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
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
@heuristic('Skeleton only, not a behaviour-grounded implementation.')
def generate_class(
    description: str,
    tool_context: ToolContext,
    class_name: Optional[str] = None
) -> dict:
    """Generate class template in the worktree. Requires create_worktree to be called first."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
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
@heuristic('Produces a plan; does not perform the refactor.')
def extract_function(
    code_range: Dict,
    function_name: str,
    tool_context: ToolContext
) -> dict:
    """Extract function in the worktree. Requires create_worktree to be called first."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
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
@heuristic('Produces a plan; does not perform the refactor.')
def rename_symbol(
    old_name: str,
    new_name: str,
    scope: str,
    tool_context: ToolContext
) -> dict:
    """Rename symbol in the worktree. Requires create_worktree to be called first."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
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
