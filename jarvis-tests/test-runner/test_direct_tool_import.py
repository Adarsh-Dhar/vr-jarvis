#!/usr/bin/env python3
"""
Test direct tool import without ai_agents package
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'server'))

# Import tool module directly
from ai_agents.tools import repository_tools

def test_direct_import():
    """Test importing tool functions directly"""
    print("Testing direct tool import...")

    # Check if read_file exists
    if hasattr(repository_tools, 'read_file'):
        print("✓ read_file function found")
        print(f"  Signature: {repository_tools.read_file.__code__.co_varnames}")
    else:
        print("✗ read_file function not found")

if __name__ == '__main__':
    test_direct_import()
