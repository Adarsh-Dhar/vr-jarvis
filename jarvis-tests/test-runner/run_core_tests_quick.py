#!/usr/bin/env python3
"""
Quick test runner for core tools - minimal output
"""

import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))
sys.path.insert(0, str(Path(__file__).parent))

from test_orchestrator import TestOrchestrator

def test_all_core_tools():
    """Test all core tools"""
    test_root = Path(__file__).parent.parent
    orchestrator = TestOrchestrator(test_root, None)

    core_tools_dir = test_root / 'tests' / 'core-tools'
    yaml_files = sorted(core_tools_dir.glob('*.yaml'))

    passed = 0
    failed = 0
    errors = 0
    results = []

    for yaml_file in yaml_files:
        with open(yaml_file, 'r') as f:
            test_def = yaml.safe_load(f)

        test_id = test_def.get('test_id')
        tool_name = test_def.get('tool')

        result = orchestrator._run_yaml_test(test_def)
        status = result.get('status')

        results.append((test_id, status, result.get('failures', []), result.get('error', '')))

        if status == 'passed':
            passed += 1
        elif status == 'failed':
            failed += 1
        else:
            errors += 1

    print(f"Results: {passed} passed, {failed} failed, {errors} errors")
    print("\nFailed tests:")
    for test_id, status, failures, error in results:
        if status != 'passed':
            print(f"  {test_id}: {status}")
            if failures:
                for f in failures[:2]:
                    print(f"    - {f}")
            if error:
                print(f"    - {error}")

    return passed == len(yaml_files)

if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')
    test_all_core_tools()
