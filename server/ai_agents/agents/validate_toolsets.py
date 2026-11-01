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
    import inspect
    from ai_agents.agents.toolsets import TOOLSETS, PERMISSION_CEILINGS, TOOL_PERMISSIONS

    # Get all available tools from the tools module
    from ai_agents import tools as tools_module

    available_tools = set(
        name for name, obj in inspect.getmembers(tools_module)
        if callable(obj) and not name.startswith('_')
    )

    print(f"Total available tools: {len(available_tools)}")

    errors = []
    tool_counts = {}

    for agent_name, tool_list in TOOLSETS.items():
        tool_counts[agent_name] = len(tool_list)

        # Check for duplicates within agent
        tool_names = [tool.__name__ if hasattr(tool, '__name__') else str(tool) for tool in tool_list]
        if len(tool_names) != len(set(tool_names)):
            duplicates = [name for name in tool_names if tool_names.count(name) > 1]
            errors.append(f"{agent_name}: Duplicate tools: {set(duplicates)}")

        # Check all tools exist
        for tool in tool_list:
            tool_name = tool.__name__ if hasattr(tool, '__name__') else str(tool)
            if tool_name not in available_tools:
                errors.append(f"{agent_name}: Tool not found: {tool_name}")

        # Check permission ceiling
        permission_ceiling = PERMISSION_CEILINGS.get(agent_name, "read")
        for tool in tool_list:
            tool_name = tool.__name__ if hasattr(tool, '__name__') else str(tool)
            # Determine tool permission level
            tool_perm = "read"  # default
            for perm_level, perm_tools in TOOL_PERMISSIONS.items():
                if tool_name in perm_tools:
                    tool_perm = perm_level
                    break

            # Check if tool exceeds ceiling
            perm_order = {"read": 0, "execute": 1, "write": 2}
            if perm_order.get(tool_perm, 0) > perm_order.get(permission_ceiling, 0):
                errors.append(
                    f"{agent_name}: Tool {tool_name} requires {tool_perm} permission, "
                    f"but agent has {permission_ceiling} ceiling"
                )

    # Print tool counts
    print("\nTool counts per agent:")
    for agent, count in sorted(tool_counts.items()):
        print(f"  {agent}: {count} tools")

    total_tools = sum(tool_counts.values())
    print(f"\nTotal tools across all agents: {total_tools}")

    if errors:
        print(f"\n❌ Validation failed with {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n✅ Toolset validation passed: All tools exist and are within permission ceilings")
        return True


if __name__ == '__main__':
    success = validate_toolsets()
    sys.exit(0 if success else 1)
