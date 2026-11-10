#!/usr/bin/env python3
"""
Validate toolsets
Checks that all tools in toolsets.py exist and are within permission ceilings.
Run this as a CI check or during development.
"""

import sys
from pathlib import Path

# Add server to path
server_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(server_path))


def validate_toolsets():
    """Validate toolsets against available tools"""
    from ai_agents.agents.toolsets import TOOLSETS, PERMISSION_CEILINGS, TOOL_LEVELS, validate_toolsets as _validate

    tool_counts = {agent: len(tools) for agent, tools in TOOLSETS.items()}

    print("\nTool counts per agent:")
    for agent, count in sorted(tool_counts.items()):
        print(f"  {agent}: {count} tools")

    print(f"\nTotal tools across all agents: {sum(tool_counts.values())}")

    try:
        _validate()
    except ValueError as e:
        print(f"\nValidation failed:\n{e}")
        return False

    print("\nAll tools exist and are within permission ceilings")
    return True


if __name__ == '__main__':
    success = validate_toolsets()
    sys.exit(0 if success else 1)
