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


def _walk(agent):
    yield agent
    for sub in getattr(agent, 'sub_agents', None) or []:
        yield from _walk(sub)


def _tool_name(t):
    return getattr(t, 'name', None) or getattr(t, '__name__', str(t))


def collect_active_agents():
    """Every real ADK agent in the live tree: the root agent, the fix
    pipelines and the dynamically built gate/repair/verifier instances."""
    from ai_agents.agent import root_agent, fix_pipeline, review_loop
    from ai_agents.agents import fix
    agents = list(_walk(root_agent))
    agents += list(_walk(fix_pipeline)) + list(_walk(review_loop))
    agents += [fix.make_patch_repair(), fix.make_patch_review_repair(),
               fix.make_review_verifier(),
               fix.make_review_verifier('gate_review_verifier_agent')]
    return {a.name: a for a in agents if getattr(a, 'tools', None)}


def validate_agent_bindings():
    """Check every tool bound to a live agent against the registry contract:
    exported, in MVP_TOOL_NAMES, permission level, owner, agent toolset,
    input schema and output schema. Returns a list of (agent, tool, reason)."""
    from ai_agents import tools as tools_module
    from ai_agents.agents.toolsets import (MVP_TOOL_NAMES, MVP_TOOL_OWNERS,
                                           PERMISSION_CEILINGS, TOOL_LEVELS,
                                           TOOLSETS)
    from ai_agents.registry.tool_registry import get_tool_registry
    from ai_agents.registry.output_schemas import OUTPUT_SCHEMAS
    reg, errors = get_tool_registry(), []
    for aname, agent in collect_active_agents().items():
        for t in agent.tools:
            n = _tool_name(t)
            spec = reg.get(n)
            if not hasattr(tools_module, n):
                errors.append((aname, n, 'not exported'))
            if n not in MVP_TOOL_NAMES:
                errors.append((aname, n, 'not in MVP_TOOL_NAMES'))
            if n not in TOOL_LEVELS:
                errors.append((aname, n, 'no permission level'))
            if not MVP_TOOL_OWNERS.get(n):
                errors.append((aname, n, 'no owner'))
            if n not in TOOLSETS.get(aname, []):
                errors.append((aname, n, 'not in agent toolset'))
            if spec is None or spec.input_schema is None:
                errors.append((aname, n, 'no input schema'))
            if n not in OUTPUT_SCHEMAS:
                errors.append((aname, n, 'no output schema'))
    return errors


if __name__ == '__main__':
    success = validate_toolsets()
    sys.exit(0 if success else 1)
