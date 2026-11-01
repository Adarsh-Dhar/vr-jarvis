#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
"""
Fix tests with missing repository_path
"""
import sys
from pathlib import Path
import yaml

WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')
TESTS_ROOT = WORKSPACE / 'jarvis-tests/tests'

# Tools that need repository_path
REPO_TOOLS = [
    'git_diff', 'git_log', 'git_status', 'git_branch', 'git_commit', 'git_show',
    'run_unit_tests', 'measure_test_coverage', 'measure_branch_coverage',
    'discover_tests', 'verify_compilation', 'run_build', 'run_linter',
    'run_formatter', 'run_type_checker'
]

def fix_test_file(yaml_file):
    """Fix a single test file"""
    try:
        with open(yaml_file) as f:
            test_def = yaml.safe_load(f)
        
        if not test_def or test_def.get('tool') not in REPO_TOOLS:
            return False
        
        input_data = test_def.get('input', {})
        
        # Check if repository_path is missing or None
        if 'repository_path' not in input_data or input_data.get('repository_path') is None:
            # Use fixture path
            fixture = test_def.get('fixture', 'simple-python')
            test_def['input']['repository_path'] = f'fixtures/repositories/{fixture}'
            
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
