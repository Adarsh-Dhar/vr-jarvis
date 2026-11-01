#!/usr/bin/env python3
"""
Test script to verify all agent imports succeed.
Run this from the repository root: python test_agent_imports.py
"""

import sys
import traceback
from pathlib import Path

# Add server to path
server_path = Path(__file__).parent / "server"
sys.path.insert(0, str(server_path))

print("Testing agent imports...")
print("=" * 60)

agents_to_test = [
    ("repository_intelligence", "server.ai_agents.agents.repository_intelligence"),
    ("code_understanding", "server.ai_agents.agents.code_understanding"),
    ("relationship_intelligence", "server.ai_agents.agents.relationship_intelligence"),
    ("visualization", "server.ai_agents.agents.visualization"),
    ("conversational", "server.ai_agents.agents.conversational"),
    ("orchestrator", "server.ai_agents.agents.orchestrator"),
    ("data_flow", "server.ai_agents.agents.data_flow"),
    ("runtime", "server.ai_agents.agents.runtime"),
    ("debugging", "server.ai_agents.agents.debugging"),
    ("security_quality", "server.ai_agents.agents.security_quality"),
    ("software_engineering", "server.ai_agents.agents.software_engineering"),
    ("testing_verification", "server.ai_agents.agents.testing_verification"),
]

passed = []
failed = []

for name, module_path in agents_to_test:
    try:
        __import__(module_path)
        print(f"✓ {name:30} OK")
        passed.append(name)
    except Exception as e:
        print(f"✗ {name:30} FAILED")
        print(f"  Error: {str(e)[:100]}")
        if "--verbose" in sys.argv:
            traceback.print_exc()
        failed.append((name, str(e)))

print("=" * 60)
print(f"Results: {len(passed)} passed, {len(failed)} failed")

if failed:
    print("\nFailed imports:")
    for name, error in failed:
        print(f"  - {name}: {error}")
    sys.exit(1)
else:
    print("\nAll agent imports succeeded!")
    sys.exit(0)
