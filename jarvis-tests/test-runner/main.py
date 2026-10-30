#!/usr/bin/env python3
"""
JARVIS Test Runner - Main Entry Point
Central test orchestration system for the JARVIS platform
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))

from test_registry import TestRegistry
from test_orchestrator import TestOrchestrator
from test_fixture_manager import TestFixtureManager
from ground_truth_engine import GroundTruthEngine
from report_generator import ReportGenerator


def main():
    parser = argparse.ArgumentParser(description='JARVIS Test Runner')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')
    parser.add_argument('--category', type=str, action='append',
                        help='Test category to run (can specify multiple)')
    parser.add_argument('--tool', type=str, action='append',
                        help='Tool to test (can specify multiple)')
    parser.add_argument('--severity', type=str, choices=['critical', 'high', 'medium', 'low'],
                        help='Minimum severity level')
    parser.add_argument('--parallel', action='store_true', default=True,
                        help='Run tests in parallel')
    parser.add_argument('--layer', type=int, choices=[1, 2, 3, 4, 5, 6, 7],
                        help='Test layer to run (1=unit, 7=stress)')
    parser.add_argument('--list', action='store_true',
                        help='List all available tests')
    parser.add_argument('--report', type=str, default='json',
                        choices=['json', 'html', 'both'],
                        help='Report format')
    
    args = parser.parse_args()
    
    test_root = Path(args.test_root)
    
    # Initialize components
    registry = TestRegistry(test_root)
    registry.load_test_definitions()
    
    if args.list:
        print("Available Tests:")
        print("=" * 50)
        for test_id, test_def in registry.get_all_tests().items():
            print(f"\n{test_id}:")
            print(f"  Name: {test_def.get('name', 'N/A')}")
            print(f"  Category: {test_def.get('category', 'N/A')}")
            print(f"  Tool: {test_def.get('tool', 'N/A')}")
            print(f"  Severity: {test_def.get('severity', 'N/A')}")
        return
    
    # Select tests based on layer
    if args.layer:
        layer_categories = {
            1: ['unit'],
            2: ['unit'],
            3: ['integration'],
            4: ['agent-capabilities'],
            5: ['multi-agent'],
            6: ['end-to-end'],
            7: ['stress']
        }
        if not args.category:
            args.category = layer_categories.get(args.layer, [])
    
    # Initialize orchestrator
    orchestrator = TestOrchestrator(test_root, registry)
    
    # Run tests
    print(f"Running JARVIS tests...")
    print(f"Categories: {args.category or 'All'}")
    print(f"Tools: {args.tool or 'All'}")
    print(f"Severity: {args.severity or 'All'}")
    print(f"Parallel: {args.parallel}")
    print()
    
    run_result = orchestrator.run_test_suite(
        categories=args.category,
        tools=args.tool,
        severity=args.severity,
        parallel=args.parallel
    )
    
    # Generate report
    report_gen = ReportGenerator(test_root)
    
    if args.report in ['json', 'both']:
        json_path = report_gen.generate_report(run_result)
        print(f"\nJSON Report: {json_path}")
    
    if args.report in ['html', 'both']:
        html_path = report_gen.generate_html_report(run_result)
        print(f"HTML Report: {html_path}")
    
    # Print summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    summary = run_result['summary']
    print(f"Total: {summary['total']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Errors: {summary['errors']}")
    print(f"Skipped: {summary['skipped']}")
    print(f"Success Rate: {run_result['success_rate']:.2%}")
    print(f"Duration: {run_result['duration']:.2f}s")
    
    if run_result['failed_tests']:
        print("\nFailed Tests:")
        for test_id in run_result['failed_tests']:
            print(f"  - {test_id}")
    
    if run_result['error_tests']:
        print("\nError Tests:")
        for test_id in run_result['error_tests']:
            print(f"  - {test_id}")
    
    # Exit with appropriate code
    sys.exit(0 if summary['failed'] == 0 and summary['errors'] == 0 else 1)


if __name__ == '__main__':
    main()
