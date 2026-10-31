#!/usr/bin/env python3
"""
Generate Remaining Tests
Generates tests for all remaining untested tools to reach 100% coverage
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))


def get_all_tool_names():
    """Get all tool names from the tools package"""
    tools_dir = Path(__file__).parent.parent.parent / 'server' / 'ai_agents' / 'tools'
    init_file = tools_dir / '__init__.py'

    # Parse the __init__.py to extract tool names
    # Look for __all__ list
    with open(init_file, 'r') as f:
        content = f.read()

    # Simple extraction - look for __all__ assignment
    import ast
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '__all__':
                    if isinstance(node.value, ast.List):
                        tool_names = []
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant):
                                tool_names.append(elt.value)
                        return tool_names

    return []


def get_tested_tools():
    """Get set of tools that already have tests"""
    tested_tools = set()
    tests_dir = Path(__file__).parent.parent / 'tests'

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


def generate_tests_for_all_remaining():
    """Generate tests for all remaining untested tools"""
    from test_spec_generator import TestSpecGenerator

    test_root = Path(__file__).parent.parent
    generator = TestSpecGenerator(test_root)
    generator.load_all_tool_signatures()

    all_tools = get_all_tool_names()
    tested_tools = get_tested_tools()

    untested_tools = set(all_tools) - tested_tools

    print(f"Total tools: {len(all_tools)}")
    print(f"Tested tools: {len(tested_tools)}")
    print(f"Untested tools: {len(untested_tools)}")

    if not untested_tools:
        print("All tools already have tests!")
        return

    print(f"\nGenerating tests for {len(untested_tools)} untested tools...")

    test_types_layer1 = [f'T0{i}' for i in range(1, 10)]
    test_types_layer2 = [f'T1{i}' for i in range(0, 6)]

    results = {}
    total_generated = 0

    for tool_name in sorted(untested_tools):
        try:
            # Generate Layer 1 tests
            specs_l1 = generator.generate_for_tool(tool_name, test_types_layer1)
            saved_l1 = generator.save_specs(specs_l1, test_root / 'tests')

            # Generate Layer 2 tests
            specs_l2 = generator.generate_for_tool(tool_name, test_types_layer2)
            saved_l2 = generator.save_specs(specs_l2, test_root / 'tests')

            tool_total = len(saved_l1) + len(saved_l2)
            total_generated += tool_total

            results[tool_name] = {
                'layer1_count': len(saved_l1),
                'layer2_count': len(saved_l2),
                'total': tool_total,
                'status': 'success'
            }

            print(f"  {tool_name}: {tool_total} tests generated")

        except Exception as e:
            results[tool_name] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"  {tool_name}: ERROR - {e}")

    print(f"\nTotal tests generated: {total_generated}")

    # Save results
    results_file = test_root / 'test-runner' / 'generation_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {results_file}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate tests for remaining untested tools')
    parser.add_argument('--generate', action='store_true', help='Generate tests for all untested tools')

    args = parser.parse_args()

    if args.generate:
        generate_tests_for_all_remaining()
    else:
        # Just check
        all_tools = get_all_tool_names()
        tested_tools = get_tested_tools()
        untested_tools = set(all_tools) - tested_tools

        print(f"Total tools: {len(all_tools)}")
        print(f"Tested tools: {len(tested_tools)}")
        print(f"Untested tools: {len(untested_tools)}")

        if untested_tools:
            print(f"\nUntested tools:")
            for tool in sorted(untested_tools):
                print(f"  - {tool}")


if __name__ == '__main__':
    main()
