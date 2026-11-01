#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
"""
Fix placeholder inputs for tests that are being skipped
"""
import sys
from pathlib import Path
import yaml

WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')
TESTS_ROOT = WORKSPACE / 'jarvis-tests/tests'

def has_placeholder(value):
    """Check if a value is a placeholder"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.lower() in ['placeholder', 'none', 'null', 'example', 'test']
    return False

def fix_test_file(yaml_file):
    """Fix a single test file"""
    try:
        with open(yaml_file) as f:
            test_def = yaml.safe_load(f)
        
        if not test_def:
            return False
        
        input_data = test_def.get('input', {})
        fixture = test_def.get('fixture', 'simple-python')
        fixed = False
        
        # Fix common placeholder fields
        for field in ['file_path', 'repository_path', 'directory_path', 'symbol_name', 'function_id', 'class_name', 'module_name']:
            if field in input_data and has_placeholder(input_data[field]):
                if field in ['file_path']:
                    input_data[field] = f'fixtures/repositories/{fixture}/main.py'
                elif field in ['repository_path', 'directory_path']:
                    input_data[field] = f'fixtures/repositories/{fixture}'
                elif field in ['symbol_name', 'function_id']:
                    input_data[field] = 'alpha'
                elif field in ['class_name']:
                    input_data[field] = 'Calculator'
                elif field in ['module_name']:
                    input_data[field] = 'main'
                fixed = True
        
        if fixed:
            with open(yaml_file, 'w') as f:
                yaml.dump(test_def, f, default_flow_style=False)
            print(f"Fixed: {yaml_file.name}")
            return True
    
    except Exception as e:
        print(f"Error processing {yaml_file}: {e}")
        return False

def main():
    fixed_count = 0
    for yaml_file in TESTS_ROOT.rglob('*.yaml'):
        if fix_test_file(yaml_file):
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} test files")

if __name__ == '__main__':
    main()
