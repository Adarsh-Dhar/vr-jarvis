"""
Test Orchestrator
Schedules test execution and manages test runs
"""

from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json
import sys
import shutil
import tempfile
import logging
sys.path.insert(0, str(Path(__file__).parent))
from test_registry import TestRegistry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestOrchestrator:
    """Orchestrates test execution across all test layers"""
    
    def __init__(self, test_root: Path, registry: TestRegistry):
        self.test_root = test_root
        self.registry = registry
        self.current_run: Optional[Dict] = None
    
    def run_test_suite(
        self,
        categories: Optional[List[str]] = None,
        tools: Optional[List[str]] = None,
        severity: Optional[str] = None,
        layers: Optional[List[int]] = None,
        test_types: Optional[List[str]] = None,
        parallel: bool = True
    ) -> Dict:
        """Run a test suite with specified filters"""
        # Determine which tests to run
        test_ids = self._select_tests(categories, tools, severity, layers, test_types)
        
        # Initialize run metadata
        self.current_run = {
            'run_id': f"run_{int(time.time())}",
            'start_time': time.time(),
            'test_ids': test_ids,
            'results': {},
            'summary': {
                'total': len(test_ids),
                'passed': 0,
                'failed': 0,
                'skipped': 0,
                'errors': 0
            }
        }
        
        # Execute tests
        if parallel:
            self._run_tests_parallel(test_ids)
        else:
            self._run_tests_sequential(test_ids)
        
        # Finalize run
        self.current_run['end_time'] = time.time()
        self.current_run['duration'] = self.current_run['end_time'] - self.current_run['start_time']
        
        # Add aggregated fields for report generation
        self.current_run['success_rate'] = self.current_run['summary']['passed'] / self.current_run['summary']['total'] if self.current_run['summary']['total'] > 0 else 0
        self.current_run['failed_tests'] = [
            test_id for test_id, result in self.current_run['results'].items()
            if result.get('status') == 'failed'
        ]
        self.current_run['error_tests'] = [
            test_id for test_id, result in self.current_run['results'].items()
            if result.get('status') == 'error'
        ]
        
        return self.current_run
    
    def _select_tests(
        self,
        categories: Optional[List[str]],
        tools: Optional[List[str]],
        severity: Optional[str],
        layers: Optional[List[int]],
        test_types: Optional[List[str]]
    ) -> List[str]:
        """Select test IDs based on filters"""
        selected = set()

        if categories:
            for category in categories:
                selected.update(self.registry.get_tests_by_category(category))

        if tools:
            for tool in tools:
                selected.update(self.registry.get_tests_by_tool(tool))

        if severity:
            selected.update(self.registry.get_tests_by_severity(severity))

        if layers:
            for layer in layers:
                selected.update(self.registry.get_tests_by_layer(layer))

        if test_types:
            for test_type in test_types:
                selected.update(self.registry.get_tests_by_test_type(test_type))

        if not selected:
            # No filters, return all tests
            selected = set(self.registry.get_all_tests().keys())

        return list(selected)
    
    def _run_tests_parallel(self, test_ids: List[str]):
        """Run tests in parallel"""
        max_workers = max(1, min(10, len(test_ids)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._run_single_test, test_id): test_id
                for test_id in test_ids
            }
            
            for future in as_completed(futures):
                test_id = futures[future]
                try:
                    result = future.result()
                    self.current_run['results'][test_id] = result
                    self._update_summary(result)
                except Exception as e:
                    self.current_run['results'][test_id] = {
                        'status': 'error',
                        'error': str(e)
                    }
                    self.current_run['summary']['errors'] += 1
    
    def _run_tests_sequential(self, test_ids: List[str]):
        """Run tests sequentially"""
        for test_id in test_ids:
            try:
                result = self._run_single_test(test_id)
                self.current_run['results'][test_id] = result
                self._update_summary(result)
            except Exception as e:
                self.current_run['results'][test_id] = {
                    'status': 'error',
                    'error': str(e)
                }
                self.current_run['summary']['errors'] += 1
    
    def _run_single_test(self, test_id: str) -> Dict:
        """Run a single test"""
        test_def = self.registry.get_test(test_id)
        if not test_def:
            return {
                'status': 'error',
                'error': f'Test {test_id} not found'
            }
        
        # Check if it's a YAML test or Python test
        if test_def.get('type') == 'python':
            return self._run_python_test(test_def)
        else:
            return self._run_yaml_test(test_def)
    
    def _run_yaml_test(self, test_def: Dict) -> Dict:
        """Run a YAML-defined test"""
        import sys
        import importlib

        start_time = time.time()

        # Check if test is skipped
        if test_def.get('skip'):
            return {
                'status': 'skipped',
                'test_id': test_def['test_id'],
                'reason': test_def.get('skip_reason', 'Skipped'),
                'duration_ms': 0
            }

        # Import the tool function directly from its module
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))

            tool_name = test_def.get('tool')
            if not tool_name:
                return {
                    'status': 'error',
                    'test_id': test_def['test_id'],
                    'error': 'No tool specified in test definition',
                    'duration_ms': int((time.time() - start_time) * 1000)
                }

            # Try to import from tools package first
            try:
                from ai_agents import tools
                tool_func = getattr(tools, tool_name, None)
                if tool_func and callable(tool_func):
                    module_name = 'ai_agents.tools'
                else:
                    # Fall back to module mapping
                    module_name = tool_modules.get(tool_name)
                    if not module_name:
                        return {
                            'status': 'error',
                            'test_id': test_def['test_id'],
                            'error': f'Unknown tool: {tool_name}',
                            'duration_ms': int((time.time() - start_time) * 1000)
                        }
                    module = __import__(module_name, fromlist=[tool_name])
                    tool_func = getattr(module, tool_name, None)
            except ImportError:
                # tools package import failed, use module mapping
                module_name = tool_modules.get(tool_name)
                if not module_name:
                    return {
                        'status': 'error',
                        'test_id': test_def['test_id'],
                        'error': f'Unknown tool module for {tool_name}',
                        'duration_ms': int((time.time() - start_time) * 1000)
                    }
                module = __import__(module_name, fromlist=[tool_name])
                tool_func = getattr(module, tool_name, None)

        except ImportError as e:
            return {
                'status': 'error',
                'test_id': test_def['test_id'],
                'error': f'Failed to import tool module: {e}',
                'duration_ms': int((time.time() - start_time) * 1000)
            }
        if not tool_func or not callable(tool_func):
            return {
                'status': 'error',
                'test_id': test_def['test_id'],
                'error': f'Tool {tool_name} not found or not callable',
                'duration_ms': int((time.time() - start_time) * 1000)
            }

        # Create a mock ToolContext
        class MockToolContext:
            def __init__(self):
                self.state = {}

        tool_context = MockToolContext()

        # Setup fixture isolation if needed
        fixture = test_def.get('fixture')
        temp_fixture_dir = None
        try:
            # Copy fixture to temp directory if specified
            if fixture:
                fixture_path = self.test_root / 'fixtures' / 'repositories' / fixture
                if fixture_path.exists():
                    temp_fixture_dir = Path(tempfile.mkdtemp(prefix=f'fixture_{fixture}_'))
                    shutil.copytree(fixture_path, temp_fixture_dir / fixture, dirs_exist_ok=True)
                    logger.info(f"Copied fixture {fixture} to {temp_fixture_dir}")

            # Call the tool with the specified input
            input_args = test_def.get('input', {}).copy()

            # Replace fixture paths with temp fixture paths
            if temp_fixture_dir:
                for key, value in input_args.items():
                    if isinstance(value, str) and 'fixtures/repositories' in value:
                        # Extract the relative path after 'fixtures/repositories/'
                        parts = value.split('fixtures/repositories/')
                        if len(parts) == 2:
                            input_args[key] = str(temp_fixture_dir / parts[1])
            elif 'fixtures/repositories' in str(input_args):
                # If no temp fixture but input has fixture path, make it absolute
                for key, value in input_args.items():
                    if isinstance(value, str) and 'fixtures/repositories' in value:
                        input_args[key] = str(self.test_root / value)

            # Remove tool_context from input_args if it's a placeholder
            # We'll always pass the mock tool_context as a kwarg
            if 'tool_context' in input_args and input_args['tool_context'] == 'placeholder':
                del input_args['tool_context']

            # Call the tool with tool_context as kwarg
            logger.info(f"Calling tool {tool_name} with args: {input_args}")
            output = tool_func(**input_args, tool_context=tool_context)
        except Exception as e:
            # Cleanup temp fixture
            if temp_fixture_dir and temp_fixture_dir.exists():
                shutil.rmtree(temp_fixture_dir, ignore_errors=True)
            logger.error(f"Tool execution failed for {test_def.get('test_id')}: {e}", exc_info=True)
            return {
                'status': 'error',
                'test_id': test_def['test_id'],
                'error': f'Tool execution failed: {e}',
                'duration_ms': int((time.time() - start_time) * 1000),
                'input_args': input_args if 'input_args' in locals() else None
            }
        finally:
            # Cleanup temp fixture
            if temp_fixture_dir and temp_fixture_dir.exists():
                shutil.rmtree(temp_fixture_dir, ignore_errors=True)

        # Check the output against expected
        expected = test_def.get('expected', {})
        failed = False
        failures = []

        if expected:
            for key, expected_value in expected.items():
                # Handle custom validation fields
                if key == 'file_path_contains':
                    file_path = output.get('file_path', '')
                    if expected_value not in file_path:
                        failures.append(f'file_path does not contain {expected_value}')
                        failed = True
                elif key == 'content_contains':
                    content = str(output.get('content', ''))
                    for required in expected_value if isinstance(expected_value, list) else [expected_value]:
                        if required not in content:
                            failures.append(f'content does not contain {required}')
                            failed = True
                elif key == 'line_count':
                    content = output.get('content', '')
                    actual_lines = len(content.split('\n')) if content else 0
                    if actual_lines != expected_value:
                        failures.append(f'line_count: expected {expected_value}, got {actual_lines}')
                        failed = True
                elif key == 'ast_not_empty':
                    ast = output.get('ast')
                    if expected_value and (not ast or (isinstance(ast, (list, dict)) and len(ast) == 0)):
                        failures.append(f'AST is empty but should not be')
                        failed = True
                elif key == 'language':
                    actual_language = output.get('language')
                    if actual_language != expected_value:
                        failures.append(f'language: expected {expected_value}, got {actual_language}')
                        failed = True
                elif key == 'symbol_count_min':
                    symbols = output.get('symbols', [])
                    if len(symbols) < expected_value:
                        failures.append(f'symbol_count: expected at least {expected_value}, got {len(symbols)}')
                        failed = True
                elif key == 'known_symbols_present':
                    symbols = output.get('symbols', [])
                    symbol_names = [s.get('name') if isinstance(s, dict) else str(s) for s in symbols]
                    for symbol in expected_value if isinstance(expected_value, list) else [expected_value]:
                        if symbol not in symbol_names:
                            failures.append(f'known symbol not found: {symbol}')
                            failed = True
                elif key == 'file_count_min':
                    files = output.get('files', [])
                    if len(files) < expected_value:
                        failures.append(f'file_count: expected at least {expected_value}, got {len(files)}')
                        failed = True
                elif key == 'known_files_present':
                    files = output.get('files', [])
                    file_names = [f.get('path') if isinstance(f, dict) else str(f) for f in files]
                    for file in expected_value if isinstance(expected_value, list) else [expected_value]:
                        if file not in file_names:
                            failures.append(f'known file not found: {file}')
                            failed = True
                elif key == 'error_contains':
                    error = output.get('error', '')
                    if expected_value not in error:
                        failures.append(f'error does not contain {expected_value}')
                        failed = True
                elif key == 'content_type':
                    content = output.get('content', '')
                    if expected_value == 'binary' and content:
                        failures.append(f'content should be binary but is text')
                        failed = True
                elif key == 'content_not_empty':
                    content = output.get('content', '')
                    if expected_value and not content:
                        failures.append(f'content is empty but should not be')
                        failed = True
                elif key == 'file_path_type':
                    file_path = output.get('file_path', '')
                    if expected_value == 'absolute' and not Path(file_path).is_absolute():
                        failures.append(f'file_path should be absolute but is relative')
                        failed = True
                elif key == 'secrets_found_min':
                    secrets = output.get('secrets', [])
                    expected_min = int(expected_value) if isinstance(expected_value, str) else expected_value
                    if len(secrets) < expected_min:
                        failures.append(f'secrets: expected at least {expected_min}, got {len(secrets)}')
                        failed = True
                elif key == 'known_secrets_detected':
                    if output is None:
                        failures.append(f'Output is None, cannot check secrets')
                        failed = True
                    else:
                        secrets = output.get('secrets', [])
                        secret_types = [s.get('type') if isinstance(s, dict) else str(s) for s in secrets]
                        for secret in expected_value if isinstance(expected_value, list) else [expected_value]:
                            if secret not in secret_types:
                                failures.append(f'known secret not detected: {secret}')
                                failed = True
                elif key == 'vulnerabilities_found_min':
                    if output is None:
                        failures.append(f'Output is None, cannot check vulnerabilities')
                        failed = True
                    else:
                        vulnerabilities = output.get('vulnerabilities', [])
                        expected_min = int(expected_value) if isinstance(expected_value, str) else expected_value
                        if len(vulnerabilities) < expected_min:
                            failures.append(f'vulnerabilities: expected at least {expected_min}, got {len(vulnerabilities)}')
                            failed = True
                elif key == 'known_vulnerabilities_detected':
                    if output is None:
                        failures.append(f'Output is None, cannot check vulnerabilities')
                        failed = True
                    else:
                        vulnerabilities = output.get('vulnerabilities', [])
                        vuln_types = [v.get('type') if isinstance(v, dict) else str(v) for v in vulnerabilities]
                        for vuln in expected_value if isinstance(expected_value, list) else [expected_value]:
                            if vuln not in vuln_types:
                                failures.append(f'known vulnerability not detected: {vuln}')
                                failed = True
                elif key == 'results_not_empty':
                    if output is None:
                        failures.append(f'Output is None, cannot check results')
                        failed = True
                    else:
                        results = output.get('results', [])
                        if expected_value and not results:
                            failures.append(f'results is empty but should not be')
                            failed = True
                # Standard field validation
                elif output is None:
                    failures.append(f'Output is None, cannot check key {key}')
                    failed = True
                elif key not in output:
                    failures.append(f'Missing key in output: {key}')
                    failed = True
                elif output[key] != expected_value:
                    failures.append(f'Key {key}: expected {expected_value}, got {output[key]}')
                    failed = True

        # Check must_not constraints
        if output is not None:
            must_not = test_def.get('must_not', [])
            for constraint in must_not:
                # Handle both string and dict formats
                if isinstance(constraint, str):
                    # String format: field name that must not exist in output
                    if constraint in output:
                        failures.append(f'Forbidden field found: {constraint}')
                        failed = True
                elif isinstance(constraint, dict):
                    # Dict format: field=value that must not match
                    for key, forbidden_value in constraint.items():
                        if key in output and output[key] == forbidden_value:
                            failures.append(f'Forbidden value found: {key}={forbidden_value}')
                            failed = True
                else:
                    logger.warning(f"Invalid must_not constraint type: {type(constraint)}")

        # Run checks
        checks = test_def.get('checks', [])
        check_results = []
        if output is not None:
            for check in checks:
                check_type = check.get('type')
                if check_type == 'schema_validity':
                    # Basic schema check - ensure output has required fields
                    required_fields = check.get('required_fields', [])
                    for field in required_fields:
                        if field not in output:
                            check_results.append(f'FAIL: Missing required field {field}')
                            failed = True
                        else:
                            check_results.append(f'PASS: Field {field} present')
                elif check_type == 'performance':
                    max_duration = check.get('max_duration_ms', 10000)
                    duration = int((time.time() - start_time) * 1000)
                    if duration > max_duration:
                        check_results.append(f'FAIL: Duration {duration}ms exceeds max {max_duration}ms')
                        failed = True
                    else:
                        check_results.append(f'PASS: Duration {duration}ms within limit')
                elif check_type == 'content_validation':
                    # Check for required/forbidden content
                    required_content = check.get('required_content', [])
                    forbidden_content = check.get('forbidden_content', [])
                    required_files = check.get('required_files', [])

                    for content in required_content:
                        if content not in str(output):
                            check_results.append(f'FAIL: Required content not found: {content}')
                            failed = True
                        else:
                            check_results.append(f'PASS: Required content found: {content}')

                    for content in forbidden_content:
                        if content in str(output):
                            check_results.append(f'FAIL: Forbidden content found: {content}')
                            failed = True
                        else:
                            check_results.append(f'PASS: Forbidden content not found: {content}')

                    for filename in required_files:
                        if filename not in str(output):
                            check_results.append(f'FAIL: Required file not found: {filename}')
                            failed = True
                        else:
                            check_results.append(f'PASS: Required file found: {filename}')

                elif check_type == 'field_type_validation':
                    # Check field types
                    for field, expected_type in check.items():
                        if field == 'type':
                            continue
                        if field in output:
                            type_map = {'str': str, 'int': int, 'bool': bool, 'list': list, 'dict': dict}
                            if expected_type in type_map and not isinstance(output[field], type_map[expected_type]):
                                check_results.append(f'FAIL: Field {field} has wrong type')
                                failed = True
                            else:
                                check_results.append(f'PASS: Field {field} has correct type')

                elif check_type == 'non_empty_check':
                    # Check fields are not empty
                    fields = check.get('fields', [])
                    for field in fields:
                        if field in output:
                            if isinstance(output[field], (str, list, dict)) and len(output[field]) == 0:
                                check_results.append(f'FAIL: Field {field} is empty')
                                failed = True
                            else:
                                check_results.append(f'PASS: Field {field} is not empty')
                        else:
                            check_results.append(f'FAIL: Field {field} missing')
                            failed = True

                else:
                    logger.warning(f"Unknown check type '{check_type}' in test {test_def.get('test_id')}")
                    check_results.append(f'WARN: Unknown check type {check_type}')

        duration_ms = int((time.time() - start_time) * 1000)

        if failed:
            return {
                'status': 'failed',
                'test_id': test_def['test_id'],
                'duration_ms': duration_ms,
                'output': output,
                'expected': expected,
                'failures': failures,
                'check_results': check_results
            }

        return {
            'status': 'passed',
            'test_id': test_def['test_id'],
            'duration_ms': duration_ms,
            'output': output,
            'expected': expected,
            'check_results': check_results
        }
    
    def _run_python_test(self, test_def: Dict) -> Dict:
        """Run a Python test file"""
        import subprocess

        # Check if pytest is available
        pytest_check = subprocess.run(['python3', '-c', 'import pytest'], capture_output=True)
        if pytest_check.returncode != 0:
            return {
                'status': 'error',
                'test_id': test_def['test_id'],
                'error': 'pytest is not installed. Please install it with: pip install pytest pyyaml',
                'duration_ms': 0
            }

        start_time = time.time()

        # Run pytest on the file
        result = subprocess.run(
            ['python3', '-m', 'pytest', test_def['file'], '-v'],
            capture_output=True,
            text=True,
            cwd=str(self.test_root.parent)
        )

        return {
            'status': 'passed' if result.returncode == 0 else 'failed',
            'test_id': test_def['test_id'],
            'duration_ms': int((time.time() - start_time) * 1000),
            'exit_code': result.returncode,
            'stdout': result.stdout[-1000:] if result.stdout else '',
            'stderr': result.stderr[-1000:] if result.stderr else ''
        }
    
    def _update_summary(self, result: Dict):
        """Update run summary based on test result"""
        status = result.get('status', 'error')
        if status == 'passed':
            self.current_run['summary']['passed'] += 1
        elif status == 'failed':
            self.current_run['summary']['failed'] += 1
        elif status == 'skipped':
            self.current_run['summary']['skipped'] += 1
        else:
            self.current_run['summary']['errors'] += 1
    
    def get_run_report(self) -> Dict:
        """Get a detailed report of the current run"""
        if not self.current_run:
            return {'error': 'No run has been executed'}
        
        return {
            'run_id': self.current_run['run_id'],
            'summary': self.current_run['summary'],
            'duration': self.current_run['duration'],
            'success_rate': self.current_run['summary']['passed'] / self.current_run['summary']['total'] if self.current_run['summary']['total'] > 0 else 0,
            'failed_tests': [
                test_id for test_id, result in self.current_run['results'].items()
                if result.get('status') == 'failed'
            ],
            'error_tests': [
                test_id for test_id, result in self.current_run['results'].items()
                if result.get('status') == 'error'
            ]
        }
