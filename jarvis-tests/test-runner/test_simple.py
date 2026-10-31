#!/usr/bin/env python3
"""
Simple test without registry
"""

import sys
from pathlib import Path
import yaml
import time

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))

def test_single_yaml():
    """Test loading and running a single YAML test"""
    # Load the YAML file directly
    yaml_file = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests/tests/core-tools/CORE-read_file-T01.yaml')
    print(f"Loading {yaml_file}")
    with open(yaml_file, 'r') as f:
        test_def = yaml.safe_load(f)

    print(f"Test ID: {test_def.get('test_id')}")
    print(f"Tool: {test_def.get('tool')}")
    print(f"Input: {test_def.get('input')}")

    # Import tools
    from ai_agents import tools
    tool_name = test_def.get('tool')
    tool_func = getattr(tools, tool_name, None)
    print(f"Tool function: {tool_func}")

    # Create mock ToolContext
    class MockToolContext:
        def __init__(self):
            self.state = {}

    tool_context = MockToolContext()

    # Prepare input
    input_args = test_def.get('input', {}).copy()
    file_path = input_args.get('file_path')
    if file_path and 'fixtures/repositories' in file_path:
        # Make absolute
        test_root = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests')
        input_args['file_path'] = str(test_root / file_path)

    # Remove placeholder tool_context
    if 'tool_context' in input_args and input_args['tool_context'] == 'placeholder':
        del input_args['tool_context']

    print(f"Calling tool with: {input_args}")

    # Call the tool
    start_time = time.time()
    try:
        output = tool_func(**input_args, tool_context=tool_context)
        duration_ms = int((time.time() - start_time) * 1000)
        print(f"Duration: {duration_ms}ms")
        print(f"Output status: {output.get('status')}")
        if output.get('status') == 'error':
            print(f"Error: {output.get('error')}")
        else:
            print(f"File path: {output.get('file_path')}")
            print(f"Content length: {len(output.get('content', ''))}")
            print("SUCCESS!")
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_single_yaml()
