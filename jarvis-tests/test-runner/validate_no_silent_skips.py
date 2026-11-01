#!/usr/bin/env python3
"""
Validate No Silent Skips
CI check that rejects any spec with skip: true but no skip_reason and linked_issue.
"""

import sys
import yaml
from pathlib import Path


def validate_no_silent_skips(test_root: Path) -> tuple[bool, list]:
    """
    Validate that no spec has skip: true without skip_reason and linked_issue.
    Returns (is_valid, list_of_violations)
    """
    tests_dir = test_root / 'tests'
    violations = []

    for yaml_file in tests_dir.rglob('*.yaml'):
        try:
            with open(yaml_file, 'r') as f:
                spec = yaml.safe_load(f)
                if not spec:
                    continue

                if spec.get('skip', False):
                    skip_reason = spec.get('skip_reason', '')
                    linked_issue = spec.get('linked_issue', '')

                    if not skip_reason or not linked_issue:
                        violations.append({
                            'file': str(yaml_file.relative_to(test_root)),
                            'test_id': spec.get('test_id', 'unknown'),
                            'tool': spec.get('tool', 'unknown'),
                            'skip_reason': skip_reason,
                            'linked_issue': linked_issue
                        })
        except Exception as e:
            print(f"Error reading {yaml_file}: {e}", file=sys.stderr)

    is_valid = len(violations) == 0
    return is_valid, violations


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate no silent skips')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')

    args = parser.parse_args()

    test_root = Path(args.test_root)

    print("Validating no silent skips...")
    is_valid, violations = validate_no_silent_skips(test_root)

    if is_valid:
        print("✅ No silent skips found")
        sys.exit(0)
    else:
        print(f"❌ Found {len(violations)} specs with skip: true but missing skip_reason or linked_issue")
        print("\nViolations:")
        for v in violations[:20]:  # Show first 20
            print(f"  - {v['file']}: {v['test_id']} (tool: {v['tool']})")
            if not v['skip_reason']:
                print(f"    Missing: skip_reason")
            if not v['linked_issue']:
                print(f"    Missing: linked_issue")

        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more")

        print("\nEach skipped spec must have:")
        print("  1. skip_reason: explaining why it's skipped")
        print("  2. linked_issue: tracking the work to fix it")
        print("\nOr remove skip: true if the test should run.")
        sys.exit(1)


if __name__ == '__main__':
    main()
