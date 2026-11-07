#!/usr/bin/env python3
"""Regression gate script for Phase 1 DFG/CFG stabilization."""
import subprocess
import sys
import json
from pathlib import Path

def run_tests(test_path: str) -> tuple[int, int]:
    """Run tests and return (passed, total)."""
    result = subprocess.run(
        ["python3", "-m", "pytest", test_path, "-q", "-W", "ignore", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True
    )
    output = result.stdout + result.stderr
    
    # Parse output to get pass/fail counts
    passed = 0
    failed = 0
    for line in output.split('\n'):
        if 'passed' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'passed':
                    try:
                        passed = int(parts[i-1])
                    except:
                        pass
                if part == 'failed':
                    try:
                        failed = int(parts[i-1])
                    except:
                        pass
    
    total = passed + failed
    return passed, total

def main():
    """Run regression checks."""
    baseline_file = Path(__file__).parent.parent / "REGRESSION_BASELINE.json"
    
    if not baseline_file.exists():
        print(f"ERROR: Baseline file not found: {baseline_file}")
        sys.exit(1)
    
    with open(baseline_file) as f:
        baseline = json.load(f)
    
    print("=" * 60)
    print("REGRESSION GATE - Phase 1 DFG/CFG Stabilization")
    print("=" * 60)
    print(f"Baseline: {baseline['baseline_date']}")
    print(f"Commit: {baseline['baseline_commit']}")
    print()
    
    all_passed = True
    
    for suite_name, suite_info in baseline['test_suites'].items():
        print(f"Testing {suite_name}...")
        path = suite_info['path']
        expected_passing = suite_info['passing']
        expected_total = suite_info['total']
        
        passed, total = run_tests(path)
        
        print(f"  Expected: {expected_passing}/{expected_total}")
        print(f"  Actual:   {passed}/{total}")
        
        if passed == expected_passing and total == expected_total:
            print(f"  ✓ PASS")
        else:
            print(f"  ✗ FAIL - Regression detected!")
            all_passed = False
        print()
    
    print("=" * 60)
    if all_passed:
        print("REGRESSION GATE: ✓ PASSED")
        print("All test suites match baseline expectations.")
        sys.exit(0)
    else:
        print("REGRESSION GATE: ✗ FAILED")
        print("Test failures detected. Please review and fix before proceeding.")
        sys.exit(1)

if __name__ == "__main__":
    main()
