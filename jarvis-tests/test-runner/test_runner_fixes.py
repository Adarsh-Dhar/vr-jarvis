#!/usr/bin/env python3
"""
Test script to verify runner fixes
"""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))
sys.path.insert(0, str(Path(__file__).parent))

from test_registry import TestRegistry
from test_orchestrator import TestOrchestrator

def test_runner_fixes():
    """Test that runner fixes work correctly"""
    # Use absolute path to jarvis-tests
    test_root = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests')
    print(f"Test root: {test_root.absolute()}")

    # Initialize registry
    registry = TestRegistry(test_root)
    registry.load_test_definitions()

    print(f"Total tests loaded: {len(registry.get_all_tests())}")

    # Test CORE-read_file-T01
    test_id = 'CORE-read_file-T01'
    test_def = registry.get_test(test_id)
    if not test_def:
        print(f"ERROR: Test not found: {test_id}")
        return False

    print(f"\n=== Testing {test_id} ===")
    print(f"Tool: {test_def.get('tool')}")
    input_data = test_def.get('input', {}).copy()
    print(f"Input: {input_data}")
    print(f"Must_not: {test_def.get('must_not')}")

    # Run the test
    orchestrator = TestOrchestrator(test_root, registry)
    result = orchestrator._run_single_test(test_id)

    print(f"\nResult status: {result.get('status')}")
    if result.get('status') == 'error':
        print(f"Error: {result.get('error')}")
        print(f"Input args: {result.get('input_args')}")
        return False
    elif result.get('status') == 'failed':
        print(f"Failures: {result.get('failures')}")
        print(f"Check results: {result.get('check_results')}")
        return False
    else:
        print("Test passed!")
        return True

if __name__ == '__main__':
    success = test_runner_fixes()
    sys.exit(0 if success else 1)
