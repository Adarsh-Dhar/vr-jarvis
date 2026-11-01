#!/usr/bin/env python3
"""
Validate Test Spec Schema
Validates test specs against JSON Schema and additional Phase 0.5 constraints:
- No placeholder values in input
- Expected not containing only status (except T02/T08 reject cases)
- No absolute paths starting with /Users/
"""

import sys
import yaml
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Try to import jsonschema, provide fallback if not available
try:
    from jsonschema import validate, ValidationError, Draft7Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    print("Warning: jsonschema not installed. Install with: pip install jsonschema", file=sys.stderr)

sys.path.insert(0, str(Path(__file__).parent))


class SpecValidator:
    """Validates test specifications against schema and Phase 0.5 constraints"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.schema_file = Path(__file__).parent / 'spec_schema.json'
        with open(self.schema_file, 'r') as f:
            self.schema = json.load(f)
        if HAS_JSONSCHEMA:
            self.validator = Draft7Validator(self.schema)
        else:
            self.validator = None

    def validate_spec(self, spec: Dict, test_file: str) -> Tuple[bool, List[str]]:
        """
        Validate a single spec against schema and constraints.
        Returns (is_valid, list_of_errors)
        """
        errors = []

        # 1. JSON Schema validation (if jsonschema is available)
        if HAS_JSONSCHEMA and self.validator:
            try:
                self.validator.validate(spec)
            except ValidationError as e:
                errors.append(f"Schema validation error: {e.message}")
                return False, errors
        elif not HAS_JSONSCHEMA:
            # Skip schema validation if jsonschema not installed, but check required fields manually
            required_fields = ['test_id', 'name', 'tool', 'description']
            for field in required_fields:
                if field not in spec:
                    errors.append(f"Missing required field: {field}")

        # 2. Phase 0.5: No placeholder values in input
        input_data = spec.get('input', {})
        for key, value in input_data.items():
            if isinstance(value, str) and 'placeholder' in value.lower():
                errors.append(f"Input field '{key}' contains 'placeholder': {value}")

        # 3. Phase 0.5: Expected not containing only status (except T02/T08 reject cases)
        expected = spec.get('expected', {})
        test_type = spec.get('test_type', '')
        if set(expected.keys()) == {'status'}:
            # Allow only status for T02 (invalid input) and T08 (malformed input) reject cases
            if test_type not in ['T02', 'T08']:
                errors.append(f"Expected contains only 'status' field (not allowed except for T02/T08)")

        # 4. Phase 0.5: No absolute paths starting with /Users/
        for field in ['input', 'expected', 'fixture']:
            data = spec.get(field, {})
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, str) and value.startswith('/Users/'):
                        errors.append(f"Field '{field}.{key}' contains absolute path: {value}")

        # 5. Phase 0.3: If skip is true, must have skip_reason and linked_issue
        if spec.get('skip', False):
            if not spec.get('skip_reason'):
                errors.append("skip is true but skip_reason is missing")
            if not spec.get('linked_issue'):
                errors.append("skip is true but linked_issue is missing")

        return len(errors) == 0, errors

    def validate_all_specs(self) -> Tuple[int, int, List[Dict]]:
        """
        Validate all test specs.
        Returns (total_specs, valid_specs, list_of_invalid_specs)
        """
        tests_dir = self.test_root / 'tests'
        total = 0
        valid = 0
        invalid_specs = []

        for yaml_file in tests_dir.rglob('*.yaml'):
            total += 1
            try:
                with open(yaml_file, 'r') as f:
                    spec = yaml.safe_load(f)
                    if not spec:
                        continue

                    is_valid, errors = self.validate_spec(spec, str(yaml_file))

                    if is_valid:
                        valid += 1
                    else:
                        invalid_specs.append({
                            'file': str(yaml_file.relative_to(self.test_root)),
                            'test_id': spec.get('test_id', 'unknown'),
                            'errors': errors
                        })
            except Exception as e:
                invalid_specs.append({
                    'file': str(yaml_file.relative_to(self.test_root)),
                    'test_id': 'unknown',
                    'errors': [f"Failed to parse YAML: {e}"]
                })

        return total, valid, invalid_specs


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate test spec schema')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')
    parser.add_argument('--file', type=str,
                        help='Validate a single spec file')
    parser.add_argument('--fix', action='store_true',
                        help='Attempt to fix common issues (placeholder removal)')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    validator = SpecValidator(test_root)

    if args.file:
        # Validate single file
        with open(args.file, 'r') as f:
            spec = yaml.safe_load(f)

        is_valid, errors = validator.validate_spec(spec, args.file)

        if is_valid:
            print(f"✅ {args.file} is valid")
            sys.exit(0)
        else:
            print(f"❌ {args.file} has errors:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
    else:
        # Validate all specs
        print("Validating all test specs...")
        total, valid, invalid = validator.validate_all_specs(test_root)

        print(f"\nResults: {valid}/{total} specs valid ({valid/total*100:.1f}%)")

        if invalid:
            print(f"\n❌ Found {len(invalid)} invalid specs:")
            for inv in invalid[:20]:  # Show first 20
                print(f"\n  {inv['file']} ({inv['test_id']}):")
                for error in inv['errors']:
                    print(f"    - {error}")

            if len(invalid) > 20:
                print(f"\n  ... and {len(invalid) - 20} more")

            sys.exit(1)
        else:
            print("✅ All specs are valid")
            sys.exit(0)


if __name__ == '__main__':
    main()
