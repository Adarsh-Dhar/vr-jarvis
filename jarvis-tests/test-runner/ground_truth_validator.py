"""
Ground Truth Validator
Validates ground truth manifests for test repositories
"""

from pathlib import Path
from typing import Dict, List, Optional
import yaml
import sys


class ValidationResult:
    """Result of ground truth validation"""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passed: List[str] = []

    def add_error(self, message: str):
        self.errors.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    def add_pass(self, message: str):
        self.passed.append(message)

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [
            f"Validation Summary",
            f"  Passed: {len(self.passed)}",
            f"  Warnings: {len(self.warnings)}",
            f"  Errors: {len(self.errors)}",
        ]

        if self.warnings:
            lines.append("\nWarnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        if self.errors:
            lines.append("\nErrors:")
            for error in self.errors:
                lines.append(f"  - {error}")

        return "\n".join(lines)


class GroundTruthValidator:
    """Validates ground truth manifests"""

    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = fixtures_dir

    def validate(self, repository_name: str) -> ValidationResult:
        """Validate ground truth for a repository"""
        result = ValidationResult()

        ground_truth_path = self.fixtures_dir / 'repositories' / repository_name / 'ground-truth.yaml'

        if not ground_truth_path.exists():
            result.add_error(f"Ground truth file not found: {ground_truth_path}")
            return result

        # Load ground truth
        try:
            with open(ground_truth_path, 'r') as f:
                ground_truth = yaml.safe_load(f)
        except Exception as e:
            result.add_error(f"Failed to load ground truth: {e}")
            return result

        # Validate structure
        self._validate_structure(ground_truth, result)

        # Validate repository section
        self._validate_repository(ground_truth, result)

        # Validate functions
        self._validate_functions(ground_truth, result)

        # Validate classes
        self._validate_classes(ground_truth, result)

        # Validate call graph
        self._validate_call_graph(ground_truth, result)

        # Validate dependency graph
        self._validate_dependency_graph(ground_truth, result)

        return result

    def _validate_structure(self, ground_truth: Dict, result: ValidationResult):
        """Validate overall structure"""
        required_sections = ['repository', 'functions', 'call_graph', 'dependency_graph']

        for section in required_sections:
            if section not in ground_truth:
                result.add_error(f"Missing required section: {section}")
            else:
                result.add_pass(f"Section '{section}' present")

    def _validate_repository(self, ground_truth: Dict, result: ValidationResult):
        """Validate repository section"""
        repo = ground_truth.get('repository', {})

        required_fields = ['name', 'language', 'files']
        for field in required_fields:
            if field not in repo:
                result.add_error(f"Repository missing field: {field}")
            else:
                result.add_pass(f"Repository field '{field}' present")

        # Check files exist
        repo_name = repo.get('name')
        if repo_name:
            repo_path = self.fixtures_dir / 'repositories' / repo_name
            for file in repo.get('files', []):
                file_path = repo_path / file
                if not file_path.exists():
                    result.add_warning(f"File listed in ground truth but not found: {file}")
                else:
                    result.add_pass(f"File exists: {file}")

    def _validate_functions(self, ground_truth: Dict, result: ValidationResult):
        """Validate functions section"""
        functions = ground_truth.get('functions', {})

        if not functions:
            result.add_warning("No functions defined in ground truth")
            return

        required_fields = ['file', 'line', 'returns']

        for func_name, func_data in functions.items():
            for field in required_fields:
                if field not in func_data:
                    result.add_error(f"Function '{func_name}' missing field: {field}")

            # Check if callers reference existing functions
            for caller in func_data.get('callers', []):
                caller_name = caller.get('name')
                if caller_name and caller_name not in functions:
                    result.add_error(f"Function '{func_name}' references non-existent caller: {caller_name}")

            # Check if callees reference existing functions
            for callee in func_data.get('callees', []):
                callee_name = callee.get('name')
                if callee_name and callee_name not in functions:
                    result.add_error(f"Function '{func_name}' references non-existent callee: {callee_name}")

        result.add_pass(f"Validated {len(functions)} functions")

    def _validate_classes(self, ground_truth: Dict, result: ValidationResult):
        """Validate classes section"""
        classes = ground_truth.get('classes', {})

        if not classes:
            result.add_pass("No classes defined (optional)")
            return

        for class_name, class_data in classes.items():
            if 'file' not in class_data:
                result.add_error(f"Class '{class_name}' missing field: file")

            # Check base classes exist
            for base in class_data.get('base_classes', []):
                if base not in classes:
                    result.add_warning(f"Class '{class_name}' extends non-existent class: {base}")

        result.add_pass(f"Validated {len(classes)} classes")

    def _validate_call_graph(self, ground_truth: Dict, result: ValidationResult):
        """Validate call graph section"""
        call_graph = ground_truth.get('call_graph', {})
        edges = call_graph.get('edges', [])
        functions = ground_truth.get('functions', {})

        for edge in edges:
            from_node = edge.get('from')
            to_node = edge.get('to')

            if from_node and from_node not in functions:
                result.add_error(f"Call graph edge references non-existent 'from' function: {from_node}")

            if to_node and to_node not in functions:
                result.add_error(f"Call graph edge references non-existent 'to' function: {to_node}")

        result.add_pass(f"Validated {len(edges)} call graph edges")

    def _validate_dependency_graph(self, ground_truth: Dict, result: ValidationResult):
        """Validate dependency graph section"""
        dep_graph = ground_truth.get('dependency_graph', {})
        edges = dep_graph.get('edges', [])
        files = ground_truth.get('repository', {}).get('files', [])

        # Common external dependencies that are valid
        external_deps = {'os', 'json', 'sys', 'path', 're', 'time', 'datetime', 'typing', 'collections'}

        for edge in edges:
            from_node = edge.get('from')
            to_node = edge.get('to')

            if from_node and from_node not in files:
                # Check if it's an external dependency
                if from_node not in external_deps:
                    result.add_warning(f"Dependency graph edge references non-existent 'from' file: {from_node}")

            if to_node and to_node not in files:
                # Check if it's an external dependency
                if to_node not in external_deps:
                    result.add_warning(f"Dependency graph edge references non-existent 'to' file: {to_node}")

        result.add_pass(f"Validated {len(edges)} dependency graph edges")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate ground truth manifests')
    parser.add_argument('repository', type=str, help='Repository name to validate')
    parser.add_argument('--fixtures-dir', type=str, default='fixtures', help='Fixtures directory')

    args = parser.parse_args()

    test_root = Path(__file__).parent.parent
    fixtures_dir = test_root / args.fixtures_dir

    validator = GroundTruthValidator(fixtures_dir)
    result = validator.validate(args.repository)

    print(result.summary())

    return 0 if result.is_valid() else 1


if __name__ == '__main__':
    sys.exit(main())
