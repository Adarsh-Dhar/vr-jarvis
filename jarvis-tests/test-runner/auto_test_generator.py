#!/usr/bin/env python3
"""
Auto Test Generator
Automatically generates tests for new or modified tools
"""

import sys
from pathlib import Path
import ast
import inspect
from typing import Dict, List
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))


class AutoTestGenerator:
    """Automatically generates tests for new or modified tools"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.tools_dir = test_root.parent.parent / 'server' / 'ai_agents' / 'tools'

    def scan_for_new_tools(self) -> List[str]:
        """Scan for tools that don't have tests yet"""
        # Get all tool names from __init__.py
        init_file = self.tools_dir / '__init__.py'
        with open(init_file, 'r') as f:
            content = f.read()

        # Extract tool names using AST
        tree = ast.parse(content)
        all_tools = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    all_tools.add(alias.name)

        # Get tools that already have tests
        tested_tools = self._get_tested_tools()

        # Find untested tools
        new_tools = all_tools - tested_tools
        return sorted(new_tools)

    def _get_tested_tools(self) -> set:
        """Get set of tools that already have tests"""
        tested_tools = set()
        tests_dir = self.test_root / 'tests'

        for yaml_file in tests_dir.rglob('*.yaml'):
            try:
                import yaml
                with open(yaml_file, 'r') as f:
                    test_def = yaml.safe_load(f)
                    tool = test_def.get('tool')
                    if tool:
                        tested_tools.add(tool)
            except:
                pass

        return tested_tools

    def generate_tests_for_new_tools(self, new_tools: List[str]) -> Dict:
        """Generate tests for new tools"""
        from test_spec_generator import TestSpecGenerator

        generator = TestSpecGenerator(self.test_root)
        generator.load_all_tool_signatures()

        results = {}
        test_types_layer1 = [f'T0{i}' for i in range(1, 10)]
        test_types_layer2 = [f'T1{i}' for i in range(0, 6)]

        for tool_name in new_tools:
            try:
                # Generate Layer 1 tests
                specs_l1 = generator.generate_for_tool(tool_name, test_types_layer1)
                saved_l1 = generator.save_specs(specs_l1, self.test_root / 'tests')

                # Generate Layer 2 tests
                specs_l2 = generator.generate_for_tool(tool_name, test_types_layer2)
                saved_l2 = generator.save_specs(specs_l2, self.test_root / 'tests')

                results[tool_name] = {
                    'layer1_count': len(saved_l1),
                    'layer2_count': len(saved_l2),
                    'total': len(saved_l1) + len(saved_l2),
                    'status': 'success'
                }
            except Exception as e:
                results[tool_name] = {
                    'status': 'error',
                    'error': str(e)
                }

        return results

    def check_for_modified_tools(self) -> List[str]:
        """Check for tools modified since last test generation"""
        # This would integrate with git to check file modifications
        # For now, return empty list
        return []


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Auto-generate tests for new tools')
    parser.add_argument('--check', action='store_true', help='Check for new tools')
    parser.add_argument('--generate', action='store_true', help='Generate tests for new tools')

    args = parser.parse_args()

    test_root = Path(__file__).parent.parent
    generator = AutoTestGenerator(test_root)

    if args.check:
        new_tools = generator.scan_for_new_tools()
        print(f"Found {len(new_tools)} new tools without tests:")
        for tool in new_tools:
            print(f"  - {tool}")

    if args.generate:
        new_tools = generator.scan_for_new_tools()
        if new_tools:
            print(f"Generating tests for {len(new_tools)} new tools...")
            results = generator.generate_tests_for_new_tools(new_tools)

            print("\nResults:")
            for tool, result in results.items():
                if result['status'] == 'success':
                    print(f"  {tool}: {result['total']} tests generated")
                else:
                    print(f"  {tool}: ERROR - {result['error']}")
        else:
            print("No new tools found. All tools have tests.")


if __name__ == '__main__':
    main()
