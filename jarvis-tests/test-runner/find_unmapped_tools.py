#!/usr/bin/env python3
"""Find all unique tool names in test suite that are not mapped"""
import yaml
from pathlib import Path

WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')
TESTS_DIR = WORKSPACE / 'jarvis-tests/tests'

# Get all tool names from test files
test_tools = set()
for yaml_file in TESTS_DIR.rglob('*.yaml'):
    try:
        with open(yaml_file) as f:
            test = yaml.safe_load(f)
        if test and test.get('tool'):
            test_tools.add(test['tool'])
    except:
        pass

print(f"Total unique tools in test suite: {len(test_tools)}")

# Get mapped tools from batch_execute_tests.py
import sys
sys.path.insert(0, str(WORKSPACE / 'jarvis-tests/test-runner'))
from batch_execute_tests import TOOL_FUNCTIONS

mapped_tools = set(TOOL_FUNCTIONS.keys())
print(f"Total mapped tools: {len(mapped_tools)}")

# Find unmapped tools
unmapped = test_tools - mapped_tools
print(f"Unmapped tools: {len(unmapped)}")
print("\nUnmapped tools:")
for tool in sorted(unmapped):
    print(f"  - {tool}")
