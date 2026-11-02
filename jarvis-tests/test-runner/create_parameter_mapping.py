#!/usr/bin/env python3
"""Create parameter mapping from tool signatures."""

import json
import sys
sys.path.insert(0, '/Users/adarsh/Documents/vr-agent/jarvis-tests/test-runner')

# Load tool signatures
with open('/Users/adarsh/Documents/vr-agent/jarvis-tests/test-runner/tool_signatures.json', 'r') as f:
    tool_signatures = json.load(f)

# Import batch executor to get TOOL_FUNCTIONS
import batch_execute_tests
tool_functions = batch_execute_tests.TOOL_FUNCTIONS

print(f"TOOL_FUNCTIONS has {len(tool_functions)} entries")
print(f"tool_signatures has {len(tool_signatures)} entries")

# Create parameter mapping
parameter_mapping = {}

for tool_name, sig in tool_signatures.items():
    if tool_name in tool_functions:
        param_info = {
            'params': sig['params'],
            'required': sig['required'],
            'optional': sig['optional'],
            'param_count': sig['param_count']
        }
        parameter_mapping[tool_name] = param_info

# Save parameter mapping
with open('/Users/adarsh/Documents/vr-agent/jarvis-tests/test-runner/parameter_mapping.json', 'w') as f:
    json.dump(parameter_mapping, f, indent=2)

print(f"\nParameter mapping created for {len(parameter_mapping)} tools")
print(f"Saved to parameter_mapping.json")

# Print examples
print("\nExamples of tools needing adapters:")
count = 0
for tool_name, sig in sorted(parameter_mapping.items()):
    if sig['param_count'] > 1 or (sig['param_count'] == 1 and sig['params'][0]['name'] != 'tool_context'):
        print(f"\n{tool_name}:")
        print(f"  Required: {sig['required']}")
        print(f"  Optional: {sig['optional']}")
        count += 1
        if count >= 10:
            break
