#!/usr/bin/env python3
"""
Extract available data from all fixture repositories
"""
import ast
from pathlib import Path
from collections import defaultdict

def extract_python_data(fixture_path):
    """Extract functions, classes, files from Python fixture"""
    data = {
        'functions': [],
        'classes': [],
        'files': [],
        'root_path': str(fixture_path)
    }

    # Get all files
    for file_path in fixture_path.rglob('*'):
        if file_path.is_file():
            rel_path = file_path.relative_to(fixture_path)
            data['files'].append(str(rel_path))

            # Extract functions/classes from .py files
            if file_path.suffix == '.py':
                try:
                    with open(file_path) as f:
                        content = f.read()
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            data['functions'].append(node.name)
                        elif isinstance(node, ast.ClassDef):
                            data['classes'].append(node.name)
                except:
                    pass

    return data

def extract_fixture_data():
    fixtures_root = Path('../fixtures/repositories')
    fixtures = {}

    for fixture_dir in fixtures_root.iterdir():
        if fixture_dir.is_dir():
            fixture_name = fixture_dir.name
            if fixture_dir.name == 'simple-python':
                fixtures[fixture_name] = extract_python_data(fixture_dir)
            else:
                # For other fixtures, just get file list
                files = []
                for file_path in fixture_dir.rglob('*'):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(fixture_dir)
                        files.append(str(rel_path))
                fixtures[fixture_name] = {
                    'files': files,
                    'root_path': str(fixture_dir)
                }

    return fixtures

if __name__ == '__main__':
    fixtures = extract_fixture_data()

    print("Fixture Data:")
    print("=" * 60)
    for name, data in fixtures.items():
        print(f"\n{name}:")
        print(f"  Files: {len(data.get('files', []))}")
        if 'functions' in data:
            print(f"  Functions: {data['functions'][:10]}")
        if 'classes' in data:
            print(f"  Classes: {data['classes']}")
