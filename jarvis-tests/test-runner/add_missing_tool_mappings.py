#!/usr/bin/env python3
"""Add missing tool mappings from server to batch executor"""
import re
from pathlib import Path

WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')
TOOLS_DIR = WORKSPACE / 'server/ai_agents/tools'

# Find all function definitions in server tools
server_functions = {}
for py_file in TOOLS_DIR.glob('*.py'):
    if py_file.name.startswith('_'):
        continue
    try:
        with open(py_file) as f:
            content = f.read()
        # Find all function definitions
        for match in re.finditer(r'def (\w+)\(', content):
            func_name = match.group(1)
            if not func_name.startswith('_'):
                server_functions[func_name] = py_file.name
    except:
        pass

print(f"Found {len(server_functions)} functions in server tools")

# Get unmapped tools from test suite
import yaml
TESTS_DIR = WORKSPACE / 'jarvis-tests/tests'
test_tools = set()
for yaml_file in TESTS_DIR.rglob('*.yaml'):
    try:
        with open(yaml_file) as f:
            test = yaml.safe_load(f)
        if test and test.get('tool'):
            test_tools.add(test['tool'])
    except:
        pass

# Get currently mapped tools
import sys
sys.path.insert(0, str(WORKSPACE / 'jarvis-tests/test-runner'))
from batch_execute_tests import TOOL_FUNCTIONS

mapped_tools = set(TOOL_FUNCTIONS.keys())

# Find tools that exist in server but aren't mapped
missing_mappings = []
for tool in test_tools:
    if tool not in mapped_tools and tool in server_functions:
        missing_mappings.append((tool, server_functions[tool]))

print(f"\n{len(missing_mappings)} tools exist in server but aren't mapped")
print("\nExample mappings to add:")
for tool, module in sorted(missing_mappings)[:20]:
    print(f"  '{tool}': {module.replace('.py', '')}.{tool},")

print(f"\n... and {len(missing_mappings) - 20} more")
