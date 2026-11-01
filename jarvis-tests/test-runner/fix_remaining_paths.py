#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
"""
Fix tests with missing file_path or repository_path for all unmapped tools
"""
import sys
from pathlib import Path
import yaml

WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')
TESTS_ROOT = WORKSPACE / 'jarvis-tests/tests'

def fix_test_file(yaml_file):
    """Fix a single test file"""
    try:
        with open(yaml_file) as f:
            test_def = yaml.safe_load(f)
        
        if not test_def:
            return False
        
        input_data = test_def.get('input', {})
        fixed = False
        
        # Check if file_path is missing or None
        if 'file_path' not in input_data or input_data.get('file_path') is None:
            # Use fixture path
            fixture = test_def.get('fixture', 'simple-python')
            if fixture and fixture != 'None':
                test_def['input']['file_path'] = f'fixtures/repositories/{fixture}/main.py'
            else:
                test_def['input']['file_path'] = 'fixtures/repositories/simple-python/main.py'
            fixed = True
        
        # Check if repository_path is missing or None
        if 'repository_path' not in input_data or input_data.get('repository_path') is None:
            # Use fixture path
            fixture = test_def.get('fixture', 'simple-python')
            if fixture and fixture != 'None':
                test_def['input']['repository_path'] = f'fixtures/repositories/{fixture}'
            else:
                test_def['input']['repository_path'] = 'fixtures/repositories/simple-python'
            fixed = True
        
        if fixed:
            # Write back
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
