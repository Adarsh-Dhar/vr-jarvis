#!/usr/bin/env python3
"""
Generate Layer 1-2 tests for Priority 3 and 4 tools
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from test_spec_generator import TestSpecGenerator

# Priority 3 tools (106 tools)
PRIORITY_3_TOOLS = [
    # Infrastructure Services (50)
    'check_permission', 'grant_permission', 'revoke_permission', 'list_permissions',
    'set_permission_level', 'request_sensitive_approval', 'check_approval_status',
    'register_tool', 'unregister_tool', 'get_tool_definition', 'list_tools',
    'discover_tools', 'update_tool_definition', 'store_graph_node', 'store_graph_edge',
    'get_graph_node', 'query_graph', 'delete_graph_node', 'delete_graph_edge',
    'clear_graph', 'start_indexing', 'get_index_status', 'update_index',
    'start_agent', 'stop_agent', 'list_agents', 'get_agent_state',
    'send_message_to_agent', 'get_agent_messages', 'publish_message',
    'subscribe_to_topic', 'unsubscribe_from_topic', 'create_workflow',
    'execute_workflow', 'get_workflow_status', 'store_memory', 'retrieve_memory',
    'delete_memory', 'start_telemetry_collection', 'get_telemetry_data',
    'stop_telemetry_collection', 'create_sandbox', 'execute_in_sandbox',
    'destroy_sandbox', 'record_evidence', 'get_evidence', 'verify_evidence',
    'render_graph', 'get_rendering_state', 'update_rendering',

    # External Integrations Toolkit (36)
    'github_get_repository', 'github_get_issues', 'github_get_pull_requests',
    'github_get_commits', 'get_ci_status', 'trigger_ci_build', 'get_ci_logs',
    'cancel_ci_build', 'docker_list_containers', 'docker_get_container_logs',
    'docker_inspect_container', 'docker_exec_command', 'kubernetes_list_pods',
    'kubernetes_get_pod_logs', 'kubernetes_describe_pod', 'kubernetes_exec_command',
    'kubernetes_get_deployments', 'cloud_list_instances', 'cloud_get_instance_logs',
    'cloud_execute_command', 'cloud_describe_instance', 'monitoring_get_metrics',
    'monitoring_query_metrics', 'monitoring_create_alert', 'error_tracking_get_errors',
    'error_tracking_get_error_details', 'error_tracking_resolve_error',
    'database_query', 'database_execute', 'database_get_schema',
    'create_issue', 'get_issue', 'update_issue', 'list_issues',
    'package_search', 'package_get_version',

    # Language Adapters (20)
    'register_language_adapter', 'get_language_adapter', 'list_supported_languages',
    'parse_language_ast', 'resolve_language_types', 'extract_language_symbols',
    'analyze_language_specific_features', 'register_framework_adapter',
    'get_framework_adapter', 'list_supported_frameworks', 'discover_framework_routes',
    'analyze_framework_lifecycle', 'discover_framework_components',
    'analyze_framework_dependency_injection', 'discover_framework_middleware',
    'analyze_framework_event_handling', 'analyze_framework_component_relationships',
    'analyze_framework_orm_integration', 'analyze_framework_configuration',
    'analyze_framework_runtime_instrumentation',
]

# Priority 4 tools (227 tools) - selecting a representative subset for initial testing
PRIORITY_4_TOOLS = [
    # Software Engineering Tools (20 selected from 45)
    'create_file', 'delete_file', 'rename_file', 'move_file', 'create_directory',
    'search_and_replace', 'format_code', 'organize_imports', 'execute_command',
    'execute_script', 'install_dependency', 'remove_dependency', 'run_compiler',
    'run_build', 'run_linter', 'run_formatter', 'run_type_checker',
    'git_status', 'git_diff', 'git_log',

    # Testing Verification Tools (10 selected from 18)
    'discover_tests', 'run_unit_tests', 'run_integration_tests', 'run_end_to_end_tests',
    'run_regression_tests', 'generate_unit_tests', 'measure_test_coverage',
    'verify_compilation', 'verify_types', 'verify_lint',

    # Visualization Spatial Tools (10 selected from 50)
    'add_graph_node', 'remove_graph_node', 'add_graph_edge', 'remove_graph_edge',
    'filter_graph', 'search_graph', 'highlight_path', 'visualize_call_graph',
    'visualize_dependency_graph', 'visualize_data_flow',

    # VR Specific Tools (10 selected from 20)
    'get_vr_session_state', 'get_selected_object', 'process_voice_command',
    'register_voice_command', 'list_voice_commands', 'set_hand_interaction_mode',
    'get_hand_interaction_state', 'set_spatial_audio', 'set_haptic_feedback',
    'set_vr_environment',

    # Conversational Tools (8 selected from 16)
    'speech_to_text', 'text_to_speech', 'stream_voice_response', 'detect_speaker_intent',
    'detect_voice_activity', 'manage_conversation', 'retrieve_conversation_context',
    'answer_code_question',

    # Runtime Intelligence Tools (8 selected from 15)
    'start_application', 'stop_application', 'attach_runtime_profiler',
    'attach_debugger', 'record_function_calls', 'record_function_arguments',
    'record_function_returns', 'record_variable_state',

    # Debugging Intelligence Tools (8 selected from 15)
    'capture_exception', 'trace_error_propagation', 'identify_failure_path',
    'set_breakpoint', 'remove_breakpoint', 'step_into', 'step_over',
    'inspect_variables',

    # Security Quality Tools (10 selected from 25)
    'scan_dependency_vulnerabilities', 'check_code_quality', 'scan_security_vulnerabilities',
    'analyze_authentication', 'analyze_authorization', 'analyze_permissions',
    'analyze_injection_risks', 'trace_sensitive_data', 'analyze_attack_surface',
    'generate_security_report',

    # Navigation Tools (10 selected from 10 - all)
    'get_symbol_definition', 'get_symbol_references', 'get_symbol_hover_info',
    'get_call_hierarchy', 'get_type_hierarchy', 'get_imports', 'get_exports',
    'get_scope_information', 'get_symbol_documentation', 'find_implementations',

    # Memory Tools (3 - all)
    'load_project_memory', 'save_finding', 'record_decision',

    # Exec Tools (3 - all)
    'run_tests', 'run_typecheck', 'read_test_results',

    # Control Tools (2 - all)
    'request_approval', 'exit_loop',

    # Scene Tools (8 - all)
    'highlight_vr_path', 'dim_unrelated', 'focus_camera', 'open_code_panel',
    'set_edge_style', 'show_ghost_diff', 'show_test_badges', 'show_approval_prompt',

    # Orchestrator Tools (9 - all)
    'understand_user_intent', 'classify_request', 'run_agents_sequentially',
    'wait_for_agent', 'get_agent_status', 'request_more_evidence',
    'check_task_completion', 'request_user_approval', 'manage_task_priority',
]

def generate_tests_for_tools(tool_list, generator, test_root, priority_name):
    """Generate tests for a list of tools"""
    test_types_layer1 = [f'T0{i}' for i in range(1, 10)]
    test_types_layer2 = [f'T1{i}' for i in range(0, 6)]

    total_specs = 0
    failed_tools = []

    print(f"\nGenerating Layer 1 tests (T01-T09) for {priority_name}...")
    for tool_name in tool_list:
        print(f"  {tool_name}...")

        try:
            specs = generator.generate_for_tool(tool_name, test_types_layer1)
            saved = generator.save_specs(specs, test_root / 'tests')
            total_specs += len(saved)
        except Exception as e:
            print(f"    ERROR: {e}")
            failed_tools.append(tool_name)

    print(f"Layer 1 specs generated: {total_specs}")

    total_specs_layer2 = 0

    print(f"\nGenerating Layer 2 tests (T10-T15) for {priority_name}...")
    for tool_name in tool_list:
        print(f"  {tool_name}...")

        try:
            specs = generator.generate_for_tool(tool_name, test_types_layer2)
            saved = generator.save_specs(specs, test_root / 'tests')
            total_specs_layer2 += len(saved)
        except Exception as e:
            print(f"    ERROR: {e}")
            if tool_name not in failed_tools:
                failed_tools.append(tool_name)

    print(f"Layer 2 specs generated: {total_specs_layer2}")

    return total_specs + total_specs_layer2, failed_tools

def main():
    test_root = Path(__file__).parent.parent
    generator = TestSpecGenerator(test_root)
    generator.load_all_tool_signatures()

    total_specs = 0
    all_failed_tools = []

    # Generate for Priority 3
    specs_p3, failed_p3 = generate_tests_for_tools(PRIORITY_3_TOOLS, generator, test_root, "Priority 3")
    total_specs += specs_p3
    all_failed_tools.extend(failed_p3)

    # Generate for Priority 4
    specs_p4, failed_p4 = generate_tests_for_tools(PRIORITY_4_TOOLS, generator, test_root, "Priority 4")
    total_specs += specs_p4
    all_failed_tools.extend(failed_p4)

    print(f"\n{'='*60}")
    print(f"Total specs generated: {total_specs}")
    print(f"Failed tools: {len(all_failed_tools)}")

    if all_failed_tools:
        print("\nFailed tools:")
        for tool in all_failed_tools:
            print(f"  - {tool}")

    print(f"\nOutput directory: {test_root / 'tests'}")


if __name__ == '__main__':
    main()
