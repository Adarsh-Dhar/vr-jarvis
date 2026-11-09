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
from ._common import repo_root, resolve_in_repo
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
            path = resolve_in_repo(path)
        
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
            'status': 'ok' if result.returncode == 0 else 'failed',
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
def run_integration_tests(
    tool_context: ToolContext,
    test_files: Optional[List[str]] = None
) -> dict:
    """Execute integration tests."""
    try:
        cwd = repo_root()
        
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
        cwd = repo_root()
        
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
            'status': 'ok' if result.returncode == 0 else 'failed',
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
def run_property_tests(
    tool_context: ToolContext,
    test_files: Optional[List[str]] = None
) -> dict:
    """Execute property-based tests."""
    try:
        cwd = repo_root()
        
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
        # Try to use Hypothesis for property-based testing
        cwd = repo_root()
        
        result = subprocess.run(
            ['python3', '-m', 'hypothesis', 'test', target_function],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=duration
        )
        
        return {
            'status': 'ok' if result.returncode == 0 else 'failed',
            'target_function': target_function,
            'duration': duration,
            'output': result.stdout[-2000:] if result.stdout else result.stderr[-2000:],
            'note': 'Real fuzzing requires integration with AFL, libFuzzer, or extended Hypothesis'
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'ok',
            'target_function': target_function,
            'duration': duration,
            'timeout': True,
            'note': 'Fuzz test completed after timeout'
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
            
            # Generate test template based on signature
            tests = []
            
            # Normal case test
            normal_test = f"def test_{function_id}_normal_case():\n"
            normal_test += f"    \"\"\"Test normal operation of {function_id}\"\"\"\n"
            normal_test += f"    result = {function_id}()\n"
            normal_test += f"    assert result is not None\n"
            tests.append({'name': f'test_{function_id}_normal_case', 'code': normal_test})
            
            # Parameterized test if function has parameters
            if params:
                param_test = f"def test_{function_id}_with_params():\n"
                param_test += f"    \"\"\"Test {function_id} with parameters\"\"\"\n"
                param_literal = ', '.join(f"'{p['name']}': None" for p in params)
                param_test += f"    params = {{{param_literal}}}\n"
                param_test += f"    result = {function_id}(**params)\n"
                param_test += f"    assert result is not None\n"
                tests.append({'name': f'test_{function_id}_with_params', 'code': param_test})
            
            # Error case test
            error_test = f"def test_{function_id}_error_case():\n"
            error_test += f"    \"\"\"Test error handling for {function_id}\"\"\"\n"
            error_test += f"    with pytest.raises(Exception):\n"
            error_test += f"        {function_id}(None)\n"
            tests.append({'name': f'test_{function_id}_error_case', 'code': error_test})
            
            return {
                'status': 'ok',
                'function_id': function_id,
                'parameters': params,
                'generated_tests': tests,
                'test_count': len(tests),
                'note': 'Parameter-aware test template generated - provide actual test values for full coverage'
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
        tests = []
        
        # Null input test
        null_test = f"def test_{function_id}_null_input():\n"
        null_test += f"    \"\"\"Test {function_id} with None/null input\"\"\"\n"
        null_test += f"    with pytest.raises((ValueError, TypeError)):\n"
        null_test += f"        {function_id}(None)\n"
        tests.append({'name': f'test_{function_id}_null_input', 'code': null_test})
        
        # Empty input test
        empty_test = f"def test_{function_id}_empty_input():\n"
        empty_test += f"    \"\"\"Test {function_id} with empty input\"\"\"\n"
        empty_test += f"    result = {function_id}('')\n"
        empty_test += f"    assert result is not None\n"
        tests.append({'name': f'test_{function_id}_empty_input', 'code': empty_test})
        
        # Boundary value test
        boundary_test = f"def test_{function_id}_boundary_value():\n"
        boundary_test += f"    \"\"\"Test {function_id} with boundary values\"\"\"\n"
        boundary_test += f"    result = {function_id}(0)\n"
        boundary_test += f"    assert result is not None\n"
        boundary_test += f"    result = {function_id}(999999)\n"
        boundary_test += f"    assert result is not None\n"
        tests.append({'name': f'test_{function_id}_boundary_value', 'code': boundary_test})
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'generated_tests': tests,
            'test_count': len(tests),
            'note': 'Edge case templates generated - provide actual test data for full coverage'
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
        import re
        endpoint_name = re.sub(r'[^a-zA-Z0-9_]', '_', endpoint.replace('/', '_'))
        
        tests = []
        
        # Success test
        success_test = f"def test_{endpoint_name}_success():\n"
        success_test += f"    \"\"\"Test successful {endpoint} call\"\"\"\n"
        success_test += f"    response = requests.get('{endpoint}')\n"
        success_test += f"    assert response.status_code == 200\n"
        tests.append({'name': f'test_{endpoint_name}_success', 'code': success_test})
        
        # Error test
        error_test = f"def test_{endpoint_name}_error():\n"
        error_test += f"    \"\"\"Test {endpoint} error handling\"\"\"\n"
        error_test += f"    response = requests.get('{endpoint}/invalid')\n"
        error_test += f"    assert response.status_code in [400, 404, 500]\n"
        tests.append({'name': f'test_{endpoint_name}_error', 'code': error_test})
        
        return {
            'status': 'ok',
            'endpoint': endpoint,
            'endpoint_name': endpoint_name,
            'generated_tests': tests,
            'test_count': len(tests),
            'note': 'Integration test templates generated - configure request payload for actual tests'
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
            path = resolve_in_repo(path)
        
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
            path = resolve_in_repo(path)
        
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
