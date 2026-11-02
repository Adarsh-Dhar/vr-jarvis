#!/usr/bin/env python3
"""Detailed analysis of skipped tests to distinguish placeholders from missing adapters."""

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

placeholder_skipped = []
adapter_skipped = []
other_skipped = []

for test_dir in test_dirs:
    test_path = workspace / test_dir
    if not test_path.exists():
        continue
    
    for yaml_file in test_path.rglob('*.yaml'):
        try:
            with open(yaml_file) as f:
                test = yaml.safe_load(f)
            
            if test.get('expected', {}).get('status') == 'skipped':
                tool = test.get('tool', 'unknown')
                inputs = test.get('input', {})
                
                # Check for placeholder patterns
                has_placeholder = False
                for key, value in inputs.items():
                    if isinstance(value, str) and 'placeholder' in value.lower():
                        has_placeholder = True
                        break
                
                if has_placeholder:
                    placeholder_skipped.append((tool, str(yaml_file)))
                elif tool in tools_with_adapters:
                    other_skipped.append((tool, str(yaml_file)))
                else:
                    adapter_skipped.append((tool, str(yaml_file)))
        except Exception as e:
            pass

print(f'Total analyzed: {len(placeholder_skipped) + len(adapter_skipped) + len(other_skipped)}')
print(f'\nSkipped due to placeholders: {len(placeholder_skipped)}')
print(f'Skipped due to missing adapters: {len(adapter_skipped)}')
print(f'Skipped for other reasons: {len(other_skipped)}')

print(f'\nTop 20 tools needing adapters:')
tool_counts = defaultdict(int)
for tool, _ in adapter_skipped:
    tool_counts[tool] += 1
for tool, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f'  {tool}: {count} tests')
