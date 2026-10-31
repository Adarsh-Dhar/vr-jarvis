#!/usr/bin/env python3
"""
Simple spec conversion without registry
"""

import sys
import yaml
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))

from ai_agents import tools


def convert_single_spec():
    """Convert a single YAML spec"""
    # Load the YAML file
    yaml_file = Path(__file__).parent.parent / 'tests' / 'core-tools' / 'CORE-read_file-T01.yaml'
    with open(yaml_file, 'r') as f:
        test_def = yaml.safe_load(f)

    print(f"Original spec:")
    print(yaml.dump(test_def, default_flow_style=False, sort_keys=False))

    tool_name = test_def.get('tool')
    print(f"\nTool: {tool_name}")

    # Get tool signature
    tool_func = getattr(tools, tool_name, None)
    if tool_func:
        sig = inspect.signature(tool_func)
        print(f"Signature: {sig}")

    # The current spec already has good expected values
    # Let's just verify it passes with the updated runner
    print("\n=== Verifying with updated runner ===")

    # Import orchestrator
    sys.path.insert(0, str(Path(__file__).parent))
    from test_orchestrator import TestOrchestrator

    test_root = Path(__file__).parent.parent
    orchestrator = TestOrchestrator(test_root, None)

    result = orchestrator._run_yaml_test(test_def)
    print(f"Result status: {result.get('status')}")

    if result.get('status') == 'passed':
        print("SUCCESS: Spec is already good!")
    elif result.get('status') == 'failed':
        print(f"Failures: {result.get('failures')}")
    else:
        print(f"Error: {result.get('error')}")

if __name__ == '__main__':
    convert_single_spec()
