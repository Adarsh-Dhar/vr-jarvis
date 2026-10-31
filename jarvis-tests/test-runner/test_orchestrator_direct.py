#!/usr/bin/env python3
"""
Test orchestrator directly with single test
"""

import sys
from pathlib import Path
import yaml
import time

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))
sys.path.insert(0, str(Path(__file__).parent))

from test_orchestrator import TestOrchestrator

def test_orchestrator_direct():
    """Test orchestrator with a manually created test definition"""
    # Load the YAML file directly
    yaml_file = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests/tests/core-tools/CORE-read_file-T01.yaml')
    print(f"Loading {yaml_file}")
    with open(yaml_file, 'r') as f:
        test_def = yaml.safe_load(f)

    print(f"Test ID: {test_def.get('test_id')}")
    print(f"Tool: {test_def.get('tool')}")
    print(f"Input: {test_def.get('input')}")

    # Create orchestrator
    test_root = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests')
    orchestrator = TestOrchestrator(test_root, None)  # Pass None for registry

    # Run the test directly
    print("\n=== Running test ===")
    result = orchestrator._run_yaml_test(test_def)

    print(f"\nResult status: {result.get('status')}")
    if result.get('status') == 'error':
        print(f"Error: {result.get('error')}")
        if result.get('input_args'):
            print(f"Input args: {result.get('input_args')}")
    elif result.get('status') == 'failed':
        print(f"Failures: {result.get('failures')}")
        print(f"Check results: {result.get('check_results')}")
    else:
        print("Test passed!")
        print(f"Duration: {result.get('duration_ms')}ms")

if __name__ == '__main__':
    test_orchestrator_direct()
