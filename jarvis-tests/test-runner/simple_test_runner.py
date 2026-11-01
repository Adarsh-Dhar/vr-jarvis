#!/usr/bin/env python3
"""
Simple test runner that loads and executes tests directly
"""
from pathlib import Path
import yaml
import json
from datetime import datetime

def load_tests(test_path, limit=None):
    """Load tests from a path"""
    tests = []
    count = 0
    for yaml_file in Path(test_path).rglob('*.yaml'):
        try:
            with open(yaml_file) as f:
                test_def = yaml.safe_load(f)
            if test_def and test_def.get('test_id'):
                tests.append(test_def)
                count += 1
                if count % 500 == 0:
                    print(f"  Loaded {count} tests...")
                if limit and len(tests) >= limit:
                    break
        except Exception as e:
            print(f"Error loading {yaml_file}: {e}")
    return tests

def run_test(test_def):
    """Run a single test (placeholder - actual execution needs tool access)"""
    test_id = test_def.get('test_id')
    tool = test_def.get('tool')
    category = test_def.get('category')
    
    # Check if test has placeholder inputs
    input_data = test_def.get('input', {})
    has_placeholder = any(str(v).lower() == 'placeholder' for v in input_data.values())
    
    # Check if test only checks status
    expected = test_def.get('expected', {})
    status_only = 'status' in expected and len(expected) == 1
    
    return {
        'test_id': test_id,
        'tool': tool,
        'category': category,
        'has_placeholder': has_placeholder,
        'status_only': status_only,
        'status': 'skipped'  # Can't execute without tool access
    }

def main():
    test_root = Path('..')
    tests_path = test_root / 'tests'
    
    print(f"Loading tests from: {tests_path}")
    tests = load_tests(tests_path, limit=None)
    print(f"Loaded {len(tests)} tests")
    
    results = []
    for test in tests:
        result = run_test(test)
        results.append(result)
        print(f"  {result['test_id']}: placeholder={result['has_placeholder']}, status_only={result['status_only']}")
    
    # Summary
    placeholder_count = sum(1 for r in results if r['has_placeholder'])
    status_only_count = sum(1 for r in results if r['status_only'])
    
    print(f"\nSummary:")
    print(f"  Total: {len(results)}")
    print(f"  With placeholder inputs: {placeholder_count}")
    print(f"  Status-only checks: {status_only_count}")
    
    # Save results
    report_path = Path('jarvis-tests/test-reports/simple_run.json')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'summary': {
                'total': len(results),
                'placeholder_inputs': placeholder_count,
                'status_only': status_only_count
            }
        }, f, indent=2)
    print(f"Report saved to: {report_path}")

if __name__ == '__main__':
    main()
