#!/usr/bin/env python3
"""
Test a single tool with timeout
"""

import sys
import yaml
import signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))
sys.path.insert(0, str(Path(__file__).parent))

from test_orchestrator import TestOrchestrator

def timeout_handler(signum, frame):
    raise TimeoutError("Test timed out")

def test_single_tool(test_id):
    """Test a single tool"""
    test_root = Path(__file__).parent.parent
    orchestrator = TestOrchestrator(test_root, None)

    yaml_file = test_root / 'tests' / 'core-tools' / f'{test_id}.yaml'
    with open(yaml_file, 'r') as f:
        test_def = yaml.safe_load(f)

    print(f"Testing {test_id}...")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)  # 10 second timeout

    try:
        result = orchestrator._run_yaml_test(test_def)
        signal.alarm(0)  # Cancel alarm

        status = result.get('status')
        if status == 'passed':
            print(f"  ✓ PASSED")
        elif status == 'failed':
            print(f"  ✗ FAILED")
            failures = result.get('failures', [])
            for f in failures[:2]:
                print(f"    - {f}")
        else:
            print(f"  ✗ ERROR: {result.get('error')}")
    except TimeoutError:
        signal.alarm(0)
        print(f"  ✗ TIMEOUT")
    except Exception as e:
        signal.alarm(0)
        print(f"  ✗ EXCEPTION: {e}")

if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')

    # Test each tool individually
    tools = [
        'CORE-extract_ast-T01',
        'CORE-extract_symbols-T01',
        'CORE-git_branch-T01',
        'CORE-git_commit-T01',
        'CORE-index_repository-T01',
        'CORE-list_files-T01',
        'CORE-parse_source_code-T01',
        'CORE-read_file-T01',
        'CORE-read_file-T02',
        'CORE-read_file-T03',
        'CORE-read_file_range-T01',
        'CORE-scan_secrets-T01',
        'CORE-scan_vulnerabilities-T01',
        'CORE-search_symbols-T01',
    ]

    for tool in tools:
        test_single_tool(tool)
