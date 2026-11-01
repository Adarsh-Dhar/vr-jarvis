#!/usr/bin/env python3
"""
Do-Nothing Tool Stub
Replaces all tools with a stub that returns {"status": "ok"}
Used for the do-nothing gate in CI to ensure tests can fail.
"""

from typing import Dict, Any

# Stub that returns {"status": "ok"} for any tool call
def do_nothing_tool(*args, **kwargs) -> Dict[str, Any]:
    """Stub that always returns success"""
    return {"status": "ok"}

# Create a dictionary mapping all tool names to the stub
def get_stub_tools():
    """Return a dictionary of all tool names mapped to the do-nothing stub"""
    # These are the tool modules from the JARVIS system
    tool_modules = [
        'repository_tools',
        'repository_intelligence_tools',
        'navigation_tools',
        'code_understanding_tools',
        'analysis_tools',
        'language_adapters',
        'graph_tools',
        'git_tools',
        'git_history_toolkit',
        'memory_tools',
        'exec_tools',
        'scene_tools',
        'control_tools',
        'relationship_intelligence_tools',
        'data_flow_intelligence_tools',
        'documentation_toolkit',
        'conversational_tools',
        'orchestrator_tools',
        'visualization_spatial_tools',
        'vr_specific_tools',
        'software_engineering_tools',
        'testing_verification_tools',
        'security_quality_tools',
        'debugging_intelligence_tools',
        'runtime_intelligence_tools',
        'infrastructure_services',
        'external_integrations_toolkit',
        'api_database_toolkit',
    ]

    stubs = {}
    for module in tool_modules:
        # For each module, we'd need to know the actual tool names
        # For now, we'll provide a generic stub function
        stubs[module] = do_nothing_tool

    return stubs


if __name__ == '__main__':
    # Test the stub
    result = do_nothing_tool()
    print(f"Stub result: {result}")
