#!/usr/bin/env python3
"""
Verify placeholder replacement worked
"""
from pathlib import Path
import yaml

def verify_placeholders():
    test_root = Path('..')
    tests_path = test_root / 'tests'

    placeholder_count = 0
    total_files = 0

    for yaml_file in tests_path.rglob('*.yaml'):
        total_files += 1
        try:
            with open(yaml_file) as f:
                test_def = yaml.safe_load(f)
            if not test_def or not test_def.get('test_id'):
                continue

            input_data = test_def.get('input', {})
            for key, value in input_data.items():
                if isinstance(value, str) and value.lower() == 'placeholder':
                    placeholder_count += 1
                    print(f"Still has placeholder: {test_def['test_id']}.{key}")
        except Exception as e:
            pass

    print(f"\nTotal files: {total_files}")
    print(f"Placeholders remaining: {placeholder_count}")

if __name__ == '__main__':
    verify_placeholders()
