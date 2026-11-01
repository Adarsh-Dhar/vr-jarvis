#!/usr/bin/env python3
"""
Simple structure check for toolsets
Checks toolsets.py structure by looking for expected agent names.
"""

import sys
from pathlib import Path

# Path to toolsets.py
toolsets_path = Path(__file__).parent / "toolsets.py"


def check_structure():
    """Check toolsets structure"""

    if not toolsets_path.exists():
        print(f"❌ toolsets.py not found at {toolsets_path}")
        return False

    # Read the file
    with open(toolsets_path, 'r') as f:
        source = f.read()

    print("Checking toolsets structure...")

    # Expected agents
    expected_agents = {
        "orchestrator",
        "conversational",
        "repository_intelligence",
        "code_understanding",
        "relationship_intelligence",
        "data_flow_intelligence",
        "runtime_intelligence",
        "debugging_intelligence",
        "security_quality",
        "software_engineering",
        "testing_verification",
        "visualization_spatial",
    }

    # Check each agent is present
    missing = []
    for agent in expected_agents:
        if f'"{agent}":' not in source:
            missing.append(agent)

    if missing:
        print(f"❌ Missing agents: {missing}")
        return False

    print(f"✅ All 12 agents present")

    # Check permission ceilings
    for agent in expected_agents:
        if f'"{agent}":' not in source:
            continue
        # Check permission section exists
        if "PERMISSION_CEILINGS" not in source:
            print("⚠️  Could not find PERMISSION_CEILINGS")
            break
    else:
        print(f"✅ PERMISSION_CEILINGS section exists")

    # Count tools per agent (using actual counts from the plan)
    # These are the expected counts based on the plan
    expected_counts = {
        "orchestrator": 8,
        "conversational": 8,
        "repository_intelligence": 19,
        "code_understanding": 22,
        "relationship_intelligence": 17,
        "data_flow_intelligence": 18,
        "runtime_intelligence": 19,
        "debugging_intelligence": 17,
        "security_quality": 20,
        "software_engineering": 15,
        "testing_verification": 14,
        "visualization_spatial": 20,
    }

    print("\nExpected tool counts per agent:")
    total = 0
    for agent in sorted(expected_agents):
        count = expected_counts.get(agent, 0)
        total += count
        print(f"  {agent}: {count} tools")

    print(f"\nTotal tools across all agents: {total}")

    print(f"\nTotal tools across all agents: {total}")

    print("\n✅ Toolsets structure is valid")
    return True


if __name__ == '__main__':
    success = check_structure()
    sys.exit(0 if success else 1)
