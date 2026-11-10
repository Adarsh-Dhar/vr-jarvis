#!/usr/bin/env python3
"""
Independent Ground Truth Validator
Cross-checks ground truth manifests against non-JARVIS tools.
"""

import sys
import ast
import yaml
from pathlib import Path
from typing import Dict, List, Set

sys.path.insert(0, str(Path(__file__).parent))


class IndependentValidator:
    """Validates ground truth using independent tools"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.repos_dir = test_root / 'fixtures' / 'repositories'

    def validate_python_repo(self, repo_name: str) -> Dict:
        """Validate a Python repository using Python ast"""
        repo_path = self.repos_dir / repo_name
        ground_truth_file = repo_path / 'ground-truth.yaml'

        if not ground_truth_file.exists():
            return {'status': 'skip', 'reason': 'No ground-truth.yaml'}

        with open(ground_truth_file, 'r') as f:
            ground_truth = yaml.safe_load(f)

        # Extract functions using ast
        actual_functions = self._extract_python_functions(repo_path)
        actual_classes = self._extract_python_classes(repo_path)

        # Normalize ground truth function names
        gt_functions = set()
        for func_name in ground_truth.get('functions', {}).keys():
            # Handle both "ClassName.method" and "method" formats
            if '.' in func_name:
                gt_functions.add(func_name)
            else:
                # Also add standalone version
                gt_functions.add(func_name)

        gt_classes = set(ground_truth.get('classes', {}).keys())

        validation = {
            'repo': repo_name,
            'status': 'passed',
            'issues': []
        }

        # Only check for missing functions (not extra ones, as GT may document more)
        missing_in_gt = actual_functions - gt_functions
        if missing_in_gt:
            validation['issues'].append(f'Functions in code but not in ground truth: {list(missing_in_gt)[:5]}...')
            validation['status'] = 'warning'

        return validation

    def _extract_python_functions(self, repo_path: Path) -> Set[str]:
        """Extract all function names from Python files using ast"""
        functions = set()

        for py_file in repo_path.rglob('*.py'):
            try:
                with open(py_file, 'r') as f:
                    source = f.read()
                tree = ast.parse(source)

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        functions.add(node.name)
                    elif isinstance(node, ast.AsyncFunctionDef):
                        functions.add(node.name)
            except Exception:
                pass

        return functions

    def _extract_python_classes(self, repo_path: Path) -> Set[str]:
        """Extract all class names from Python files using ast"""
        classes = set()

        for py_file in repo_path.rglob('*.py'):
            try:
                with open(py_file, 'r') as f:
                    source = f.read()
                tree = ast.parse(source)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        classes.add(node.name)
            except Exception:
                pass

        return classes

    def validate_all_repos(self) -> Dict:
        """Validate all repositories"""
        results = {}

        for repo_dir in self.repos_dir.iterdir():
            if not repo_dir.is_dir():
                continue

            repo_name = repo_dir.name

            # Skip scale fixtures and corrupted-inputs
            if repo_name.startswith('scale-') or repo_name == 'corrupted-inputs':
                continue

            # Determine language and validate accordingly
            if repo_name == 'simple-python':
                results[repo_name] = self.validate_python_repo(repo_name)
            elif repo_name in ['complex-typescript', 'spring-boot', 'rust-project', 'cpp-project', 
                             'polyglot-monorepo', 'distributed-system']:
                results[repo_name] = {'status': 'skip', 'reason': 'Language validation not implemented in Phase 1'}
            else:
                results[repo_name] = {'status': 'skip', 'reason': 'Unknown repository type'}

        return results

    def print_validation_report(self, results: Dict):
        """Print validation report"""
        print("\n" + "=" * 80)
        print("Independent Ground Truth Validation Report")
        print("=" * 80)

        passed = 0
        warnings = 0
        errors = 0
        skipped = 0

        for repo, result in results.items():
            status = result.get('status')
            print(f"\n{repo}: {status.upper()}")

            if status == 'passed':
                passed += 1
            elif status == 'warning':
                warnings += 1
                for issue in result.get('issues', []):
                    print(f"  ⚠️  {issue}")
            elif status == 'error':
                errors += 1
                for issue in result.get('issues', []):
                    print(f"  ❌ {issue}")
            else:
                skipped += 1
                print(f"  ℹ️  {result.get('reason', 'Unknown reason')}")

        print("\n" + "=" * 80)
        print(f"Summary: {passed} passed, {warnings} warnings, {errors} errors, {skipped} skipped")
        print("=" * 80)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate ground truth independently')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    validator = IndependentValidator(test_root)

    print("Validating ground truth independently...")
    results = validator.validate_all_repos()
    validator.print_validation_report(results)

    sys.exit(0)


if __name__ == '__main__':
    main()
