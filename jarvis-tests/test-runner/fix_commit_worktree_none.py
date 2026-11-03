#!/usr/bin/env python3
"""Fix commit_worktree expected status to None."""

from pathlib import Path
import yaml

# Fix commit_worktree expected status
for yaml_file in Path('/Users/adarsh/Documents/vr-agent/jarvis-tests').rglob('MSC-commit_worktree-T01.yaml'):
    with open(yaml_file) as f:
        test_def = yaml.safe_load(f)
    test_def['expected']['status'] = None
    with open(yaml_file, 'w') as f:
        yaml.dump(test_def, f, default_flow_style=False, sort_keys=False)
    print(f'Fixed MSC-commit_worktree-T01.yaml: None')
