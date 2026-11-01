#!/usr/bin/env python3
"""
Analyze placeholder patterns across all tests
"""
from pathlib import Path
import yaml
from collections import defaultdict

def analyze_placeholders():
    test_root = Path('..')
    tests_path = test_root / 'tests'

    patterns = defaultdict(int)
    tool_placeholders = defaultdict(list)
    examples = []
    count = 0
    limit = 2000  # Sample first 2000 tests

    for yaml_file in tests_path.rglob('*.yaml'):
        try:
            with open(yaml_file) as f:
                test_def = yaml.safe_load(f)
            if not test_def or not test_def.get('test_id'):
                continue

            tool = test_def.get('tool', 'unknown')
            input_data = test_def.get('input', {})

            for key, value in input_data.items():
                if isinstance(value, str) and value.lower() == 'placeholder':
                    patterns[f"{tool}.{key}"] += 1
                    tool_placeholders[tool].append({
                        'test_id': test_def['test_id'],
                        'field': key,
                        'file': str(yaml_file)
                    })
                    if len(examples) < 50:
                        examples.append({
                            'tool': tool,
                            'field': key,
                            'test_id': test_def['test_id']
                        })
            count += 1
            if count >= limit:
                break
        except Exception as e:
            pass

    print("Placeholder Patterns by Tool.Field:")
    print("=" * 60)
    for pattern, count in sorted(patterns.items(), key=lambda x: -x[1])[:20]:
        print(f"  {pattern}: {count}")

    print(f"\nTotal unique patterns: {len(patterns)}")

    print("\nTools with most placeholders:")
    print("=" * 60)
    for tool, items in sorted(tool_placeholders.items(), key=lambda x: -len(x[1]))[:15]:
        print(f"  {tool}: {len(items)}")

    print(f"\nExamples (first 50):")
    print("=" * 60)
    for ex in examples:
        print(f"  {ex['tool']}.{ex['field']}: {ex['test_id']}")

    return patterns, tool_placeholders

if __name__ == '__main__':
    analyze_placeholders()
