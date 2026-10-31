#!/usr/bin/env python3
"""
Replace Placeholder Inputs
Batch updates YAML test specs to replace placeholder inputs with real fixture-based inputs
"""

import yaml
from pathlib import Path
import sys
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))


def find_placeholder_specs(tests_dir: Path) -> List[Path]:
    """Find all YAML specs containing placeholder values"""
    placeholder_specs = []

    for yaml_file in tests_dir.rglob('*.yaml'):
        try:
            with open(yaml_file, 'r') as f:
                content = f.read()
                if 'placeholder' in content:
                    placeholder_specs.append(yaml_file)
        except:
            pass

    return placeholder_specs


def update_spec_with_real_inputs(yaml_file: Path, generator) -> bool:
    """Update a single spec with real inputs"""
    try:
        with open(yaml_file, 'r') as f:
            spec = yaml.safe_load(f)

        tool_name = spec.get('tool')
        test_type = spec.get('test_type')

        if not tool_name or not test_type:
            return False

        # Get tool signature
        signature = generator.get_tool_signature(tool_name)

        # Generate new input with real_input_mode
        new_input = generator._generate_real_input(tool_name, test_type, signature)

        # Update the spec
        spec['input'] = new_input

        # Write back
        with open(yaml_file, 'w') as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False)

        return True

    except Exception as e:
        print(f"Error updating {yaml_file}: {e}")
        return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Replace placeholder inputs with real inputs')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--tool', type=str, help='Only update specs for a specific tool')

    args = parser.parse_args()

    test_root = Path(__file__).parent.parent
    tests_dir = test_root / 'tests'

    # Initialize generator
    from test_spec_generator import TestSpecGenerator
    generator = TestSpecGenerator(test_root)
    generator.load_all_tool_signatures()

    # Find specs with placeholders
    placeholder_specs = find_placeholder_specs(tests_dir)

    print(f"Found {len(placeholder_specs)} specs with placeholder values")

    if args.tool:
        # Filter by tool
        placeholder_specs = [f for f in placeholder_specs if args.tool in f.name]
        print(f"Filtered to {len(placeholder_specs)} specs for tool {args.tool}")

    if args.dry_run:
        print("\nDry run - would update the following files:")
        for spec_file in placeholder_specs[:10]:  # Show first 10
            print(f"  - {spec_file}")
        if len(placeholder_specs) > 10:
            print(f"  ... and {len(placeholder_specs) - 10} more")
        return

    # Update specs
    updated = 0
    failed = 0

    for spec_file in placeholder_specs:
        if update_spec_with_real_inputs(spec_file, generator):
            updated += 1
            if updated % 100 == 0:
                print(f"Updated {updated} specs...")
        else:
            failed += 1

    print(f"\nComplete!")
    print(f"Updated: {updated} specs")
    print(f"Failed: {failed} specs")


if __name__ == '__main__':
    main()
