#!/usr/bin/env python3
"""Analyze which tools have adapters and which need them."""

import yaml
from pathlib import Path
from collections import defaultdict

workspace = Path('/Users/adarsh/Documents/vr-agent')

# Tools that have adapter branches in batch_execute_tests.py
tools_with_adapters = {
    'exit_loop', 'request_sensitive_approval', 'check_permission', 'grant_permission',
    'search_graph_symbols', 'get_callers', 'get_callees', 'get_dependents',
    'capture_exception', 'analyze_stack_trace', 'find_error_origin', 'trace_error_propagation',
    'identify_failure_path', 'record_function_calls', 'record_function_arguments',
    'record_function_returns', 'record_variable_state', 'collect_execution_trace',
    'docker_get_container_logs', 'move_file', 'rename_file', 'get_diff',
    'get_branch_info', 'get_symbol_definition', 'search_external_docs',
    'get_framework_adapter', 'register_language_adapter', 'add_graph_node',
    'remove_graph_node', 'add_graph_edge', 'remove_graph_edge', 'filter_graph',
    'parse_language_ast', 'resolve_language_types', 'set_spatial_audio',
    'set_haptic_feedback', 'find_introducing_commit', 'analyze_commit_impact',
    'trace_file_history', 'search_graph', 'get_node', 'create_graph',
    'expand_graph_node', 'collapse_graph_node', 'git_show',
}

test_dirs = [
    'jarvis-tests/tests/layer1',
    'jarvis-tests/tests/layer2',
]

tools_needing_adapters = defaultdict(list)
tools_with_params = defaultdict(list)

for test_dir in test_dirs:
    test_path = workspace / test_dir
    if not test_path.exists():
        continue
    
    for yaml_file in test_path.rglob('*.yaml'):
        try:
            with open(yaml_file) as f:
                test = yaml.safe_load(f)
            
            tool = test.get('tool', 'unknown')
            inputs = test.get('input', {})
            
            if tool not in tools_with_adapters:
                tools_needing_adapters[tool].append(str(yaml_file))
            
            # Collect parameter names
            param_names = list(inputs.keys())
            for param in param_names:
                tools_with_params[tool].add(param)
        except Exception as e:
            pass

print(f'Tools needing adapters: {len(tools_needing_adapters)}')
print(f'\nTop 20 tools needing adapters (by test count):')
for tool, files in sorted(tools_needing_adapters.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
    print(f'  {tool}: {len(files)} tests')
    print(f'    Parameters: {sorted(tools_with_params[tool])}')
