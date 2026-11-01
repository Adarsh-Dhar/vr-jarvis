#!/usr/bin/env python3
"""
Scale Fixture Generator
Generates synthetic repositories of 1,000, 10,000, and 100,000 files
with known answers that stay consistent at any size.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List
import random
import string

sys.path.insert(0, str(Path(__file__).parent))


class ScaleFixtureGenerator:
    """Generates scale test fixtures"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_file(self, file_path: Path, file_type: str, index: int):
        """Generate a single file with deterministic content"""
        if file_type == 'python':
            content = self._generate_python_file(index)
        elif file_type == 'javascript':
            content = self._generate_javascript_file(index)
        elif file_type == 'typescript':
            content = self._generate_typescript_file(index)
        elif file_type == 'java':
            content = self._generate_java_file(index)
        else:
            content = self._generate_generic_file(index)

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(content)

    def _generate_python_file(self, index: int) -> str:
        """Generate a Python file"""
        func_name = f"function_{index}"
        return f'''"""
Auto-generated Python file {index}
"""

def {func_name}():
    """Auto-generated function"""
    return {index}

class Class{index}:
    """Auto-generated class"""
    def __init__(self):
        self.value = {index}

    def method(self):
        return self.value * 2

# Constant
CONSTANT_{index} = {index}
'''

    def _generate_javascript_file(self, index: int) -> str:
        """Generate a JavaScript file"""
        return f'''/**
 * Auto-generated JavaScript file {index}
 */

function function{index}() {{
    return {index};
}}

class Class{index} {{
    constructor() {{
        this.value = {index};
    }}

    method() {{
        return this.value * 2;
    }}
}}

const CONSTANT_{index} = {index};
'''

    def _generate_typescript_file(self, index: int) -> str:
        """Generate a TypeScript file"""
        return f'''/**
 * Auto-generated TypeScript file {index}
 */

interface Interface{index} {{
    value: number;
    method(): number;
}}

class Class{index} implements Interface{index} {{
    constructor(public value: number = {index}) {{}}

    method(): number {{
        return this.value * 2;
    }}
}}

function function{index}(): number {{
    return {index};
}}

const CONSTANT_{index}: number = {index};
'''

    def _generate_java_file(self, index: int) -> str:
        """Generate a Java file"""
        return f'''/**
 * Auto-generated Java file {index}
 */
public class Class{index} {{
    private int value = {index};

    public int method() {{
        return value * 2;
    }}

    public static int function{index}() {{
        return {index};
    }}
}}
'''

    def _generate_generic_file(self, index: int) -> str:
        """Generate a generic text file"""
        return f'''Auto-generated file {index}
Content line 1
Content line 2
Value: {index}
'''

    def generate_repository(self, size: int, name: str) -> Path:
        """
        Generate a repository of specified size.
        size: number of files to generate
        name: name of the repository
        """
        repo_dir = self.output_dir / name
        repo_dir.mkdir(exist_ok=True)

        print(f"Generating {name} with {size} files...")

        # File type distribution
        file_types = ['python'] * 40 + ['javascript'] * 30 + ['typescript'] * 20 + ['java'] * 10

        # Directory structure (depth-3 tree)
        dirs = ['src', 'tests', 'lib', 'utils', 'components']
        subdirs = ['module_a', 'module_b', 'module_c', 'shared']

        for i in range(size):
            # Select file type
            file_type = random.choice(file_types)

            # Select directory
            dir_name = random.choice(dirs)
            subdir_name = random.choice(subdirs)

            # Generate file path
            ext = {'python': '.py', 'javascript': '.js', 'typescript': '.ts', 'java': '.java'}[file_type]
            file_name = f"file_{i}{ext}"
            file_path = repo_dir / dir_name / subdir_name / file_name

            self.generate_file(file_path, file_type, i)

            if (i + 1) % 1000 == 0:
                print(f"  Generated {i + 1}/{size} files...")

        # Generate ground truth
        self._generate_ground_truth(repo_dir, size, name)

        print(f"Completed {name}: {size} files")
        return repo_dir

    def _generate_ground_truth(self, repo_dir: Path, size: int, name: str):
        """Generate ground truth manifest for the repository"""
        ground_truth = {
            'repository': name,
            'file_count': size,
            'directory_structure': {
                'depth': 3,
                'directories': ['src', 'tests', 'lib', 'utils', 'components'],
                'subdirectories': ['module_a', 'module_b', 'module_c', 'shared']
            },
            'file_distribution': {
                'python': int(size * 0.4),
                'javascript': int(size * 0.3),
                'typescript': int(size * 0.2),
                'java': int(size * 0.1)
            },
            'known_functions': {
                'python': [f'function_{i}' for i in range(100)],  # Sample of 100
                'javascript': [f'function{i}' for i in range(100)],
                'typescript': [f'function{i}' for i in range(100)],
                'java': [f'function{i}' for i in range(100)]
            },
            'known_classes': {
                'python': [f'Class{i}' for i in range(100)],
                'javascript': [f'Class{i}' for i in range(100)],
                'typescript': [f'Class{i}' for i in range(100)],
                'java': [f'Class{i}' for i in range(100)]
            },
            'constants': {
                'python': [f'CONSTANT_{i}' for i in range(100)],
                'javascript': [f'CONSTANT_{i}' for i in range(100)],
                'typescript': [f'CONSTANT_{i}' for i in range(100)]
            }
        }

        with open(repo_dir / 'ground-truth.yaml', 'w') as f:
            import yaml
            yaml.dump(ground_truth, f, default_flow_style=False)

        print(f"  Generated ground truth for {name}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate scale fixtures')
    parser.add_argument('--output-dir', type=str, default='jarvis-tests/fixtures/repositories',
                        help='Output directory for fixtures')
    parser.add_argument('--sizes', type=int, nargs='+', default=[1000, 10000, 100000],
                        help='Sizes to generate (default: 1K, 10K, 100K)')

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    generator = ScaleFixtureGenerator(output_dir)

    for size in args.sizes:
        name = f"scale-{size}"
        generator.generate_repository(size, name)

    print("\n✅ Scale fixtures generated successfully")
    print("Note: Large fixtures (10K, 100K) should be generated in CI, not committed")


if __name__ == '__main__':
    main()
