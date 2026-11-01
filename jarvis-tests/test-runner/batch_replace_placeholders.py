#!/usr/bin/env python3
"""
Batch replace placeholders in all test files with real fixture values
"""
from pathlib import Path
import yaml
import sys
sys.path.insert(0, str(Path(__file__).parent))
from tool_field_mapping import get_tool_mapping, get_fixture_value

def replace_placeholders_in_file(yaml_file):
    """Replace placeholders in a single test file"""
    try:
        with open(yaml_file) as f:
            test_def = yaml.safe_load(f)

        if not test_def or not test_def.get('test_id'):
            return False, False

        tool = test_def.get('tool')
        fixture = test_def.get('fixture', 'simple-python')
        input_data = test_def.get('input', {})

        # Check if this test has placeholders
        has_placeholder = any(
            isinstance(v, str) and v.lower() == 'placeholder'
            for v in input_data.values()
        )

        if not has_placeholder:
            return False, False

        # Get tool mapping
        mapping = get_tool_mapping(tool)

        # Replace placeholders
        modified = False
        for key, value in input_data.items():
            if isinstance(value, str) and value.lower() == 'placeholder':
                # Get appropriate value based on field type
                new_value = get_fixture_value(fixture, key)

                # Use extra values if defined
                if 'extra_values' in mapping and key in mapping['extra_values']:
                    new_value = mapping['extra_values'][key]

                input_data[key] = new_value
                modified = True

        if modified:
            # Write back
            with open(yaml_file, 'w') as f:
                yaml.dump(test_def, f, default_flow_style=False, sort_keys=False)
            return True, True

        return True, False

    except Exception as e:
        print(f"Error processing {yaml_file}: {e}")
        return False, False

def batch_replace_placeholders():
    """Replace placeholders in all test files"""
    test_root = Path('..')
    tests_path = test_root / 'tests'

    total_files = 0
    processed_files = 0
    modified_files = 0

    print("Scanning test files...")
    for yaml_file in tests_path.rglob('*.yaml'):
        total_files += 1
        processed, modified = replace_placeholders_in_file(yaml_file)
        if processed:
            processed_files += 1
        if modified:
            modified_files += 1
            print(f"Modified: {yaml_file.name}")

        if total_files % 500 == 0:
            print(f"Processed {total_files} files...")

    print(f"\nSummary:")
    print(f"  Total files: {total_files}")
    print(f"  Processed: {processed_files}")
    print(f"  Modified: {modified_files}")

if __name__ == '__main__':
    batch_replace_placeholders()
