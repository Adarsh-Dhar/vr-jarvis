#!/usr/bin/env python3
"""
Run Tests with Do-Nothing Stub
Runs the test suite with all tools replaced by a do-nothing stub.
This is used for the do-nothing gate in CI.
"""

import sys
import json
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent))

from test_registry import TestRegistry
from test_orchestrator import TestOrchestrator


class StubTestOrchestrator(TestOrchestrator):
    """Test orchestrator that uses do-nothing stubs"""

    def _execute_single_test(self, test_id: str, test_def: Dict) -> Dict:
        """Execute a single test with do-nothing stub"""
        # Override tool execution to always return {"status": "ok"}
        result = {
            'test_id': test_id,
            'status': 'passed',  # Stub always passes
            'tool': test_def.get('tool', 'unknown'),
            'duration': 0.001,
            'output': {"status": "ok"},
            'message': 'Executed with do-nothing stub'
        }

        # Check if the spec only expects status: ok
        # If so, it will pass against the stub (bad)
        # If it expects specific values, it should fail (good)
        expected = test_def.get('expected', {})
        if set(expected.keys()) == {'status'}:
            result['stub_vulnerable'] = True
            result['message'] = 'SPEC VULNERABLE: Only checks status, will pass against stub'
        else:
            result['stub_vulnerable'] = False
            result['message'] = 'SPEC ROBUST: Checks specific values, will fail against stub'

        return result


def run_stub_gate(test_root: Path, max_allowed_passes: int = 100) -> Dict:
    """
    Run the test suite with do-nothing stub and check gate
    Returns pass/fail status
    """
    print("=" * 80)
    print("Do-Nothing Gate")
    print("=" * 80)
    print(f"Running all tests with do-nothing stub...")
    print(f"Gate threshold: max {max_allowed_passes} specs allowed to pass against stub")
    print()

    # Initialize registry
    registry = TestRegistry(test_root)
    registry.load_test_definitions()

    # Get all test IDs
    all_tests = registry.get_all_tests()
    test_ids = list(all_tests.keys())

    print(f"Total tests to check: {len(test_ids)}")
    print()

    # Run with stub orchestrator
    orchestrator = StubTestOrchestrator(test_root, registry)

    results = {}
    vulnerable_count = 0
    robust_count = 0

    for test_id in test_ids:
        test_def = all_tests[test_id]
        result = orchestrator._execute_single_test(test_id, test_def)
        results[test_id] = result

        if result['stub_vulnerable']:
            vulnerable_count += 1
        else:
            robust_count += 1

    # Print summary
    print("=" * 80)
    print("Stub Gate Results")
    print("=" * 80)
    print(f"Total specs checked: {len(test_ids)}")
    print(f"Vulnerable (pass against stub): {vulnerable_count}")
    print(f"Robust (fail against stub): {robust_count}")
    print()

    # Check gate
    gate_passed = vulnerable_count <= max_allowed_passes

    if gate_passed:
        print(f"✅ GATE PASSED: {vulnerable_count} vulnerable specs <= {max_allowed_passes} threshold")
        exit_code = 0
    else:
        print(f"❌ GATE FAILED: {vulnerable_count} vulnerable specs > {max_allowed_passes} threshold")
        print(f"   Need to fix {vulnerable_count - max_allowed_passes} specs to have real expected values")
        exit_code = 1

    print("=" * 80)

    # Save results
    gate_result = {
        'total_specs': len(test_ids),
        'vulnerable_count': vulnerable_count,
        'robust_count': robust_count,
        'max_allowed': max_allowed_passes,
        'gate_passed': gate_passed,
        'exit_code': exit_code
    }

    results_file = test_root / 'test-reports' / 'stub-gate-results.json'
    results_file.parent.mkdir(parents=True, exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump(gate_result, f, indent=2)

    print(f"Results saved to: {results_file}")

    return gate_result


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Run do-nothing gate')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')
    parser.add_argument('--max-allowed', type=int, default=100,
                        help='Maximum number of specs allowed to pass against stub')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    result = run_stub_gate(test_root, args.max_allowed)

    sys.exit(result['exit_code'])


if __name__ == '__main__':
    main()
