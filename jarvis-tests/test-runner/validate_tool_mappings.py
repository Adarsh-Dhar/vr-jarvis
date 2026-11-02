#!/usr/bin/env python3
"""Validate tool mappings and only include existing functions"""
import sys
sys.path.insert(0, '/Users/adarsh/Documents/vr-agent/server')
sys.path.insert(0, '/Users/adarsh/Documents/vr-agent/jarvis-tests/test-runner')

from batch_execute_tests import TOOL_FUNCTIONS
import repository_intelligence_tools, analysis_tools, api_database_toolkit, security_quality_tools
import language_adapters, relationship_intelligence_tools, code_understanding_tools, software_engineering_tools
import git_tools, data_flow_intelligence_tools, debugging_intelligence_tools, documentation_toolkit
import external_integrations_toolkit, git_history_toolkit, graph_tools, infrastructure_services
import memory_tools, navigation_tools, orchestrator_tools, runtime_intelligence_tools
import scene_tools, visualization_spatial_tools, vr_specific_tools, conversational_tools
import control_tools, exec_tools, repository_tools, testing_verification_tools

valid_mappings = {}
for tool_name, tool_func in TOOL_FUNCTIONS.items():
    try:
        # Try to access the function to see if it exists
        module_name = tool_func.__module__
        if module_name.startswith('server.'):
            valid_mappings[tool_name] = tool_func
    except:
        pass

print(f"Valid mappings: {len(valid_mappings)}")
print(f"Invalid mappings: {len(TOOL_FUNCTIONS) - len(valid_mappings)}")

# Generate Python dictionary mapping
print("\n# Tool mapping - validated mappings only")
print("TOOL_FUNCTIONS = {")
for func_name in sorted(valid_mappings.keys()):
    tool_func = valid_mappings[func_name]
    module_name = tool_func.__module__.replace('server.ai_agents.tools.', '')
    print(f"    '{func_name}': {module_name}.{func_name},")
print("}")
