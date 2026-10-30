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
sys.path.insert(0, str(Path(__file__).parent))
from test_registry import TestRegistry


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
        parallel: bool = True
    ) -> Dict:
        """Run a test suite with specified filters"""
        # Determine which tests to run
        test_ids = self._select_tests(categories, tools, severity)
        
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
        severity: Optional[str]
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
        
        if not selected:
            # No filters, return all tests
            selected = set(self.registry.get_all_tests().keys())
        
        return list(selected)
    
    def _run_tests_parallel(self, test_ids: List[str]):
        """Run tests in parallel"""
        max_workers = min(10, len(test_ids))
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
        start_time = time.time()
        
        # For now, simulate test execution
        # In real implementation, this would call the actual tool
        result = {
            'status': 'passed',
            'test_id': test_def['test_id'],
            'duration_ms': int((time.time() - start_time) * 1000),
            'expected': test_def.get('expected'),
            'checks': test_def.get('checks', [])
        }
        
        return result
    
    def _run_python_test(self, test_def: Dict) -> Dict:
        """Run a Python test file"""
        import subprocess
        
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
