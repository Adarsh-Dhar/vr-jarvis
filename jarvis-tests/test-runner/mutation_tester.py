#!/usr/bin/env python3
"""
Mutation Testing Framework
Introduces mutations in tool implementations to verify tests catch them
"""

import sys
from pathlib import Path
from typing import Dict, List
import importlib.util
import ast

sys.path.insert(0, str(Path(__file__).parent))


class MutationTester:
    """Runs mutation tests to validate test quality"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.server_root = test_root.parent.parent / 'server'
        self.mutations_dir = test_root / 'test-reports' / 'mutations'
        self.mutations_dir.mkdir(parents=True, exist_ok=True)

    def get_tool_function(self, tool_name: str):
        """Get the actual tool function"""
        sys.path.insert(0, str(self.server_root))
        
        try:
            from ai_agents import tools
            tool_func = getattr(tools, tool_name, None)
            return tool_func
        except Exception as e:
            print(f"Error importing tool {tool_name}: {e}")
            return None

    def create_mutation(self, tool_name: str, mutation_type: str):
        """Create a mutated version of a tool"""
        original_func = self.get_tool_function(tool_name)
        if not original_func:
            return None

        # Get the source file
        module = importlib.import_module('ai_agents.tools')
        module_file = getattr(module, '__file__', None)
        
        if not module_file:
            return None

        tool_file = Path(module_file).parent / f"{tool_name.replace('_', '-')}.py"
        if not tool_file.exists():
            # Try other naming patterns
            for py_file in Path(module_file).parent.glob('*.py'):
                if tool_name in py_file.stem or py_file.stem.replace('-', '_') == tool_name:
                    tool_file = py_file
                    break

        if not tool_file.exists():
            return None

        # Read the source
        with open(tool_file, 'r') as f:
            source = f.read()

        # Create mutation based on type
        mutations = {
            'return_empty': self._mutate_return_empty,
            'return_none': self._mutate_return_none,
            'skip_filtering': self._mutate_skip_filtering,
            'wrong_field': self._mutate_wrong_field,
        }

        mutator = mutations.get(mutation_type)
        if not mutator:
            return None

        mutated_source = mutator(source, tool_name)
        
        if mutated_source == source:
            return None  # No mutation applied

        return {
            'tool_name': tool_name,
            'mutation_type': mutation_type,
            'original_source': source,
            'mutated_source': mutated_source,
            'tool_file': str(tool_file)
        }

    def _mutate_return_empty(self, source: str, tool_name: str) -> str:
        """Mutate to return empty list/dict instead of actual result"""
        # Find return statements and change them
        lines = source.split('\n')
        mutated_lines = []
        
        for line in lines:
            if 'return' in line and 'return ' in line:
                # Change return value to empty list
                if 'return {' in line:
                    mutated_lines.append('            return {}')
                elif 'return [' in line:
                    mutated_lines.append('            return []')
                else:
                    mutated_lines.append(line)
            else:
                mutated_lines.append(line)
        
        return '\n'.join(mutated_lines)

    def _mutate_return_none(self, source: str, tool_name: str) -> str:
        """Mutate to return None"""
        lines = source.split('\n')
        mutated_lines = []
        
        for line in lines:
            if 'return' in line and 'return ' in line and 'return None' not in line:
                mutated_lines.append('            return None')
            else:
                mutated_lines.append(line)
        
        return '\n'.join(mutated_lines)

    def _mutate_skip_filtering(self, source: str, tool_name: str) -> str:
        """Mutate to skip filtering logic"""
        # This is tool-specific, for now return unchanged
        return source

    def _mutate_wrong_field(self, source: str, tool_name: str) -> str:
        """Mutate to return wrong field values"""
        # Find number/string literals and change them
        lines = source.split('\n')
        mutated_lines = []
        
        for line in lines:
            if "'line':" in line:
                mutated_lines.append(line.replace("'line':", "'line': 999"))
            elif '"line":' in line:
                mutated_lines.append(line.replace('"line":', '"line": 999'))
            else:
                mutated_lines.append(line)
        
        return '\n'.join(mutated_lines)

    def run_mutation_test(self, tool_name: str, mutation_type: str) -> Dict:
        """Run a single mutation test"""
        mutation = self.create_mutation(tool_name, mutation_type)
        
        if not mutation:
            return {
                'tool_name': tool_name,
                'mutation_type': mutation_type,
                'status': 'skipped',
                'reason': 'Could not create mutation'
            }

        # Find test specs for this tool
        from test_registry import TestRegistry
        registry = TestRegistry(self.test_root)
        registry.load_test_definitions()
        
        test_ids = registry.get_tests_by_tool(tool_name)
        
        if not test_ids:
            return {
                'tool_name': tool_name,
                'mutation_type': mutation_type,
                'status': 'skipped',
                'reason': 'No tests found'
            }

        # For now, just report that we would run tests
        # In a full implementation, we would:
        # 1. Temporarily replace the tool function with mutated version
        # 2. Run the tests
        # 3. Check if tests fail (good) or pass (bad - test too weak)
        
        return {
            'tool_name': tool_name,
            'mutation_type': mutation_type,
            'status': 'pending',
            'test_count': len(test_ids),
            'message': 'Mutation created, test execution pending'
        }

    def calculate_mutation_score(self, results: List[Dict]) -> float:
        """Calculate mutation score"""
        if not results:
            return 0.0

        killed = sum(1 for r in results if r.get('status') == 'killed')
        total = len(results)
        
        return (killed / total) * 100 if total > 0 else 0.0


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Run mutation tests')
    parser.add_argument('--tool', type=str, help='Test specific tool')
    parser.add_argument('--mutation', type=str, help='Mutation type (return_empty, return_none, wrong_field)')
    parser.add_argument('--all', action='store_true', help='Run mutation tests on all tools')

    args = parser.parse_args()

    test_root = Path(__file__).parent.parent
    tester = MutationTester(test_root)

    if args.tool and args.mutation:
        result = tester.run_mutation_test(args.tool, args.mutation)
        print(f"Mutation test result: {result}")
    elif args.all:
        # Run on core tools
        core_tools = ['read_file', 'parse_source_code', 'extract_symbols', 'index_repository']
        mutation_types = ['return_empty', 'return_none']
        
        results = []
        for tool in core_tools:
            for mutation in mutation_types:
                result = tester.run_mutation_test(tool, mutation)
                results.append(result)
                print(f"{tool} / {mutation}: {result['status']}")
        
        score = tester.calculate_mutation_score(results)
        print(f"\nMutation Score: {score:.1f}%")
    else:
        print("Please specify --tool and --mutation, or --all")


if __name__ == '__main__':
    main()
