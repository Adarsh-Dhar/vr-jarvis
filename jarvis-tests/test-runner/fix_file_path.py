#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
"""
Fix tests with missing file_path for all tools
"""
import sys
from pathlib import Path
import yaml

WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')
TESTS_ROOT = WORKSPACE / 'jarvis-tests/tests'

# Tools that need file_path
FILE_TOOLS = [
    'read_file', 'list_files', 'search_files', 'search_code', 'read_file_range',
    'parse_source_code', 'parse_function', 'extract_function_signature', 'get_symbol_definition',
    'build_call_graph', 'analyze_annotations', 'analyze_code_complexity', 'analyze_data_flow',
    'analyze_dependencies', 'analyze_exceptions', 'analyze_generated_code', 'analyze_macros',
    'create_file', 'edit_file', 'delete_file', 'move_file', 'rename_file', 'create_directory'
]

def fix_test_file(yaml_file):
    """Fix a single test file"""
    try:
        with open(yaml_file) as f:
            test_def = yaml.safe_load(f)
        
        if not test_def or test_def.get('tool') not in FILE_TOOLS:
            return False
        
        input_data = test_def.get('input', {})
        
        # Check if file_path is missing or None
        if 'file_path' not in input_data or input_data.get('file_path') is None:
            # Use fixture path
            fixture = test_def.get('fixture', 'simple-python')
            if fixture and fixture != 'None':
                test_def['input']['file_path'] = f'fixtures/repositories/{fixture}/main.py'
            else:
                test_def['input']['file_path'] = 'fixtures/repositories/simple-python/main.py'
            
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
