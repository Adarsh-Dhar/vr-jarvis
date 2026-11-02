#!/usr/bin/env python3
"""Generate signature-driven adapter code for batch_execute_tests.py."""

import json

# Load parameter mapping
with open('/Users/adarsh/Documents/vr-agent/jarvis-tests/test-runner/parameter_mapping.json', 'r') as f:
    parameter_mapping = json.load(f)

# Group tools by signature pattern
context_only = []
simple_params = []
complex_params = []

for tool_name, sig in parameter_mapping.items():
    if sig['param_count'] == 1 and sig['params'][0]['name'] == 'tool_context':
        context_only.append(tool_name)
    elif sig['param_count'] == 2 and 'tool_context' in sig['required']:
        # Simple: one param + tool_context
        other_params = [p for p in sig['required'] if p != 'tool_context']
        if other_params:
            simple_params.append((tool_name, other_params[0]))
        else:
            complex_params.append(tool_name)
    else:
        complex_params.append(tool_name)

print(f"Context-only tools: {len(context_only)}")
print(f"Simple param tools: {len(simple_params)}")
print(f"Complex param tools: {len(complex_params)}")

# Generate code for context-only tools
print("\n# Context-only tools (only take tool_context)")
print("context_only_tools = [")
for tool in sorted(context_only):
    print(f"    '{tool}',")
print("]")

# Generate code for simple param tools
print("\n# Simple param tools (one param + tool_context)")
print("simple_param_tools = {")
for tool, param in sorted(simple_params):
    print(f"    '{tool}': '{param}',")
print("}")

# Generate code for complex param tools
print("\n# Complex param tools (need special handling)")
print("complex_param_tools = [")
for tool in sorted(complex_params):
    sig = parameter_mapping[tool]
    print(f"    # {tool}: required={sig['required']}, optional={sig['optional']}")
print("]")

# Generate a generic adapter function
print("\n# Generic signature-driven adapter")
print("""
def call_tool_with_signature(tool_name, tool_func, input_data, tool_context):
    '''Call a tool using its signature to map input_data to parameters.'''
    sig = parameter_mapping.get(tool_name)
    if not sig:
        # Fallback: try calling with just tool_context
        return tool_func(tool_context)
    
    # Build arguments from signature
    kwargs = {}
    for param in sig['params']:
        param_name = param['name']
        if param_name == 'tool_context':
            kwargs['tool_context'] = tool_context
        else:
            # Get value from input_data
            if param_name in input_data:
                kwargs[param_name] = input_data[param_name]
            elif not param['has_default']:
                # Missing required parameter
                kwargs[param_name] = None  # Or raise error
    
    return tool_func(**kwargs)
""")
