#!/usr/bin/env python3
"""
Check actual tool outputs to fix specs
"""

import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))

from ai_agents.tools import repository_tools, analysis_tools, security_quality_tools, repository_intelligence_tools, software_engineering_tools, graph_tools
from google.adk.tools import ToolContext

class MockToolContext:
    def __init__(self):
        self.state = {}

def check_tool_output(tool_name, tool_func, input_args):
    """Check what a tool actually returns"""
    tool_context = MockToolContext()

    # Make paths absolute
    test_root = Path(__file__).parent.parent
    input_copy = input_args.copy()
    for key, value in input_copy.items():
        if isinstance(value, str) and 'fixtures/repositories' in value:
            input_copy[key] = str(test_root / value)

    print(f"\n=== {tool_name} ===")
    print(f"Input: {input_copy}")

    try:
        output = tool_func(**input_copy, tool_context=tool_context)
        print(f"Status: {output.get('status')}")
        if output.get('status') == 'ok':
            print(f"Output keys: {list(output.keys())}")
            if 'symbols' in output:
                print(f"Symbol count: {len(output.get('symbols', []))}")
                symbols = output.get('symbols', [])
                if symbols:
                    print(f"First few symbols: {symbols[:3]}")
            if 'files' in output:
                print(f"File count: {len(output.get('files', []))}")
                files = output.get('files', [])
                if files:
                    print(f"Files: {files}")
            if 'secrets' in output:
                print(f"Secrets: {output.get('secrets')}")
            if 'vulnerabilities' in output:
                print(f"Vulnerabilities: {output.get('vulnerabilities')}")
            if 'results' in output:
                print(f"Results: {output.get('results')}")
        else:
            print(f"Error: {output.get('error')}")
        return output
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Check all failing tools"""
    test_root = Path(__file__).parent.parent

    # extract_symbols
    check_tool_output(
        'extract_symbols',
        analysis_tools.extract_symbols,
        {'file_path': 'fixtures/repositories/simple-python/main.py'}
    )

    # list_files
    check_tool_output(
        'list_files',
        repository_tools.list_files,
        {'directory': 'fixtures/repositories/simple-python', 'recursive': True}
    )

    # scan_secrets
    check_tool_output(
        'scan_secrets',
        security_quality_tools.scan_secrets,
        {'repository_path': 'fixtures/repositories/security-challenge'}
    )

    # scan_vulnerabilities
    check_tool_output(
        'scan_vulnerabilities',
        security_quality_tools.scan_vulnerabilities,
        {'repository_path': 'fixtures/repositories/security-challenge'}
    )

    # search_symbols
    check_tool_output(
        'search_symbols',
        repository_tools.search_symbols,
        {'query': 'target', 'file_path': 'fixtures/repositories/simple-python/main.py'}
    )

if __name__ == '__main__':
    main()
