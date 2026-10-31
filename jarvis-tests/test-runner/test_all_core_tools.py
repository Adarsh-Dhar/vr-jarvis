#!/usr/bin/env python3
"""
Test all 14 core tools with the fixed runner
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

    print(f"Found {len(yaml_files)} core tool specs")
    print("=" * 60)

    passed = 0
    failed = 0
    errors = 0

    for yaml_file in yaml_files:
        with open(yaml_file, 'r') as f:
            test_def = yaml.safe_load(f)

        test_id = test_def.get('test_id')
        tool_name = test_def.get('tool')

        print(f"\nTesting {test_id} (tool: {tool_name})")

        result = orchestrator._run_yaml_test(test_def)
        status = result.get('status')

        if status == 'passed':
            print(f"  ✓ PASSED")
            passed += 1
        elif status == 'failed':
            print(f"  ✗ FAILED")
            failures = result.get('failures', [])
            for failure in failures[:3]:  # Show first 3 failures
                print(f"    - {failure}")
            failed += 1
        else:
            print(f"  ✗ ERROR: {result.get('error')}")
            errors += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {errors} errors")
    print(f"Total: {len(yaml_files)}")

    return passed == len(yaml_files)


if __name__ == '__main__':
    success = test_all_core_tools()
    sys.exit(0 if success else 1)
