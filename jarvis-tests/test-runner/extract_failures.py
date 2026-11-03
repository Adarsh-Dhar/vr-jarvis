#!/usr/bin/env python3
"""Extract failing tests from batch execution report."""

import json
from pathlib import Path

report_path = Path('/Users/adarsh/Documents/vr-agent/jarvis-tests/test-reports/batch_execution.json')
with open(report_path) as f:
    report = json.load(f)

print(f"Report structure: {type(report)}")
if isinstance(report, dict):
    if 'results' in report:
        tests = report['results']
    elif 'tests' in report:
        tests = report['tests']
    else:
        print(f"Keys: {report.keys()}")
        if 'results' in report:
            print(f"Sample result: {report['results'][0] if report['results'] else 'empty'}")
        tests = []
elif isinstance(report, list):
    tests = report
else:
    tests = []

failures = [test for test in tests if test.get('status') == 'failed']
print(f'\n{len(failures)} failures:')
for failure in failures:
    print(f"  {failure.get('test_id', 'Unknown')}: {failure.get('reason', 'No reason')}")
    print(f"    Expected: {failure.get('expected')}, Actual: {failure.get('actual')}")
