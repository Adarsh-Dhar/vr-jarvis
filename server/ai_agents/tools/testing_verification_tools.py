"""
Agent 11 - Testing & Verification Tools
Establish whether the code works and whether changes have broken anything.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import subprocess
import re
import xml.etree.ElementTree as ET
from google.adk.tools import ToolContext
from ._common import heuristic, resolve_in_repo
from ._safe import safe


def _run_status(returncode, passed, failed, skipped):
    """Classify a pytest run. 'ok' requires exit 0 AND at least one real pass AND
    no failures. A zero-exit run where nothing passed (all skipped, or nothing
    collected) is 'unverified', never 'ok'. A non-zero exit with parsed results
    is 'failed'; a non-zero exit that produced nothing is 'unverified'."""
    if failed or (returncode != 0 and (passed or skipped)):
        return 'failed'
    if returncode != 0 or not passed:
        return 'unverified'
    return 'ok'


@safe
def discover_tests(
    repository_path: str,
    tool_context: ToolContext,
    test_framework: str = 'auto'
) -> dict:
    """Find existing tests."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'Repository not found: {repository_path}'
            }
        
        tests_found = []
        seen = set()

        def _add(test_file, kind):
            rel = str(test_file.relative_to(path))
            if rel in seen:
                return
            seen.add(rel)
            tests_found.append({'file': rel, 'name': test_file.stem, 'type': kind})

        # Check for common test directories
        test_dirs = ['tests', 'test', '__tests__', 'spec', 'specs']
        js_suffixes = ('.test.js', '.test.jsx', '.test.ts', '.test.tsx',
                       '.spec.js', '.spec.jsx', '.spec.ts', '.spec.tsx')
        for test_dir in test_dirs:
            test_path = path / test_dir
            if not test_path.is_dir():
                continue
            for test_file in test_path.rglob('*'):
                if not test_file.is_file():
                    continue
                name = test_file.name
                if name.startswith('test_') and name.endswith('.py') or name.endswith('_test.py'):
                    _add(test_file, 'unit')
                elif name.endswith(js_suffixes):
                    _add(test_file, 'unit')

        # Jest also keeps tests next to sources outside the classic test dirs.
        if (path / 'package.json').is_file():
            for test_file in path.rglob('*'):
                if test_file.is_file() and test_file.name.endswith(js_suffixes):
                    try:
                        test_file.relative_to(path)
                    except ValueError:
                        continue
                    parts = set(test_file.relative_to(path).parts)
                    if parts & {'node_modules', '.git'}:
                        continue
                    _add(test_file, 'unit')

        # Report the detected framework so callers know what can execute them.
        detected = 'unknown'
        pkg = path / 'package.json'
        if pkg.is_file():
            try:
                import json as _json
                blob = _json.dumps(_json.loads(pkg.read_text(errors='ignore'))).lower()
                if 'vitest' in blob:
                    detected = 'vitest'
                elif 'jest' in blob:
                    detected = 'jest'
            except Exception:
                pass
        if detected == 'unknown' and any(t['file'].endswith('.py') for t in tests_found):
            detected = 'pytest'
        if test_framework != 'auto':
            detected = test_framework

        return {
            'status': 'ok',
            'repository_path': str(path),
            'test_framework': detected,
            'tests_found': tests_found
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
@heuristic('pytest only.')
def run_unit_tests(
    tool_context: ToolContext,
    test_files: Optional[List[str]] = None
) -> dict:
    """Execute unit tests using pytest with JUnit XML output for reliable parsing."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
        
        cwd = Path(worktree)
        
        # Use JUnit XML for reliable parsing
        junit_path = cwd / '.pytest_junit.xml'
        cmd = ['python3', '-m', 'pytest', '--junitxml', str(junit_path), '-v']
        if test_files:
            cmd.extend(test_files)
        
        result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=60)
        
        # Parse JUnit XML if it exists
        passed = 0
        failed = 0
        skipped = 0
        failures = []
        duration = 0.0
        
        if junit_path.exists():
            try:
                tree = ET.parse(junit_path)
                root = tree.getroot()
                
                for testcase in root.findall('.//testcase'):
                    test_name = testcase.get('name', 'unknown')
                    test_time = float(testcase.get('time', 0))
                    duration += test_time
                    
                    if testcase.find('failure') is not None:
                        failed += 1
                        failure_elem = testcase.find('failure')
                        failures.append({
                            'test': test_name,
                            'error': failure_elem.get('message', 'Test failed') if failure_elem is not None else 'Test failed'
                        })
                    elif testcase.find('error') is not None:
                        failed += 1
                        error_elem = testcase.find('error')
                        failures.append({
                            'test': test_name,
                            'error': error_elem.get('message', 'Test error') if error_elem is not None else 'Test error'
                        })
                    elif testcase.find('skipped') is not None:
                        skipped += 1
                    else:
                        passed += 1
                
                # Clean up
                junit_path.unlink()
            except Exception as e:
                # Fall back to parsing stdout if XML fails
                for line in result.stdout.splitlines():
                    if line.startswith('PASSED'):
                        passed += 1
                    elif line.startswith('FAILED'):
                        failed += 1
                        failures.append({'test': line.split()[1] if len(line.split()) > 1 else 'unknown', 'error': 'Test failed'})
                    elif line.startswith('SKIPPED'):
                        skipped += 1
        else:
            # Fallback to stdout parsing
            for line in result.stdout.splitlines():
                if line.startswith('PASSED'):
                    passed += 1
                elif line.startswith('FAILED'):
                    failed += 1
                    failures.append({'test': line.split()[1] if len(line.split()) > 1 else 'unknown', 'error': 'Test failed'})
                elif line.startswith('SKIPPED'):
                    skipped += 1
        
        return {
            'status': _run_status(result.returncode, passed, failed, skipped),
            'test_type': 'unit',
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'duration': duration,
            'failures': failures[:10],
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Tests timed out after 60 seconds'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
@heuristic('pytest only.')
def run_integration_tests(
    tool_context: ToolContext,
    test_files: Optional[List[str]] = None
) -> dict:
    """Execute integration tests inside the sandbox worktree."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }

        cwd = Path(worktree)

        cmd = ['python3', '-m', 'pytest', '-v', '-m', 'integration']
        if test_files:
            cmd.extend(test_files)
        
        result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=120)
        
        passed = 0
        failed = 0
        skipped = 0
        failures = []
        
        for line in result.stdout.splitlines():
            if 'PASSED' in line:
                passed += 1
            elif 'FAILED' in line:
                failed += 1
                failures.append({'test': line.split()[1] if line.split() else 'unknown', 'error': 'Test failed'})
            elif 'SKIPPED' in line:
                skipped += 1
        
        return {
            'status': _run_status(result.returncode, passed, failed, skipped),
            'test_type': 'integration',
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'duration': 0.0,
            'failures': failures[:10],
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Integration tests timed out after 120 seconds'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
@heuristic('pytest only.')
def run_regression_tests(
    tool_context: ToolContext,
    test_files: Optional[List[str]] = None
) -> dict:
    """Execute regression tests using pytest with JUnit XML output for reliable parsing."""
    try:
        worktree = tool_context.state.get('worktree')
        if not worktree:
            return {
                'status': 'blocked',
                'reason': 'Create a sandbox worktree first with create_worktree.'
            }
        
        cwd = Path(worktree)
        
        # Use JUnit XML for reliable parsing
        junit_path = cwd / '.pytest_junit_regression.xml'
        cmd = ['python3', '-m', 'pytest', '--junitxml', str(junit_path), '-v', '-m', 'regression']
        if test_files:
            cmd.extend(test_files)
        
        result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=90)
        
        # Parse JUnit XML if it exists
        passed = 0
        failed = 0
        skipped = 0
        failures = []
        duration = 0.0
        
        if junit_path.exists():
            try:
                tree = ET.parse(junit_path)
                root = tree.getroot()
                
                for testcase in root.findall('.//testcase'):
                    test_name = testcase.get('name', 'unknown')
                    test_time = float(testcase.get('time', 0))
                    duration += test_time
                    
                    if testcase.find('failure') is not None:
                        failed += 1
                        failure_elem = testcase.find('failure')
                        failures.append({
                            'test': test_name,
                            'error': failure_elem.get('message', 'Test failed') if failure_elem is not None else 'Test failed'
                        })
                    elif testcase.find('error') is not None:
                        failed += 1
                        error_elem = testcase.find('error')
                        failures.append({
                            'test': test_name,
                            'error': error_elem.get('message', 'Test error') if error_elem is not None else 'Test error'
                        })
                    elif testcase.find('skipped') is not None:
                        skipped += 1
                    else:
                        passed += 1
                
                # Clean up
                junit_path.unlink()
            except Exception as e:
                # Fall back to parsing stdout if XML fails
                for line in result.stdout.splitlines():
                    if 'PASSED' in line:
                        passed += 1
                    elif 'FAILED' in line:
                        failed += 1
                        failures.append({'test': 'unknown', 'error': 'Test failed'})
                    elif 'SKIPPED' in line:
                        skipped += 1
        else:
            # Fallback to stdout parsing
            for line in result.stdout.splitlines():
                if 'PASSED' in line:
                    passed += 1
                elif 'FAILED' in line:
                    failed += 1
                    failures.append({'test': 'unknown', 'error': 'Test failed'})
                elif 'SKIPPED' in line:
                    skipped += 1
        
        return {
            'status': _run_status(result.returncode, passed, failed, skipped),
            'test_type': 'regression',
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'duration': duration,
            'failures': failures[:10],
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Regression tests timed out after 90 seconds'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
@heuristic('pytest only.')
def measure_test_coverage(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Measure code coverage with proper error handling."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)

        result = subprocess.run(
            ['python3', '-m', 'pytest', '--cov=.', '--cov-report=json'],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return {
                'status': 'error',
                'error': f"Coverage run failed: {result.stderr[-500:] if result.stderr else result.stdout[-500:]}",
                'repository_path': str(path)
            }

        # Try to read the coverage.json file
        coverage_file = path / '.coverage.json'
        if not coverage_file.exists():
            coverage_file = path / 'coverage.json'
        
        if not coverage_file.exists():
            return {
                'status': 'error',
                'error': 'Coverage JSON report not generated',
                'repository_path': str(path)
            }

        import json
        with open(coverage_file) as f:
            coverage_data = json.load(f)
        
        overall = coverage_data.get('totals', {}).get('percent_covered', 0.0)

        return {
            'status': 'ok',
            'repository_path': str(path),
            'coverage': {
                'overall': overall,
                'by_file': {k: v.get('percent_covered', 0.0) for k, v in coverage_data.get('files', {}).items()}
            }
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Coverage measurement timed out',
            'repository_path': str(path)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'repository_path': str(path)
        }


@safe
def map_tests_to_functions(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Connect tests to the functions they actually exercise.

    Python test files are parsed with ast: for every test_* function we collect
    the names it calls and the names it imports from project modules, so the
    mapping reflects real references instead of only the test's own name. JS/TS
    test files get a regex-based pass over test()/it() bodies. Every entry is
    tagged with a confidence: 'high' when the target is called or imported in
    the test body, 'low' when it is only a name-derived guess."""
    try:
        import ast
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)

        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}
        test_files = []
        for test_file in path.rglob('*'):
            if not test_file.is_file():
                continue
            rel_parts = test_file.relative_to(path).parts
            if set(rel_parts) & skip_dirs:
                continue
            name = test_file.name
            if (name.startswith('test_') and name.endswith('.py')) or name.endswith('_test.py') \
                    or name.endswith(('.test.js', '.test.jsx', '.test.ts', '.test.tsx',
                                      '.spec.js', '.spec.jsx', '.spec.ts', '.spec.tsx')):
                test_files.append(test_file)

        def _py_mapping(test_file):
            try:
                tree = ast.parse(test_file.read_text(encoding='utf-8', errors='replace'))
            except Exception:
                return []
            module_imports = {}   # local name -> imported qualified name
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for a in node.names:
                        module_imports[a.asname or a.name] = node.module + '.' + a.name
                elif isinstance(node, ast.Import):
                    for a in node.names:
                        module_imports[a.asname or a.name.split('.')[0]] = a.name
            out = []
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not node.name.startswith('test'):
                    continue
                called = set()
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        f = sub.func
                        if isinstance(f, ast.Name):
                            called.add(f.id)
                        elif isinstance(f, ast.Attribute):
                            called.add(f.attr)
                test_out = []
                for name in sorted(called):
                    if name.startswith('test') or name in ('assert', 'print', 'len', 'str',
                                                         'int', 'list', 'dict', 'set', 'open',
                                                         'isinstance', 'getattr', 'setattr',
                                                         'super', 'range', 'enumerate', 'zip'):
                        continue
                    target = module_imports.get(name, name)
                    test_out.append({'test': node.name, 'function': target,
                                     'file': str(test_file.relative_to(path)),
                                     'confidence': 'high',
                                     'evidence': 'called or imported inside the test'})
                if not test_out:
                    leaf = node.name[5:] if node.name.startswith('test_') else node.name[4:]
                    leaf = leaf.lstrip('_')
                    if leaf:
                        test_out.append({'test': node.name, 'function': leaf,
                                         'file': str(test_file.relative_to(path)),
                                         'confidence': 'low',
                                         'evidence': 'derived from the test name only'})
                out.extend(test_out)
            return out

        def _js_mapping(test_file):
            try:
                content = test_file.read_text(encoding='utf-8', errors='replace')
            except Exception:
                return []
            out = []
            for m in re.finditer(r'(?:test|it)\(\s*[\'"`]([^\'"`]+)[\'"`]', content):
                title = m.group(1)
                leaf = re.sub(r'[^A-Za-z0-9]+', '_', title).strip('_').lower()
                if not leaf:
                    continue
                out.append({'test': title, 'function': leaf,
                            'file': str(test_file.relative_to(path)),
                            'confidence': 'low',
                            'evidence': 'derived from the test title only'})
            return out

        test_mapping = []
        for test_file in test_files:
            if test_file.suffix == '.py':
                test_mapping.extend(_py_mapping(test_file))
            else:
                test_mapping.extend(_js_mapping(test_file))

        return {
            'status': 'ok',
            'repository_path': str(path),
            'test_mapping': test_mapping[:50]
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
@heuristic('File-level coverage threshold; not per-CFG-path.')
def identify_untested_paths(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Find paths without adequate coverage."""
    try:
        coverage_result = measure_test_coverage(repository_path, tool_context)
        
        if coverage_result.get('status') != 'ok':
            return coverage_result
        
        coverage = coverage_result.get('coverage', {})
        by_file = coverage.get('by_file', {})
        
        untested_paths = []
        for file_path, cov_value in by_file.items():
            if cov_value < 0.5:
                untested_paths.append({
                    'file': file_path,
                    'coverage': cov_value,
                    'needs_attention': True
                })
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'untested_paths': untested_paths
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def verify_compilation(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Check compilation."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        # Try to compile based on language
        if (path / 'setup.py').exists() or (path / 'pyproject.toml').exists():
            result = subprocess.run(['python3', '-m', 'compileall', str(path)], capture_output=True, text=True)
            return {
                'status': 'ok' if result.returncode == 0 else 'error',
                'repository_path': str(path),
                'compilation': 'success' if result.returncode == 0 else 'failed',
                'errors': result.stderr[-1000:] if result.stderr else '',
                'output': result.stdout[-1000:] if result.stdout else ''
            }
        
        return {
            'status': 'not_applicable',
            'repository_path': str(path),
            'message': 'No Python build configuration found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def verify_types(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Check type correctness."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        # Check if mypy is available
        check_result = subprocess.run(['python3', '-m', 'mypy', '--version'], capture_output=True, text=True)
        if check_result.returncode != 0:
            return {
                'status': 'unavailable',
                'reason': 'mypy not found',
                'hint': 'Install with: pip install mypy'
            }
        
        result = subprocess.run(['python3', '-m', 'mypy', str(path)], capture_output=True, text=True, timeout=60)
        
        errors = []
        for line in result.stdout.splitlines():
            if 'error:' in line.lower():
                errors.append(line[:200])
        
        return {
            'status': 'ok' if result.returncode == 0 else 'error',
            'repository_path': str(path),
            'type_check': 'success' if result.returncode == 0 else 'failed',
            'errors': errors[:20],
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Type checking timed out'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def verify_lint(
    repository_path: str,
    tool_context: ToolContext,
    linter: str = 'auto'
) -> dict:
    """Check lint rules."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if linter == 'auto':
            linter = 'pylint'
        
        # Check if linter is available
        check_result = subprocess.run(['which', linter], capture_output=True, text=True)
        if check_result.returncode != 0:
            return {
                'status': 'unavailable',
                'reason': f'Linter {linter} not found',
                'hint': f'Install with: pip install {linter}'
            }
        
        result = subprocess.run([linter, str(path)], capture_output=True, text=True, timeout=60)

        # Diagnostics can appear on either stream (pylint reports on stdout,
        # many linters report on stderr). A non-zero exit with NO diagnostic
        # lines means the linter itself failed — that is an error, not a pass.
        diag_re = re.compile(r'^\s*(?:\S+[/\\])?\S+\.(?:py|pyi|js|jsx|ts|tsx|go|rs|java|cs|cpp|c|h):\d+')
        all_lines = (result.stdout + '\n' + result.stderr).splitlines()
        warnings = []
        for line in all_lines:
            stripped = line.strip()
            if stripped and (diag_re.match(stripped) or re.match(r'^\S+\[\w\]', stripped)):
                warnings.append(stripped[:200])

        # pylint-style severity bits: fatal=1, error=2, warning=4, refactor=8,
        # convention=16, usage error=32. For other linters the bitmask is a
        # best-effort hint only; the diagnostic-line check above is authoritative.
        rc = result.returncode
        if rc != 0 and not warnings:
            return {
                'status': 'error',
                'repository_path': str(path),
                'linter': linter,
                'lint_check': 'error',
                'error': ('Linter exited with code %s and produced no diagnostics; '
                          'the lint run itself failed.') % rc,
                'output': (result.stderr or result.stdout)[-1000:],
                'exit_code': rc
            }
        if rc & 0b00011 or rc & 32:
            lint_check = 'failed'
        elif warnings or rc:
            lint_check = 'warning'
        else:
            lint_check = 'success'

        return {
            'status': 'ok',
            'repository_path': str(path),
            'linter': linter,
            'lint_check': lint_check,
            'warnings': warnings[:20],
            'exit_code': rc
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Lint checking timed out'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def compare_before_after(
    before_snapshot: str,
    after_snapshot: str,
    tool_context: ToolContext
) -> dict:
    """Compare results before and after changes."""
    try:
        from pathlib import Path
        import difflib
        
        before_path = Path(before_snapshot)
        after_path = Path(after_snapshot)
        
        # If paths exist, compare files
        if before_path.exists() and after_path.exists():
            before_content = before_path.read_text(encoding='utf-8')
            after_content = after_path.read_text(encoding='utf-8')
            
            diff = list(difflib.unified_diff(
                before_content.splitlines(keepends=True),
                after_content.splitlines(keepends=True),
                fromfile=str(before_path),
                tofile=str(after_path)
            ))
            
            return {
                'status': 'ok',
                'before_snapshot': before_snapshot,
                'after_snapshot': after_snapshot,
                'diff': ''.join(diff),
                'changes_detected': len(diff) > 0,
                'note': 'File comparison - full snapshot comparison requires test result management'
            }
        
        # Otherwise, compare as strings
        diff = list(difflib.unified_diff(
            before_snapshot.splitlines(keepends=True),
            after_snapshot.splitlines(keepends=True),
            fromfile='before',
            tofile='after'
        ))
        
        return {
            'status': 'ok',
            'before_snapshot': before_snapshot[:100] + '...' if len(before_snapshot) > 100 else before_snapshot,
            'after_snapshot': after_snapshot[:100] + '...' if len(after_snapshot) > 100 else after_snapshot,
            'diff': ''.join(diff),
            'changes_detected': len(diff) > 0,
            'note': 'String comparison - full snapshot comparison requires test result management'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


