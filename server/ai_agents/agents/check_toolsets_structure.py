#!/usr/bin/env python3
"""
Quick structure check for toolsets
Validates toolsets.py structure without importing the full tools module.
"""

import sys
from pathlib import Path

# Add server to path
server_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(server_path))


def check_structure():
    """Check toolsets structure"""
    from ai_agents.agents.toolsets import TOOLSETS, PERMISSION_CEILINGS

    print("Checking toolsets structure...")

    # Check we have 12 agents
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

    actual_agents = set(TOOLSETS.keys())

    if actual_agents != expected_agents:
        missing = expected_agents - actual_agents
        extra = actual_agents - expected_agents
        print(f"❌ Agent mismatch:")
        if missing:
            print(f"  Missing: {missing}")
        if extra:
            print(f"  Extra: {extra}")
        return False

    print(f"✅ All 12 agents present")

    # Check permission ceilings
    for agent in expected_agents:
        if agent not in PERMISSION_CEILINGS:
            print(f"❌ Missing permission ceiling for {agent}")
            return False

    print(f"✅ All agents have permission ceilings")

    # Check tool counts
    print("\nTool counts per agent:")
    total = 0
    for agent in sorted(TOOLSETS.keys()):
        count = len(TOOLSETS[agent])
        total += count
        print(f"  {agent}: {count} tools")

    print(f"\nTotal tools across all agents: {total}")

    # Check each agent has tools
    for agent, tools in TOOLSETS.items():
        if not tools:
            print(f"❌ Agent {agent} has no tools")
            return False

    print(f"✅ All agents have tools")

    # Check for duplicates within each agent (now checking string names)
    for agent, tool_names in TOOLSETS.items():
        if len(tool_names) != len(set(tool_names)):
            duplicates = [name for name in tool_names if tool_names.count(name) > 1]
            print(f"❌ Agent {agent} has duplicate tools: {set(duplicates)}")
            return False

    print(f"✅ No duplicate tools within agents")

    print("\n✅ Toolsets structure is valid")
    return True


if __name__ == '__main__':
    success = check_structure()
    sys.exit(0 if success else 1)
