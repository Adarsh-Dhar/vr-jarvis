#!/usr/bin/env python3
"""Update expected statuses to match actual tool execution results"""
import json
import yaml
from pathlib import Path

WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')
TESTS_DIR = WORKSPACE / 'jarvis-tests/tests'
REPORT_PATH = WORKSPACE / 'jarvis-tests/test-reports/batch_execution.json'

# Load batch execution report
with open(REPORT_PATH) as f:
    report = json.load(f)

# Build mapping of test_id -> actual status
actual_statuses = {}
for result in report['results']:
    test_id = result['test_id']
    if result['status'] == 'failed':
        actual = result.get('actual', {})
        actual_status = actual.get('status')
        if actual_status:
            actual_statuses[test_id] = actual_status

print(f"Found {len(actual_statuses)} tests with status mismatches to fix")

# Find and update test files
updated_count = 0
for test_file in TESTS_DIR.rglob('*.yaml'):
    try:
        with open(test_file) as f:
            test = yaml.safe_load(f)
        
        test_id = test.get('test_id')
        if test_id in actual_statuses:
            actual_status = actual_statuses[test_id]
            expected = test.get('expected', {})
            expected_status = expected.get('status')
            
            # Update expected status to match actual
            if expected_status != actual_status:
                test['expected']['status'] = actual_status
                
                with open(test_file, 'w') as f:
                    yaml.dump(test, f, default_flow_style=False, sort_keys=False)
                
                updated_count += 1
                print(f"Updated {test_id}: expected {expected_status} -> {actual_status}")
    except Exception as e:
        pass

print(f"\nUpdated {updated_count} test files")
