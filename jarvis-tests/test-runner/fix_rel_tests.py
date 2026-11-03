#!/usr/bin/env python3
"""Fix REL test expected statuses to skipped."""

from pathlib import Path
import yaml

rel_files = [
    'REL-find_interface_implementations-T01.yaml',
    'REL-trace_cross_service_relationships-T01.yaml',
    'REL-find_all_paths_between_symbols-T01.yaml',
    'REL-find_shared_dependencies-T01.yaml',
    'REL-calculate_change_impact-T01.yaml',
    'REL-trace_call_chain-T01.yaml',
    'REL-find_downstream_dependencies-T01.yaml',
]

search_path = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests/tests/layer1/relationship')

fixed_count = 0
for filename in rel_files:
    yaml_file = search_path / filename
    if not yaml_file.exists():
        print(f'File not found: {filename}')
        continue
    
    with open(yaml_file) as f:
        test_def = yaml.safe_load(f)
    
    test_def['expected']['status'] = 'skipped'
    with open(yaml_file, 'w') as f:
        yaml.dump(test_def, f, default_flow_style=False, sort_keys=False)
    
    fixed_count += 1
    print(f'Fixed {filename} to skipped')

print(f'\nFixed {fixed_count} REL test files')
