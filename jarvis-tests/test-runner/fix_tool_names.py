#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
"""
Map fictional tool names to real tool names from the server
"""
import sys
from pathlib import Path
import yaml

WORKSPACE = Path('/Users/adarsh/Documents/vr-agent')
TESTS_ROOT = WORKSPACE / 'jarvis-tests/tests'

# Mapping of fictional tool names to real tool names
TOOL_NAME_MAP = {
    # Repository tools
    'list_repository_files': 'list_files',
    'get_file': 'read_file',
    'get_file_content': 'read_file',
    'search_repository': 'search_files',
    'find_files': 'search_files',
    
    # Code understanding
    'parse_file': 'parse_source_code',
    'extract_ast': 'extract_ast',
    'get_symbols': 'extract_symbols',
    'resolve_type': 'resolve_types',
    'resolve_ref': 'resolve_references',
    'analyze_flow': 'analyze_control_flow',
    
    # Relationship tools
    'get_call_graph': 'build_call_graph',
    'get_dependency_graph': 'build_dependency_graph',
    'get_reference_graph': 'build_reference_graph',
    'get_class_graph': 'build_class_relationship_graph',
    'trace_calls': 'trace_call_chain',
    
    # Repository intelligence
    'detect_lang': 'detect_languages',
    'detect_framework': 'detect_frameworks',
    'get_entry_points': 'identify_entry_points',
    'detect_build': 'detect_build_system',
    'detect_pkg': 'detect_package_manager',
    'detect_type': 'detect_project_type',
    'analyze_repo': 'analyze_repository_structure',
    'analyze_monorepo': 'analyze_monorepo',
    'analyze_config': 'analyze_project_configuration',
    'analyze_build_config': 'analyze_build_configuration',
    
    # Analysis tools
    'analyze_annotations': 'analyze_annotations',
    'analyze_complexity': 'analyze_code_complexity',
    'analyze_deps': 'analyze_dependencies',
    'analyze_exceptions': 'analyze_exceptions',
    'analyze_gen_code': 'analyze_generated_code',
    'analyze_macros': 'analyze_macros',
    
    # Git tools
    'get_git_diff': 'get_diff',
    'get_git_status': 'list_changed_nodes',
    'get_branch': 'get_branch_info',
    'git_status': 'list_changed_nodes',
    'git_diff': 'get_diff',
    'git_branch': 'get_branch_info',
    
    # Software engineering
    'create_new_file': 'create_file',
    'update_file': 'edit_file',
    'remove_file': 'delete_file',
    'move_file': 'move_file',
    'rename': 'rename_file',
    'new_directory': 'create_directory',
    
    # Testing
    'run_tests': 'run_unit_tests',
    'discover_tests': 'discover_tests',
    'measure_coverage': 'measure_test_coverage',
    'verify_build': 'verify_compilation',
    
    # Data flow
    'trace_var_origin': 'trace_variable_origin',
    'trace_var_usage': 'trace_variable_usage',
    'trace_var_mod': 'trace_variable_modifications',
    'trace_param': 'trace_parameter_flow',
    'trace_return': 'trace_return_value_flow',
    'trace_transform': 'trace_transformations',
    'trace_cross_func': 'trace_cross_function_flow',
    'trace_cross_service': 'trace_cross_service_flow',
    'trace_db_read': 'trace_database_reads',
    'trace_db_write': 'trace_database_writes',
    'trace_api': 'trace_api_data_flow',
    'trace_file_ops': 'trace_file_operations',
    'trace_state': 'trace_state_changes',
    'build_flow_graph': 'build_data_flow_graph',
    'find_sinks': 'identify_data_sinks',
    'find_sources': 'identify_data_sources',
    'find_leaks': 'identify_data_leaks',
    'find_gaps': 'identify_validation_gaps',
    
    # Navigation
    'get_definition': 'get_symbol_definition',
    'get_refs': 'get_symbol_references',
    'get_hover': 'get_symbol_hover_info',
    'get_hierarchy': 'get_call_hierarchy',
    'get_type_hier': 'get_type_hierarchy',
    'get_imports': 'get_imports',
    
    # Documentation
    'search_docs': 'search_documentation',
    'gen_docs': 'generate_code_documentation',
    'extract_docs': 'extract_docstrings',
    'verify_docs': 'verify_documentation_coverage',
    'read_docs': 'read_documentation',
    
    # API/Database
    'discover_api': 'discover_api_endpoints',
    'inspect_api': 'inspect_api_schema',
    'analyze_api': 'analyze_api_contract',
    'trace_api_call': 'trace_api_call',
    'analyze_api_sec': 'analyze_api_security',
    'inspect_routes': 'inspect_http_routes',
    'inspect_middleware': 'inspect_middleware',
    'inspect_auth': 'inspect_authentication',
    'inspect_authz': 'inspect_authorization',
    
    # Debugging
    'capture_exception': 'capture_exception',
    'analyze_stack': 'analyze_stack_trace',
    'find_error': 'find_error_origin',
    'trace_error': 'trace_error_propagation',
    'find_failure': 'identify_failure_path',
    'set_breakpoint': 'set_breakpoint',
    'remove_breakpoint': 'remove_breakpoint',
    'step_into': 'step_into',
    'step_over': 'step_over',
    'step_out': 'step_out',
    
    # Orchestrator
    'understand_intent': 'understand_user_intent',
    'classify': 'classify_request',
    'create_plan': 'create_investigation_plan',
    'decompose': 'decompose_task',
    'select_agents': 'select_agents',
    'delegate': 'delegate_task',
    'run_parallel': 'run_agents_parallel',
    'run_sequential': 'run_agents_sequentially',
    'wait_agent': 'wait_for_agent',
    'agent_status': 'get_agent_status',
    
    # Conversational
    'speech_to_text': 'speech_to_text',
    'text_to_speech': 'text_to_speech',
    'stream_voice': 'stream_voice_response',
    'detect_intent': 'detect_speaker_intent',
    'detect_voice': 'detect_voice_activity',
    'manage_conv': 'manage_conversation',
    'get_context': 'retrieve_conversation_context',
    
    # Infrastructure
    'check_perm': 'check_permission',
    'grant_perm': 'grant_permission',
    'revoke_perm': 'revoke_permission',
    'list_perms': 'list_permissions',
    'set_perm_level': 'set_permission_level',
    'request_sensitive': 'request_sensitive_approval',
    'check_approval': 'check_approval_status',
    'register_tool': 'register_tool',
    'unregister_tool': 'unregister_tool',
    'get_tool_def': 'get_tool_definition',
    
    # Language adapters
    'register_lang': 'register_language_adapter',
    'get_lang': 'get_language_adapter',
    'list_langs': 'list_supported_languages',
    'parse_ast': 'parse_language_ast',
    'resolve_types': 'resolve_language_types',
    'extract_lang_symbols': 'extract_language_symbols',
    'analyze_lang_features': 'analyze_language_specific_features',
    'register_framework': 'register_framework_adapter',
    'get_framework': 'get_framework_adapter',
    'list_frameworks': 'list_supported_frameworks',
    
    # Memory
    'load_memory': 'load_project_memory',
    'save_finding': 'save_finding',
    'record_decision': 'record_decision',
    
    # Runtime
    'start_app': 'start_application',
    'stop_app': 'stop_application',
    'attach_profiler': 'attach_runtime_profiler',
    'attach_debugger': 'attach_debugger',
    'collect_trace': 'collect_execution_trace',
    'record_calls': 'record_function_calls',
    'record_args': 'record_function_arguments',
    'record_returns': 'record_function_returns',
    'record_timing': 'record_execution_timing',
    'record_vars': 'record_variable_state',
    
    # Scene tools
    'highlight_path': 'highlight_vr_path',
    'dim_unrelated': 'dim_unrelated',
    'focus_cam': 'focus_camera',
    'open_panel': 'open_code_panel',
    'set_edge': 'set_edge_style',
    'show_diff': 'show_ghost_diff',
    'show_badges': 'show_test_badges',
    'show_approval': 'show_approval_prompt',
    
    # VR tools
    'get_vr_state': 'get_vr_session_state',
    'get_selected': 'get_selected_object',
    'process_voice': 'process_voice_command',
    'register_voice': 'register_voice_command',
    'list_voice': 'list_voice_commands',
    'set_hand_mode': 'set_hand_interaction_mode',
    'get_hand_state': 'get_hand_interaction_state',
    'set_audio': 'set_spatial_audio',
    'set_haptic': 'set_haptic_feedback',
    'set_env': 'set_vr_environment',
    
    # Security
    'scan_secrets': 'scan_secrets',
    'scan_vulns': 'scan_vulnerabilities',
    'check_quality': 'check_code_quality',
    'scan_dep_vulns': 'scan_dependency_vulnerabilities',
    'analyze_auth': 'analyze_authentication',
    'analyze_authz': 'analyze_authorization',
    'analyze_perms': 'analyze_permissions',
    'analyze_input': 'analyze_input_validation',
    
    # External integrations
    'github_repo': 'github_get_repository',
    'github_issues': 'github_get_issues',
    'github_prs': 'github_get_pull_requests',
    'github_commits': 'github_get_commits',
    'get_ci': 'get_ci_status',
    'trigger_ci': 'trigger_ci_build',
    'get_ci_logs': 'get_ci_logs',
    'cancel_ci': 'cancel_ci_build',
    'docker_list': 'docker_list_containers',
    'docker_logs': 'docker_get_container_logs',
    
    # Git history
    'find_commit': 'find_introducing_commit',
    'analyze_commit': 'analyze_commit_impact',
    'trace_history': 'trace_file_history',
    
    # Graph tools
    'search_graph': 'search_graph_symbols',
    'get_node': 'get_node',
    'get_callers': 'get_callers',
    'get_callees': 'get_callees',
    'get_dependents': 'get_dependents',
    
    # Exec tools
    'run_tests': 'run_tests',
    'run_typecheck': 'run_typecheck',
    'read_test_results': 'read_test_results',
    
    # Control
    'request_approval': 'request_approval',
    'exit_loop': 'exit_loop',
}

def fix_test_file(yaml_file):
    """Fix tool name in a test file"""
    try:
        with open(yaml_file) as f:
            test_def = yaml.safe_load(f)
        
        if not test_def:
            return False
        
        tool = test_def.get('tool')
        if not tool:
            return False
        
        # Check if tool needs mapping
        if tool in TOOL_NAME_MAP:
            test_def['tool'] = TOOL_NAME_MAP[tool]
            with open(yaml_file, 'w') as f:
                yaml.dump(test_def, f, default_flow_style=False)
            print(f"Fixed: {yaml_file.name} - {tool} -> {TOOL_NAME_MAP[tool]}")
            return True
    
    except Exception as e:
        print(f"Error processing {yaml_file}: {e}")
        return False

def main():
    fixed_count = 0
    for yaml_file in TESTS_ROOT.rglob('*.yaml'):
        if fix_test_file(yaml_file):
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} test files")

if __name__ == '__main__':
    main()
