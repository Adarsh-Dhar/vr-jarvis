#!/usr/bin/env python3
"""
Generate Real-Input Tests
Batch generates real-input tests for tools using fixture-based inputs
"""

import yaml
from pathlib import Path
import sys
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))


def get_tools_without_real_inputs(tests_dir: Path) -> List[str]:
    """Find tools that don't have real-input tests in core-tools directory"""
    core_tools_dir = tests_dir / 'core-tools'
    
    if not core_tools_dir.exists():
        return []
    
    tools_with_real_inputs = set()
    for yaml_file in core_tools_dir.glob('*.yaml'):
        try:
            with open(yaml_file, 'r') as f:
                spec = yaml.safe_load(f)
                tool = spec.get('tool')
                if tool:
                    tools_with_real_inputs.add(tool)
        except:
            pass
    
    return list(tools_with_real_inputs)


def generate_real_input_test(tool_name: str, generator, output_dir: Path):
    """Generate a real-input test for a tool"""
    try:
        # Get tool signature
        signature = generator.get_tool_signature(tool_name)
        if not signature:
            print(f"  Skipping {tool_name}: no signature found")
            return False
        
        # Generate spec with real_input_mode
        spec = generator.create_spec(tool_name, 'T01', signature, real_input_mode=True)
        
        # Determine output directory based on category
        category = generator._get_tool_category(tool_name)
        category_dir = output_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        
        # Write spec
        output_file = category_dir / f"{generator._category_prefix(tool_name)}-{tool_name}-T01.yaml"
        with open(output_file, 'w') as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False)
        
        return True
        
    except Exception as e:
        print(f"  Error generating test for {tool_name}: {e}")
        return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate real-input tests for tools')
    parser.add_argument('--tool', type=str, help='Generate test for specific tool')
    parser.add_argument('--category', type=str, help='Generate tests for a category')
    parser.add_argument('--all', action='store_true', help='Generate for all tools without real inputs')

    args = parser.parse_args()

    test_root = Path(__file__).parent.parent
    tests_dir = test_root / 'tests'
    output_dir = tests_dir / 'real-input'

    # Initialize generator
    from test_spec_generator import TestSpecGenerator
    generator = TestSpecGenerator(test_root)
    generator.load_all_tool_signatures()

    # Get tools that already have real inputs
    tools_with_real_inputs = get_tools_without_real_inputs(tests_dir)
    print(f"Tools with real inputs: {len(tools_with_real_inputs)}")

    if args.tool:
        # Generate for specific tool
        print(f"Generating real-input test for {args.tool}...")
        if generate_real_input_test(args.tool, generator, output_dir):
            print(f"  Success: {args.tool}")
        return

    if args.category:
        # Generate for category
        from test_spec_generator import TOOL_CATEGORIES
        category_tools = [tool for tool, cat in TOOL_CATEGORIES.items() if cat == args.category]
        print(f"Generating real-input tests for {args.category} ({len(category_tools)} tools)...")
        
        for tool_name in category_tools:
            if tool_name not in tools_with_real_inputs:
                generate_real_input_test(tool_name, generator, output_dir)
        return

    if args.all:
        # Generate for all tools without real inputs
        all_tools = list(generator.tools_signatures.keys())
        tools_without_real = [t for t in all_tools if t not in tools_with_real_inputs]
        
        print(f"Generating real-input tests for {len(tools_without_real)} tools...")
        
        success = 0
        failed = 0
        
        for tool_name in tools_without_real:
            if generate_real_input_test(tool_name, generator, output_dir):
                success += 1
                if success % 50 == 0:
                    print(f"  Generated {success} tests...")
            else:
                failed += 1
        
        print(f"\nComplete!")
        print(f"Generated: {success} tests")
        print(f"Failed: {failed} tests")
        return

    print("Please specify --tool, --category, or --all")


if __name__ == '__main__':
    main()
