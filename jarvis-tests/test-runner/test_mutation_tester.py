#!/usr/bin/env python3
"""
Test Mutation Tester
Mutates test expectations to validate test quality (mutates tests, not implementations)
"""

import yaml
from pathlib import Path
from typing import Dict, List
import sys

sys.path.insert(0, str(Path(__file__).parent))


class TestMutationTester:
    """Mutates test expectations to check if tests are too weak"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.tests_dir = test_root / 'tests'

    def mutate_test_file(self, yaml_file: Path, mutation_type: str) -> Dict:
        """Mutate a test file and return the mutation"""
        try:
            with open(yaml_file, 'r') as f:
                original_spec = yaml.safe_load(f)

            mutated_spec = original_spec.copy()

            # Apply mutation based on type
            if mutation_type == 'remove_status':
                if 'expected' in mutated_spec and 'status' in mutated_spec['expected']:
                    del mutated_spec['expected']['status']
            
            elif mutation_type == 'wrong_status':
                if 'expected' in mutated_spec and 'status' in mutated_spec['expected']:
                    mutated_spec['expected']['status'] = 'error' if mutated_spec['expected']['status'] == 'ok' else 'ok'
            
            elif mutation_type == 'remove_required_content':
                if 'checks' in mutated_spec:
                    for check in mutated_spec['checks']:
                        if 'required_content' in check:
                            check['required_content'] = []
            
            elif mutation_type == 'flip_checks':
                if 'checks' in mutated_spec:
                    # Remove all checks
                    mutated_spec['checks'] = []
            
            elif mutation_type == 'change_fixture':
                if 'fixture' in mutated_spec:
                    # Change to non-existent fixture
                    mutated_spec['fixture'] = 'nonexistent-fixture'

            if mutated_spec == original_spec:
                return {
                    'file': str(yaml_file),
                    'mutation_type': mutation_type,
                    'status': 'skipped',
                    'reason': 'No mutation applied'
                }

            return {
                'file': str(yaml_file),
                'mutation_type': mutation_type,
                'status': 'mutated',
                'original': original_spec,
                'mutated': mutated_spec
            }

        except Exception as e:
            return {
                'file': str(yaml_file),
                'mutation_type': mutation_type,
                'status': 'error',
                'error': str(e)
            }

    def run_mutation_scan(self, directory: Path) -> List[Dict]:
        """Scan directory and apply mutations to tests"""
        mutation_types = ['remove_status', 'wrong_status', 'remove_required_content', 'flip_checks']
        results = []

        for yaml_file in directory.rglob('*.yaml'):
            for mutation_type in mutation_types:
                result = self.mutate_test_file(yaml_file, mutation_type)
                results.append(result)

        return results

    def generate_mutation_report(self, results: List[Dict]) -> str:
        """Generate a mutation testing report"""
        mutated = sum(1 for r in results if r['status'] == 'mutated')
        skipped = sum(1 for r in results if r['status'] == 'skipped')
        errors = sum(1 for r in results if r['status'] == 'error')

        lines = [
            "Test Mutation Report",
            "=" * 50,
            f"Total mutations attempted: {len(results)}",
            f"Mutations applied: {mutated}",
            f"Skipped: {skipped}",
            f"Errors: {errors}",
            "",
            "Mutation Types:",
            "- remove_status: Remove status from expected output",
            "- wrong_status: Flip ok/error in expected status",
            "- remove_required_content: Remove required content checks",
            "- flip_checks: Remove all checks",
            "- change_fixture: Change to non-existent fixture",
            "",
            "Note: Full mutation testing requires running tests against mutated specs",
            "      to verify they fail. This scan only identifies potential mutations."
        ]

        return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Run test mutation testing')
    parser.add_argument('--directory', type=str, help='Directory to scan')
    parser.add_argument('--core-tools', action='store_true', help='Test core-tools directory')

    args = parser.parse_args()

    test_root = Path(__file__).parent.parent
    tester = TestMutationTester(test_root)

    if args.core_tools:
        directory = test_root / 'tests' / 'core-tools'
    elif args.directory:
        directory = Path(args.directory)
    else:
        directory = test_root / 'tests' / 'real-input'

    print(f"Scanning {directory} for mutations...")
    results = tester.run_mutation_scan(directory)
    
    report = tester.generate_mutation_report(results)
    print(report)

    # Save detailed results
    mutations_dir = test_root / 'test-reports' / 'mutations'
    mutations_dir.mkdir(parents=True, exist_ok=True)
    
    report_file = mutations_dir / 'mutation_scan_report.txt'
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\nDetailed report saved to: {report_file}")


if __name__ == '__main__':
    main()
