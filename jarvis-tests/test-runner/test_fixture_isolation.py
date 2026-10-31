#!/usr/bin/env python3
"""
Test fixture isolation with destructive operations
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path('.').parent.parent / 'server'))
sys.path.insert(0, str(Path('.')))

from test_orchestrator import TestOrchestrator

def test_delete_file_isolation():
    """Test that delete_file doesn't mutate shared fixture"""
    test_def = {
        'test_id': 'TEST-delete-file-isolation',
        'tool': 'delete_file',
        'fixture': 'simple-python',
        'input': {
            'file_path': 'fixtures/repositories/simple-python/main.py'
        },
        'expected': {
            'status': 'ok'
        },
        'must_not': ['error'],
        'checks': []
    }

    test_root = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests')
    orchestrator = TestOrchestrator(test_root, None)

    # Run the test twice
    print("=== First run ===")
    result1 = orchestrator._run_yaml_test(test_def)
    print(f"Result status: {result1.get('status')}")

    # Check if file still exists in shared fixture
    shared_file = test_root / 'fixtures' / 'repositories' / 'simple-python' / 'main.py'
    print(f"Shared file exists after first run: {shared_file.exists()}")

    print("\n=== Second run ===")
    result2 = orchestrator._run_yaml_test(test_def)
    print(f"Result status: {result2.get('status')}")

    # Check if file still exists in shared fixture
    print(f"Shared file exists after second run: {shared_file.exists()}")

    if shared_file.exists():
        print("\nSUCCESS: Fixture isolation working - shared file not mutated")
    else:
        print("\nFAILURE: Fixture isolation broken - shared file was deleted")

if __name__ == '__main__':
    test_delete_file_isolation()
