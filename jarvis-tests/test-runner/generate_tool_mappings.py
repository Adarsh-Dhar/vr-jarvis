#!/usr/bin/env python3
"""Generate all tool mappings from server to batch executor"""
import re
from pathlib import Path

WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')
TOOLS_DIR = WORKSPACE / 'server/ai_agents/tools'

# Module name mapping
module_map = {
    'repository_tools.py': 'repository_tools',
    'code_understanding_tools.py': 'code_understanding_tools',
    'relationship_intelligence_tools.py': 'relationship_intelligence_tools',
    'repository_intelligence_tools.py': 'repository_intelligence_tools',
    'analysis_tools.py': 'analysis_tools',
    'testing_verification_tools.py': 'testing_verification_tools',
    'software_engineering_tools.py': 'software_engineering_tools',
    'git_tools.py': 'git_tools',
    'data_flow_intelligence_tools.py': 'data_flow_intelligence_tools',
    'api_database_toolkit.py': 'api_database_toolkit',
    'debugging_intelligence_tools.py': 'debugging_intelligence_tools',
    'documentation_toolkit.py': 'documentation_toolkit',
    'external_integrations_toolkit.py': 'external_integrations_toolkit',
    'git_history_toolkit.py': 'git_history_toolkit',
    'graph_tools.py': 'graph_tools',
    'infrastructure_services.py': 'infrastructure_services',
    'language_adapters.py': 'language_adapters',
    'memory_tools.py': 'memory_tools',
    'navigation_tools.py': 'navigation_tools',
    'orchestrator_tools.py': 'orchestrator_tools',
    'runtime_intelligence_tools.py': 'runtime_intelligence_tools',
    'scene_tools.py': 'scene_tools',
    'security_quality_tools.py': 'security_quality_tools',
    'visualization_spatial_tools.py': 'visualization_spatial_tools',
    'vr_specific_tools.py': 'vr_specific_tools',
    'conversational_tools.py': 'conversational_tools',
    'control_tools.py': 'control_tools',
    'exec_tools.py': 'exec_tools',
}

# Find all function definitions in server tools
server_functions = {}
for py_file in TOOLS_DIR.glob('*.py'):
    if py_file.name.startswith('_'):
        continue
    module_name = module_map.get(py_file.name, py_file.name.replace('.py', ''))
    try:
        with open(py_file) as f:
            content = f.read()
        # Find all function definitions
        for match in re.finditer(r'def (\w+)\(', content):
            func_name = match.group(1)
            if not func_name.startswith('_'):
                server_functions[func_name] = module_name
    except:
        pass

# Generate Python dictionary mapping
print("TOOL_FUNCTIONS = {")
for func_name in sorted(server_functions.keys()):
    module = server_functions[func_name]
    print(f"    '{func_name}': {module}.{func_name},")
print("}")
