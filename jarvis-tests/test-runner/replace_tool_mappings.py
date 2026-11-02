#!/usr/bin/env python3
"""Replace TOOL_FUNCTIONS dictionary with validated mappings"""
import re

# Read the original file
with open('/Users/adarsh/Documents/vr-agent/jarvis-tests/test-runner/batch_execute_tests.py', 'r') as f:
    content = f.read()

# Read the new mappings
with open('/tmp/tool_mappings_only.txt', 'r') as f:
    new_mappings = f.read()

# Find and replace the TOOL_FUNCTIONS dictionary
pattern = r'# Tool mapping.*?\n}'
content = re.sub(pattern, new_mappings, content, flags=re.DOTALL)

# Write back
with open('/Users/adarsh/Documents/vr-agent/jarvis-tests/test-runner/batch_execute_tests.py', 'w') as f:
    f.write(content)

print("Replaced TOOL_FUNCTIONS dictionary")
