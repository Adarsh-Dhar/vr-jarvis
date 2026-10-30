#!/usr/bin/env python3
"""
Test All Tools
Quick validation script to test all JARVIS tools
"""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))
sys.path.insert(0, str(Path(__file__).parent))

from test_registry import TestRegistry
from test_orchestrator import TestOrchestrator


def test_all_tools():
    """Test all registered tools"""
    test_root = Path(__file__).parent.parent
    
    # Initialize registry
    registry = TestRegistry(test_root)
    registry.load_test_definitions()
    
    print("=" * 60)
    print("JARVIS Tool Testing")
    print("=" * 60)
    print(f"\nLoaded {len(registry.get_all_tests())} test definitions")
    
    # Get all tools
    all_tools = set()
    for test_def in registry.get_all_tests().values():
        tool = test_def.get('tool')
        if tool:
            all_tools.add(tool)
    
    print(f"Found {len(all_tools)} unique tools to test")
    print("\nTools to test:")
    for tool in sorted(all_tools):
        print(f"  - {tool}")
    
    # Initialize orchestrator
    orchestrator = TestOrchestrator(test_root, registry)
    
    # Run all tests
    print("\n" + "=" * 60)
    print("Running all tests...")
    print("=" * 60)
    
    run_result = orchestrator.run_test_suite(
        parallel=True
    )
    
    # Print results
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    summary = run_result['summary']
    print(f"Total Tests: {summary['total']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Errors: {summary['errors']}")
    print(f"Skipped: {summary['skipped']}")
    success_rate = run_result.get('success_rate', 0)
    print(f"Success Rate: {success_rate:.2%}")
    print(f"Duration: {run_result.get('duration', 0):.2f}s")
    
    if run_result.get('failed_tests'):
        print("\nFailed Tests:")
        for test_id in run_result['failed_tests']:
            print(f"  - {test_id}")
    
    if run_result.get('error_tests'):
        print("\nError Tests:")
        for test_id in run_result['error_tests']:
            print(f"  - {test_id}")
    
    # Generate report
    from report_generator import ReportGenerator
    report_gen = ReportGenerator(test_root)
    json_path = report_gen.generate_report(run_result)
    html_path = report_gen.generate_html_report(run_result)
    
    print(f"\nReports generated:")
    print(f"  JSON: {json_path}")
    print(f"  HTML: {html_path}")
    
    # Return exit code
    return 0 if summary['failed'] == 0 and summary['errors'] == 0 else 1


if __name__ == '__main__':
    sys.exit(test_all_tools())
