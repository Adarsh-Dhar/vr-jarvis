#!/usr/bin/env python3
"""
Quick fix: Replace placeholders with real values for tools we can execute
"""
from pathlib import Path
import yaml

# Real values from simple-python fixture
FIXTURE_VALUES = {
    'simple-python': {
        'file_path': 'fixtures/repositories/simple-python/main.py',
        'directory': 'fixtures/repositories/simple-python',
        'function_id': 'alpha',  # Function in main.py
        'pattern': '*.py',
        'search_term': 'def',
    }
}

def fix_placeholder_tests():
    test_root = Path('..')
    tests_path = test_root / 'tests' / 'real-input'

    fixed_count = 0
    for yaml_file in tests_path.rglob('*.yaml'):
        try:
            with open(yaml_file) as f:
                test_def = yaml.safe_load(f)

            if not test_def or not test_def.get('test_id'):
                continue

            tool = test_def.get('tool')
            fixture = test_def.get('fixture', 'simple-python')
            input_data = test_def.get('input', {})

            # Check if this test has placeholders
            has_placeholder = any(
                isinstance(v, str) and v.lower() == 'placeholder'
                for v in input_data.values()
            )

            if not has_placeholder:
                continue

            # Get fixture values
            fixture_data = FIXTURE_VALUES.get(fixture, FIXTURE_VALUES['simple-python'])

            # Replace placeholders
            modified = False
            for key, value in input_data.items():
                if isinstance(value, str) and value.lower() == 'placeholder':
                    if key in fixture_data:
                        input_data[key] = fixture_data[key]
                        modified = True
                    elif key == 'file_path':
                        input_data[key] = fixture_data['file_path']
                        modified = True
                    elif key == 'directory':
                        input_data[key] = fixture_data['directory']
                        modified = True
                    elif key == 'function_id':
                        input_data[key] = fixture_data['function_id']
                        modified = True
                    elif key == 'pattern':
                        input_data[key] = fixture_data['pattern']
                        modified = True
                    elif key == 'search_term':
                        input_data[key] = fixture_data['search_term']
                        modified = True

            if modified:
                # Write back
                with open(yaml_file, 'w') as f:
                    yaml.dump(test_def, f, default_flow_style=False)
                fixed_count += 1
                print(f"Fixed: {test_def['test_id']}")

        except Exception as e:
            print(f"Error processing {yaml_file}: {e}")

    print(f"\nTotal fixed: {fixed_count}")

if __name__ == '__main__':
    fix_placeholder_tests()
