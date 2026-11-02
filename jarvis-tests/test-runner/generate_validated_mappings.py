#!/usr/bin/env python3
"""Generate validated tool mappings directly from server modules"""
import sys
sys.path.insert(0, '/Users/adarsh/Documents/vr-agent/server')

from ai_agents.tools import repository_intelligence_tools, analysis_tools, api_database_toolkit, security_quality_tools
from ai_agents.tools import language_adapters, relationship_intelligence_tools, code_understanding_tools, software_engineering_tools
from ai_agents.tools import git_tools, data_flow_intelligence_tools, debugging_intelligence_tools, documentation_toolkit
from ai_agents.tools import external_integrations_toolkit, git_history_toolkit, graph_tools, infrastructure_services
from ai_agents.tools import memory_tools, navigation_tools, orchestrator_tools, runtime_intelligence_tools
from ai_agents.tools import scene_tools, visualization_spatial_tools, vr_specific_tools, conversational_tools
from ai_agents.tools import control_tools, exec_tools, repository_tools, testing_verification_tools

modules = [
    repository_intelligence_tools, analysis_tools, api_database_toolkit, security_quality_tools,
    language_adapters, relationship_intelligence_tools, code_understanding_tools, software_engineering_tools,
    git_tools, data_flow_intelligence_tools, debugging_intelligence_tools, documentation_toolkit,
    external_integrations_toolkit, git_history_toolkit, graph_tools, infrastructure_services,
    memory_tools, navigation_tools, orchestrator_tools, runtime_intelligence_tools,
    scene_tools, visualization_spatial_tools, vr_specific_tools, conversational_tools,
    control_tools, exec_tools, repository_tools, testing_verification_tools
]

# Get all functions from modules
valid_mappings = {}
for module in modules:
    module_name = module.__name__.replace('server.ai_agents.tools.', '')
    for attr_name in dir(module):
        if not attr_name.startswith('_'):
            attr = getattr(module, attr_name)
            if callable(attr):
                valid_mappings[attr_name] = f"{module_name}.{attr_name}"

print(f"Total valid functions: {len(valid_mappings)}")

# Generate Python dictionary mapping
print("\n# Tool mapping - validated mappings only")
print("TOOL_FUNCTIONS = {")
for func_name in sorted(valid_mappings.keys()):
    print(f"    '{func_name}': {valid_mappings[func_name]},")
print("}")
