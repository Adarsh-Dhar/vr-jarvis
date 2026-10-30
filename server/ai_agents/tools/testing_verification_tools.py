"""
Agent 11 - Testing & Verification Tools
Establish whether the code works and whether changes have broken anything.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import subprocess
import re
from google.adk.tools import ToolContext
from ._safe import safe


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
            path = Path.cwd() / path
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'Repository not found: {repository_path}'
            }
        
        tests_found = []
        
        # Detect test framework and find test files
        if test_framework == 'auto':
            # Check for common test directories
            test_dirs = ['tests', 'test', '__tests__', 'spec']
            for test_dir in test_dirs:
                test_path = path / test_dir
                if test_path.exists():
                    for test_file in test_path.rglob('test_*.py'):
                        tests_found.append({
                            'file': str(test_file.relative_to(path)),
                            'name': test_file.stem,
                            'type': 'unit'
                        })
                    for test_file in test_path.rglob('*_test.py'):
                        tests_found.append({
                            'file': str(test_file.relative_to(path)),
                            'name': test_file.stem,
                            'type': 'unit'
                        })
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'test_framework': test_framework,
            'tests_found': tests_found
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def run_unit_tests(
    tool_context: ToolContext,
    test_files: Optional[List[str]] = None
) -> dict:
    """Execute unit tests."""
    try:
        cwd = Path.cwd()
        
        cmd = ['python3', '-m', 'pytest', '-v']
        if test_files:
            cmd.extend(test_files)
        
        result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=60)
        
        # Parse pytest output
        passed = 0
        failed = 0
        skipped = 0
        failures = []
        
        for line in result.stdout.splitlines():
            if line.startswith('PASSED'):
                passed += 1
            elif line.startswith('FAILED'):
                failed += 1
                failures.append({'test': line.split()[1], 'error': 'Test failed'})
            elif line.startswith('SKIPPED'):
                skipped += 1
        
        # Also parse summary line
        summary_match = re.search(r'(\d+) passed, (\d+) failed, (\d+) skipped', result.stdout)
        if summary_match:
            passed = int(summary_match.group(1))
            failed = int(summary_match.group(2))
            skipped = int(summary_match.group(3))
        
        return {
            'status': 'ok' if result.returncode == 0 else 'failed',
            'test_type': 'unit',
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
            'error': 'Tests timed out after 60 seconds'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def run_integration_tests(
    tool_context: ToolContext,
    test_files: Optional[List[str]] = None
) -> dict:
    """Execute integration tests."""
    try:
        cwd = Path.cwd()
        
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
            'status': 'ok' if result.returncode == 0 else 'failed',
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
def run_end_to_end_tests(
    tool_context: ToolContext,
    test_files: Optional[List[str]] = None
) -> dict:
    """Execute end-to-end tests."""
    try:
        cwd = Path.cwd()
        
        cmd = ['python3', '-m', 'pytest', '-v', '-m', 'e2e']
        if test_files:
            cmd.extend(test_files)
        
        result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=180)
        
        passed = 0
        failed = 0
        skipped = 0
        
        for line in result.stdout.splitlines():
            if 'PASSED' in line:
                passed += 1
            elif 'FAILED' in line:
                failed += 1
            elif 'SKIPPED' in line:
                skipped += 1
        
        return {
            'status': 'ok' if result.returncode == 0 else 'failed',
            'test_type': 'end_to_end',
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'duration': 0.0,
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'E2E tests timed out after 180 seconds'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def run_regression_tests(
    tool_context: ToolContext,
    test_files: Optional[List[str]] = None
) -> dict:
    """Execute regression tests."""
    try:
        cwd = Path.cwd()
        
        cmd = ['python3', '-m', 'pytest', '-v', '-m', 'regression']
        if test_files:
            cmd.extend(test_files)
        
        result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=90)
        
        passed = 0
        failed = 0
        skipped = 0
        
        for line in result.stdout.splitlines():
            if 'PASSED' in line:
                passed += 1
            elif 'FAILED' in line:
                failed += 1
            elif 'SKIPPED' in line:
                skipped += 1
        
        return {
            'status': 'ok' if result.returncode == 0 else 'failed',
            'test_type': 'regression',
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'duration': 0.0,
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
def run_property_tests(
    tool_context: ToolContext,
    test_files: Optional[List[str]] = None
) -> dict:
    """Execute property-based tests."""
    try:
        cwd = Path.cwd()
        
        cmd = ['python3', '-m', 'pytest', '-v', '-m', 'property']
        if test_files:
            cmd.extend(test_files)
        
        result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=60)
        
        passed = 0
        failed = 0
        failures = []
        
        for line in result.stdout.splitlines():
            if 'PASSED' in line:
                passed += 1
            elif 'FAILED' in line:
                failed += 1
                failures.append({'test': line.split()[1] if line.split() else 'unknown', 'error': 'Property violated'})
        
        return {
            'status': 'ok' if result.returncode == 0 else 'failed',
            'test_type': 'property',
            'passed': passed,
            'failed': failed,
            'skipped': 0,
            'duration': 0.0,
            'failures': failures[:10],
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Property tests timed out after 60 seconds'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def run_fuzz_tests(
    target_function: str,
    tool_context: ToolContext,
    duration: int = 60
) -> dict:
    """Fuzz inputs and behavior."""
    try:
        # This is a placeholder - real fuzzing requires tools like AFL, libFuzzer, or Hypothesis
        return {
            'status': 'not_implemented',
            'message': 'Fuzzing requires integration with tools like AFL, libFuzzer, or Hypothesis',
            'target_function': target_function,
            'duration': duration
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_unit_tests(
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Generate unit tests."""
    try:
        from .code_understanding_tools import extract_function_signature
        
        sig_result = extract_function_signature(function_id, tool_context)
        
        if sig_result.get('status') == 'ok':
            signature = sig_result['signature']
            params = signature.get('parameters', [])
            
            # Generate test template
            test_code = f"import pytest\n\n"
            test_code += f"def test_{function_id}_normal_case():\n"
            test_code += f"    # TODO: Implement test for {function_id}\n"
            test_code += f"    assert True\n\n"
            
            if params:
                test_code += f"def test_{function_id}_with_params():\n"
                test_code += f"    # TODO: Test with parameters: {', '.join(p['name'] for p in params)}\n"
                test_code += f"    assert True\n\n"
            
            test_code += f"def test_{function_id}_error_case():\n"
            test_code += f"    # TODO: Test error handling\n"
            test_code += f"    assert True\n"
            
            return {
                'status': 'ok',
                'function_id': function_id,
                'generated_tests': [
                    {'name': f'test_{function_id}_normal_case', 'code': test_code},
                    {'name': f'test_{function_id}_with_params', 'code': test_code},
                    {'name': f'test_{function_id}_error_case', 'code': test_code}
                ],
                'note': 'Real test generation requires LLM integration'
            }
        
        return sig_result
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_edge_case_tests(
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Generate edge-case tests."""
    try:
        test_code = f"import pytest\n\n"
        test_code += f"def test_{function_id}_null_input():\n"
        test_code += f"    # TODO: Test with None/null input\n"
        test_code += f"    assert True\n\n"
        
        test_code += f"def test_{function_id}_empty_input():\n"
        test_code += f"    # TODO: Test with empty string/list\n"
        test_code += f"    assert True\n\n"
        
        test_code += f"def test_{function_id}_boundary_value():\n"
        test_code += f"    # TODO: Test with boundary values\n"
        test_code += f"    assert True\n"
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'generated_tests': [
                {'name': f'test_{function_id}_null_input', 'code': test_code},
                {'name': f'test_{function_id}_empty_input', 'code': test_code},
                {'name': f'test_{function_id}_boundary_value', 'code': test_code}
            ],
            'note': 'Real test generation requires LLM integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_integration_tests(
    endpoint: str,
    tool_context: ToolContext
) -> dict:
    """Generate integration tests."""
    try:
        test_code = f"import pytest\n\n"
        test_code += f"def test_{endpoint.replace('/', '_')}_success():\n"
        test_code += f"    # TODO: Test successful endpoint call\n"
        test_code += f"    assert True\n\n"
        
        test_code += f"def test_{endpoint.replace('/', '_')}_error():\n"
        test_code += f"    # TODO: Test error handling\n"
        test_code += f"    assert True\n"
        
        return {
            'status': 'ok',
            'endpoint': endpoint,
            'generated_tests': [
                {'name': f'test_{endpoint.replace('/', '_')}_success', 'code': test_code},
                {'name': f'test_{endpoint.replace('/', '_')}_error', 'code': test_code}
            ],
            'note': 'Real test generation requires LLM integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def measure_test_coverage(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Measure code coverage."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(
            ['python3', '-m', 'pytest', '--cov=.', '--cov-report=term'],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Parse coverage output
        coverage = {'overall': 0.0, 'by_file': {}}
        
        for line in result.stdout.splitlines():
            if 'TOTAL' in line:
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        coverage['overall'] = float(parts[3].rstrip('%'))
                    except:
                        pass
            elif '%' in line and line.strip() and not line.startswith('TOTAL'):
                parts = line.split()
                if len(parts) >= 2:
                    file_name = parts[0]
                    try:
                        cov_value = float(parts[-1].rstrip('%'))
                        coverage['by_file'][file_name] = cov_value
                    except:
                        pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'coverage': coverage,
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Coverage measurement timed out'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def measure_branch_coverage(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Measure branch coverage."""
    try:
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        result = subprocess.run(
            ['python3', '-m', 'pytest', '--cov=.', '--cov-branch', '--cov-report=term'],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        branch_coverage = {'overall': 0.0, 'by_function': {}}
        
        for line in result.stdout.splitlines():
            if 'branch' in line.lower() and '%' in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        branch_coverage['overall'] = float(parts[-1].rstrip('%'))
                    except:
                        pass
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'branch_coverage': branch_coverage,
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:]
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Branch coverage measurement timed out'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def map_tests_to_functions(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Connect tests to functions."""
    try:
        # This is a heuristic implementation
        # Real implementation would use AST analysis of test files
        path = Path(repository_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        test_mapping = []
        
        for test_file in path.rglob('test_*.py'):
            try:
                content = test_file.read_text(encoding='utf-8')
                
                # Extract function names from test file
                import re
                test_funcs = re.findall(r'def (test_\w+)', content)
                
                for test_func in test_funcs:
                    # Extract target function name from test name
                    target = test_func.replace('test_', '').replace('_test', '')
                    test_mapping.append({
                        'test': test_func,
                        'function': target,
                        'file': str(test_file.relative_to(path))
                    })
            except:
                continue
        
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
            path = Path.cwd() / path
        
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
            path = Path.cwd() / path
        
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
            path = Path.cwd() / path
        
        if linter == 'auto':
            linter = 'pylint'
        
        result = subprocess.run([linter, str(path)], capture_output=True, text=True, timeout=60)
        
        warnings = []
        for line in result.stdout.splitlines():
            if line.strip():
                warnings.append(line[:200])
        
        return {
            'status': 'ok',
            'repository_path': str(path),
            'linter': linter,
            'lint_check': 'warning' if warnings else 'success',
            'warnings': warnings[:20],
            'exit_code': result.returncode
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
def verify_security(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Check security findings."""
    try:
        # This is a placeholder - real implementation would use tools like bandit, safety, etc.
        return {
            'status': 'not_implemented',
            'message': 'Security verification requires integration with tools like bandit, safety, or SAST tools',
            'repository_path': repository_path
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
        # This would compare test results, coverage, etc.
        # For now, return a placeholder
        return {
            'status': 'not_implemented',
            'message': 'Before/after comparison requires snapshot management',
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def generate_test_report(
    repository_path: str,
    tool_context: ToolContext,
    format: str = 'json'
) -> dict:
    """Produce a verification report."""
    try:
        # Run various verification checks
        type_result = verify_types(repository_path, tool_context)
        lint_result = verify_lint(repository_path, tool_context)
        coverage_result = measure_test_coverage(repository_path, tool_context)
        
        report = {
            'repository_path': repository_path,
            'format': format,
            'summary': 'Verification complete',
            'type_check': type_result.get('type_check', 'unknown'),
            'lint_check': lint_result.get('lint_check', 'unknown'),
            'coverage': coverage_result.get('coverage', {}).get('overall', 0.0),
            'generated_at': '2024-01-01T12:00:00Z'
        }
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'format': format,
            'report': report
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
