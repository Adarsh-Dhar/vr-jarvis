#!/usr/bin/env python3
"""
Test script to verify the server agent import succeeds.
Run this from the repository root: python3 test_server_import.py
"""

import sys
import traceback
from pathlib import Path

# Add server to path
server_path = Path(__file__).parent / "server"
sys.path.insert(0, str(server_path))

print("Testing server agent import...")
print("=" * 60)

try:
    from ai_agents.agent import root_agent
    print("✓ root_agent imported successfully")
    print(f"  Name: {root_agent.name}")
    print(f"  Description: {root_agent.description}")
    print(f"  Sub-agents: {len(root_agent.sub_agents)}")
    for sub in root_agent.sub_agents:
        print(f"    - {sub.name}")
    print("=" * 60)
    print("Server agent import succeeded!")
    sys.exit(0)
except Exception as e:
    print(f"✗ Server agent import FAILED")
    print(f"  Error: {str(e)}")
    print("=" * 60)
    traceback.print_exc()
    sys.exit(1)
