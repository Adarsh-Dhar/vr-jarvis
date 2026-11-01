#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
"""
Fix analyze_data_flow tests with missing file_path
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
        
        if not test_def or test_def.get('tool') != 'analyze_data_flow':
            return False
        
        input_data = test_def.get('input', {})
        
        # Check if file_path is missing
        if 'file_path' not in input_data or input_data.get('file_path') is None:
            # Use variable_name or tool_context as file_path
            if 'variable_name' in input_data:
                test_def['input']['file_path'] = input_data['variable_name']
                del test_def['input']['variable_name']
            elif 'tool_context' in input_data:
                test_def['input']['file_path'] = input_data['tool_context']
                del test_def['input']['tool_context']
            else:
                # Use fixture path
                fixture = test_def.get('fixture', 'simple-python')
                test_def['input']['file_path'] = f'fixtures/repositories/{fixture}/main.py'
            
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
