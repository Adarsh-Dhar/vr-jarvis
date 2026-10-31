#!/usr/bin/env python3
"""Verify all 14 core tools pass"""
import sys
import yaml
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))
sys.path.insert(0, str(Path(__file__).parent))

from test_orchestrator import TestOrchestrator

test_root = Path(__file__).parent.parent
orchestrator = TestOrchestrator(test_root, None)

core_tools_dir = test_root / 'tests' / 'core-tools'
yaml_files = sorted(core_tools_dir.glob('*.yaml'))

passed = 0
failed = 0
errors = 0

for yaml_file in yaml_files:
    with open(yaml_file, 'r') as f:
        test_def = yaml.safe_load(f)
    
    test_id = test_def.get('test_id')
    result = orchestrator._run_yaml_test(test_def)
    status = result.get('status')
    
    if status == 'passed':
        passed += 1
        print(f"✓ {test_id}")
    elif status == 'failed':
        failed += 1
        print(f"✗ {test_id}: {result.get('failures', [])[:1]}")
    elif status == 'skipped':
        print(f"⊘ {test_id}: {result.get('reason', '')}")
    else:
        errors += 1
        print(f"✗ {test_id}: {result.get('error', '')[:50]}")

print(f"\nResults: {passed} passed, {failed} failed, {errors} errors")
print(f"Total: {len(yaml_files)}")
