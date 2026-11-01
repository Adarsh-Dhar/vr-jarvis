#!/usr/bin/env python3
"""
Execute a real test against actual tool implementation
"""
import sys
from pathlib import Path

# Add server to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))

from ai_agents.tools import repository_tools
from google.adk.tools import ToolContext
import yaml

# Mock ToolContext for testing
class MockToolContext:
    def __init__(self):
        pass

def execute_read_file_test():
    """Execute CORE-read_file-T01 test"""
    test_file = Path('../tests/core-tools/CORE-read_file-T01.yaml')
    with open(test_file) as f:
        test_def = yaml.safe_load(f)

    print(f"Executing test: {test_def['test_id']}")
    print(f"Description: {test_def['description']}")
    print(f"Tool: {test_def['tool']}")
    print(f"Fixture: {test_def['fixture']}")
    print()

    # Get input
    input_data = test_def['input']
    file_path = input_data['file_path']

    # Resolve path relative to jarvis-tests
    test_root = Path('..')
    full_path = test_root / file_path

    print(f"Reading file: {full_path}")
    print(f"File exists: {full_path.exists()}")

    if not full_path.exists():
        print("ERROR: File not found")
        return

    # Execute actual tool
    try:
        tool_context = MockToolContext()
        result = repository_tools.read_file(full_path, tool_context)
        print(f"\nTool result status: {result.get('status')}")
        print(f"File path: {result.get('file_path')}")
        print(f"Content length: {len(result.get('content', ''))} chars")
        print(f"Line count: {result.get('line_count')}")

        # Check expected results
        expected = test_def['expected']
        print(f"\nExpected status: {expected.get('status')}")
        print(f"Expected line count: {expected.get('line_count')}")

        if 'content_contains' in expected:
            content = result.get('content', '')
            for expected_str in expected['content_contains']:
                found = expected_str in content
                print(f"  '{expected_str}' in content: {found}")

        print("\nTest PASSED" if result.get('status') == 'ok' else "Test FAILED")

    except Exception as e:
        print(f"ERROR executing tool: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    execute_read_file_test()
