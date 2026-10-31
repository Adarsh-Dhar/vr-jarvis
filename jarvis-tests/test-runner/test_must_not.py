#!/usr/bin/env python3
"""
Test must_not handling with string format
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path('.').parent.parent / 'server'))
sys.path.insert(0, str(Path('.')))

from test_orchestrator import TestOrchestrator

def test_must_not_string():
    """Test that must_not as string works"""
    test_def = {
        'test_id': 'TEST-must-not-string',
        'tool': 'read_file',
        'input': {
            'file_path': 'fixtures/repositories/simple-python/main.py'
        },
        'expected': {
            'status': 'ok'
        },
        'must_not': ['error'],  # String format
        'checks': []
    }

    test_root = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests')
    orchestrator = TestOrchestrator(test_root, None)

    result = orchestrator._run_yaml_test(test_def)
    print(f"Result status: {result.get('status')}")
    if result.get('status') == 'error':
        print(f"Error: {result.get('error')}")
    elif result.get('status') == 'failed':
        print(f"Failures: {result.get('failures')}")
    else:
        print("Test passed!")

def test_must_not_dict():
    """Test that must_not as dict works"""
    test_def = {
        'test_id': 'TEST-must-not-dict',
        'tool': 'read_file',
        'input': {
            'file_path': 'fixtures/repositories/simple-python/main.py'
        },
        'expected': {
            'status': 'ok'
        },
        'must_not': [{'status': 'error'}],  # Dict format
        'checks': []
    }

    test_root = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests')
    orchestrator = TestOrchestrator(test_root, None)

    result = orchestrator._run_yaml_test(test_def)
    print(f"\nResult status: {result.get('status')}")
    if result.get('status') == 'error':
        print(f"Error: {result.get('error')}")
    elif result.get('status') == 'failed':
        print(f"Failures: {result.get('failures')}")
    else:
        print("Test passed!")

if __name__ == '__main__':
    print("=== Testing must_not as string ===")
    test_must_not_string()
    print("\n=== Testing must_not as dict ===")
    test_must_not_dict()
