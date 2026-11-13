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
            elif getattr(tools_module, n) is not getattr(t, '__wrapped__', t) \
                    and getattr(tools_module, n) is not t \
                    and getattr(tools_module, n) is not getattr(t, 'func', t):
                errors.append((aname, n, 'bound callable differs from exported tool'))
            if n not in MVP_TOOL_NAMES:
                errors.append((aname, n, 'not in MVP_TOOL_NAMES'))
            if n not in TOOL_LEVELS:
                errors.append((aname, n, 'no permission level'))
            if not MVP_TOOL_OWNERS.get(n):
                errors.append((aname, n, 'no owner'))
            owners = set(spec.owner_agents if spec else [])
            if aname not in owners:
                errors.append((aname, n, f'agent is not an authorized owner; owners={sorted(owners)}'))
            if n not in TOOLSETS.get(aname, []):
                errors.append((aname, n, 'not in agent toolset'))
            if spec is None or spec.input_schema is None:
                errors.append((aname, n, 'no input schema'))
            if n not in OUTPUT_SCHEMAS:
                errors.append((aname, n, 'no output schema'))
    return errors


def collect_live_agent_index():
    """Every agent node in the live tree keyed by name, including pipeline
    nodes that own no direct tools."""
    from ai_agents.agent import root_agent, fix_pipeline, review_loop
    from ai_agents.agents import fix
    agents = []
    for root in (root_agent, fix_pipeline, review_loop):
        agents += list(_walk(root))
    agents += [fix.make_patch_repair(), fix.make_patch_review_repair(),
               fix.make_review_verifier(),
               fix.make_review_verifier('gate_review_verifier_agent')]
    return {a.name: a for a in agents if getattr(a, 'name', None)}


def validate_delegation_contracts(live_agents=None):
    """Validate DELEGATED_TOOL_ROUTES / DELEGATED_PIPELINE_ROUTES against the
    live agent tree. Returns a list of (agent, tool, reason) errors."""
    from ai_agents.agents.agent_contracts import (
        DELEGATED_PIPELINE_ROUTES, DELEGATED_TOOL_ROUTES)
    live_agents = live_agents if live_agents is not None else collect_live_agent_index()
    errors = []

    for delegating_agent, routes in DELEGATED_TOOL_ROUTES.items():
        for tool_name, pipeline_name in routes.items():
            pipeline = live_agents.get(pipeline_name)
            if pipeline is None:
                errors.append((delegating_agent, tool_name,
                               f'delegated pipeline {pipeline_name} does not exist'))
                continue
            descendants = list(_walk(pipeline))
            owners = {
                getattr(child, 'name', '')
                for child in descendants
                if tool_name in {_tool_name(t)
                                 for t in (getattr(child, 'tools', None) or [])}
            }
            if not owners:
                errors.append((delegating_agent, tool_name,
                               'delegated pipeline has no descendant that owns the tool'))
            # The delegating agent must not bind the tool directly.
            delegator = live_agents.get(delegating_agent)
            if delegator is not None:
                bound = {_tool_name(t) for t in (getattr(delegator, 'tools', None) or [])}
                if tool_name in bound:
                    errors.append((delegating_agent, tool_name,
                                   'delegating agent directly binds a delegated tool'))

    for delegating_agent, routes in DELEGATED_PIPELINE_ROUTES.items():
        for _route_name, pipeline_name in routes.items():
            if pipeline_name not in live_agents:
                errors.append((delegating_agent, _route_name,
                               f'delegated pipeline {pipeline_name} does not exist'))

    return errors


def validate_runtime_agent_contracts():
    """Startup contract check: toolsets resolve, every live agent's tool
    bindings satisfy the registry, delegated routes point at pipelines whose
    descendants really own the tools, and no agent instruction names a tool
    it neither binds nor delegates. Raises RuntimeError on any violation —
    the server refuses to start."""
    from ai_agents.agents.agent_contracts import DELEGATED_TOOL_ROUTES
    from ai_agents.agents.toolsets import validate_toolsets as _vt, \
        validate_instruction_tools
    errors = []
    try:
        _vt()
    except ValueError as e:
        errors.append(('toolsets', '-', str(e)))
    errors.extend(validate_agent_bindings())
    errors.extend(validate_delegation_contracts())
    for aname, agent in collect_active_agents().items():
        instruction = getattr(agent, 'instruction', '')
        if not isinstance(instruction, str):
            instruction = ''
        try:
            errors.extend((aname, '-', e) for e in
                          validate_instruction_tools(
                              {aname: instruction},
                              delegated_routes=DELEGATED_TOOL_ROUTES))
        except Exception as e:
            errors.append((aname, '-', 'instruction/tool mismatch: %s' % e))
    if errors:
        raise RuntimeError('Agent/tool integration validation failed:\n'
                           + '\n'.join(map(str, errors)))


if __name__ == '__main__':
    success = validate_toolsets()
    sys.exit(0 if success else 1)
