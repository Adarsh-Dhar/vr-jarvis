#!/usr/bin/env python3
"""Inspect tool signatures and create parameter mapping."""

import inspect
import sys
import importlib
sys.path.insert(0, '/Users/adarsh/Documents/vr-agent')

# Import tool modules directly to avoid agent initialization
repository_tools = importlib.import_module('server.ai_agents.tools.repository_tools')
code_understanding_tools = importlib.import_module('server.ai_agents.tools.code_understanding_tools')
relationship_intelligence_tools = importlib.import_module('server.ai_agents.tools.relationship_intelligence_tools')
repository_intelligence_tools = importlib.import_module('server.ai_agents.tools.repository_intelligence_tools')
analysis_tools = importlib.import_module('server.ai_agents.tools.analysis_tools')
testing_verification_tools = importlib.import_module('server.ai_agents.tools.testing_verification_tools')
software_engineering_tools = importlib.import_module('server.ai_agents.tools.software_engineering_tools')
git_tools = importlib.import_module('server.ai_agents.tools.git_tools')
data_flow_intelligence_tools = importlib.import_module('server.ai_agents.tools.data_flow_intelligence_tools')
api_database_tools = importlib.import_module('server.ai_agents.tools.api_database_toolkit')
debugging_intelligence_tools = importlib.import_module('server.ai_agents.tools.debugging_intelligence_tools')
documentation_tools = importlib.import_module('server.ai_agents.tools.documentation_toolkit')
external_integrations_tools = importlib.import_module('server.ai_agents.tools.external_integrations_toolkit')
git_history_tools = importlib.import_module('server.ai_agents.tools.git_history_toolkit')
graph_tools = importlib.import_module('server.ai_agents.tools.graph_tools')
infrastructure_tools = importlib.import_module('server.ai_agents.tools.infrastructure_services')
language_adapters_tools = importlib.import_module('server.ai_agents.tools.language_adapters')
memory_tools = importlib.import_module('server.ai_agents.tools.memory_tools')
navigation_tools = importlib.import_module('server.ai_agents.tools.navigation_tools')
orchestrator_tools = importlib.import_module('server.ai_agents.tools.orchestrator_tools')
runtime_intelligence_tools = importlib.import_module('server.ai_agents.tools.runtime_intelligence_tools')
scene_tools = importlib.import_module('server.ai_agents.tools.scene_tools')
security_tools = importlib.import_module('server.ai_agents.tools.security_quality_tools')
visualization_tools = importlib.import_module('server.ai_agents.tools.visualization_spatial_tools')
vr_tools = importlib.import_module('server.ai_agents.tools.vr_specific_tools')
conversational_tools = importlib.import_module('server.ai_agents.tools.conversational_tools')
control_tools = importlib.import_module('server.ai_agents.tools.control_tools')
exec_tools = importlib.import_module('server.ai_agents.tools.exec_tools')

def get_tool_signature(func):
    """Get signature information for a tool function."""
    sig = inspect.signature(func)
    params = []
    required = []
    optional = []
    
    for name, param in sig.parameters.items():
        param_info = {
            'name': name,
            'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
            'default': str(param.default) if param.default != inspect.Parameter.empty else None,
            'has_default': param.default != inspect.Parameter.empty
        }
        params.append(param_info)
        if param.default == inspect.Parameter.empty:
            required.append(name)
        else:
            optional.append(name)
    
    return {
        'params': params,
        'required': required,
        'optional': optional,
        'param_count': len(params)
    }

def inspect_module(module_name, module):
    """Inspect all functions in a module."""
    results = {}
    for name in dir(module):
        obj = getattr(module, name)
        # Only inspect actual functions, not classes or type annotations
        if inspect.isfunction(obj) and not name.startswith('_'):
            try:
                sig_info = get_tool_signature(obj)
                results[name] = sig_info
            except Exception as e:
                pass
    return results

def main():
    """Inspect all tool modules."""
    modules = [
        repository_tools,
        code_understanding_tools,
        relationship_intelligence_tools,
        repository_intelligence_tools,
        analysis_tools,
        testing_verification_tools,
        software_engineering_tools,
        git_tools,
        data_flow_intelligence_tools,
        api_database_tools,
        debugging_intelligence_tools,
        documentation_tools,
        external_integrations_tools,
        git_history_tools,
        graph_tools,
        infrastructure_tools,
        language_adapters_tools,
        memory_tools,
        navigation_tools,
        orchestrator_tools,
        runtime_intelligence_tools,
        scene_tools,
        security_tools,
        visualization_tools,
        vr_tools,
        conversational_tools,
        control_tools,
        exec_tools,
    ]
    
    all_tools = {}
    for module in modules:
        module_name = module.__name__
        print(f"Inspecting {module_name}...")
        tools = inspect_module(module_name, module)
        all_tools.update(tools)
    
    # Print summary
    print(f"\nTotal tools found: {len(all_tools)}")
    
    # Print tools that need adapters (have parameters beyond tool_context)
    print("\nTools needing adapters (have parameters beyond tool_context):")
    needs_adapter = []
    for name, sig in sorted(all_tools.items()):
        if sig['param_count'] > 1 or (sig['param_count'] == 1 and sig['params'][0]['name'] != 'tool_context'):
            needs_adapter.append((name, sig))
    
    print(f"Total tools needing adapters: {len(needs_adapter)}")
    
    # Print tools that only take tool_context
    print("\nTools that only take tool_context:")
    context_only = []
    for name, sig in sorted(all_tools.items()):
        if sig['param_count'] == 1 and sig['params'][0]['name'] == 'tool_context':
            context_only.append(name)
    
    print(f"Total context-only tools: {len(context_only)}")
    
    # Save detailed output
    import json
    with open('/Users/adarsh/Documents/vr-agent/jarvis-tests/test-runner/tool_signatures.json', 'w') as f:
        json.dump(all_tools, f, indent=2)
    
    print("\nDetailed signatures saved to tool_signatures.json")

if __name__ == '__main__':
    main()
