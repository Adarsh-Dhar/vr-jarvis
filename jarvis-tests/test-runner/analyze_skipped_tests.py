#!/usr/bin/env python3
"""Analyze skipped tests to understand placeholder patterns."""

import yaml
from pathlib import Path
from collections import defaultdict

workspace = Path('/Users/adarsh/Documents/vr-agent')
test_dirs = [
    'jarvis-tests/tests/core-tools',
    'jarvis-tests/tests/real-input/relationship',
    'jarvis-tests/tests/real-input/code_understanding',
    'jarvis-tests/tests/real-input/analysis',
    'jarvis-tests/tests/real-input/api_database',
    'jarvis-tests/tests/real-input/data_flow',
    'jarvis-tests/tests/real-input/misc',
    'jarvis-tests/tests/real-input/security_quality',
    'jarvis-tests/tests/unit/relationships',
    'jarvis-tests/tests/layer1/code_understanding',
    'jarvis-tests/tests/layer1/relationship',
    'jarvis-tests/tests/layer1/repository_intelligence',
    'jarvis-tests/tests/real-input/repository_intelligence',
    'jarvis-tests/tests/layer1/analysis',
    'jarvis-tests/tests/layer1/api_database',
    'jarvis-tests/tests/layer1/data_flow',
    'jarvis-tests/tests/layer1/misc',
    'jarvis-tests/tests/layer1/security_quality',
    'jarvis-tests/tests/layer2/analysis',
    'jarvis-tests/tests/layer2/api_database',
    'jarvis-tests/tests/layer2/code_understanding',
    'jarvis-tests/tests/layer2/data_flow',
    'jarvis-tests/tests/layer2/relationship',
    'jarvis-tests/tests/layer2/repository_intelligence',
    'jarvis-tests/tests/layer2/security_quality',
    'jarvis-tests/tests/layer2/misc',
    'jarvis-tests/tests/layer3',
    'jarvis-tests/tests/layer3/integration',
    'jarvis-tests/tests/layer4',
    'jarvis-tests/tests/layer4/agent-capabilities',
    'jarvis-tests/tests/layer5',
    'jarvis-tests/tests/layer5/multi-agent',
    'jarvis-tests/tests/layer6',
    'jarvis-tests/tests/layer6/end-to-end',
    'jarvis-tests/tests/layer7',
    'jarvis-tests/tests/layer7/stress',
    'jarvis-tests/tests/repository_intelligence',
    'jarvis-tests/tests/security_quality',
    'jarvis-tests/tests/integration',
    'jarvis-tests/tests/stress',
    'jarvis-tests/tests/multi-agent',
    'jarvis-tests/tests/end-to-end',
    'jarvis-tests/tests/agent-capabilities',
    'jarvis-tests/tests/chaos',
    'jarvis-tests/tests/code_understanding',
    'jarvis-tests/tests/load',
    'jarvis-tests/tests/phase2_core_tools',
    'jarvis-tests/tests/regression',
    'jarvis-tests/tests/security',
    'jarvis-tests/tests/verified',
    'jarvis-tests/tests/verified/analysis',
    'jarvis-tests/tests/unit/data-flow',
    'jarvis-tests/tests/unit/parsing',
    'jarvis-tests/tests/unit/repository',
    'jarvis-tests/tests/unit/runtime',
    'jarvis-tests/tests/unit/security',
    'jarvis-tests/tests/unit/symbols',
    'jarvis-tests/tests/unit/visualization',
]

skipped_by_tool = defaultdict(list)
skipped_by_reason = defaultdict(list)
placeholder_patterns = []

for test_dir in test_dirs:
    test_path = workspace / test_dir
    if not test_path.exists():
        continue
    
    for yaml_file in test_path.rglob('*.yaml'):
        try:
            with open(yaml_file) as f:
                test = yaml.safe_load(f)
            
            # Check if test is marked as skipped
            if test.get('expected', {}).get('status') == 'skipped':
                tool = test.get('tool', 'unknown')
                skipped_by_tool[tool].append(str(yaml_file))
                
                # Analyze input for placeholder patterns
                inputs = test.get('input', {})
                has_placeholder = False
                
                for key, value in inputs.items():
                    if isinstance(value, str) and ('placeholder' in value.lower() or value in ['N/A', 'TBD', 'NONE', 'null']):
                        has_placeholder = True
                        placeholder_patterns.append((tool, key, value, str(yaml_file)))
                
                if has_placeholder:
                    skipped_by_reason['placeholder'].append(str(yaml_file))
                else:
                    skipped_by_reason['other'].append(str(yaml_file))
        except Exception as e:
            pass

print(f'Total skipped tests: {sum(len(tests) for tests in skipped_by_tool.values())}')
print(f'\nSkipped by tool (top 20):')
for tool, tests in sorted(skipped_by_tool.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
    print(f'  {tool}: {len(tests)} tests')

print(f'\nSkipped by reason:')
for reason, tests in skipped_by_reason.items():
    print(f'  {reason}: {len(tests)} tests')

print(f'\nPlaceholder patterns (top 20):')
for pattern in placeholder_patterns[:20]:
    print(f'  {pattern[0]}.{pattern[1]} = {pattern[2]}')
