"""
Agent Toolsets
Curated tool mappings for each of the JARVIS agents.
Each agent gets a focused set of MVP tools.

Uses string names for tools to avoid slow imports. Tools are resolved
when needed by calling get_toolset().
"""

from typing import List, Dict

# Permission ceilings for each agent
PERMISSION_CEILINGS = {
    "code_understanding": 'read',
    "conversational": 'read',
    "data_flow_intelligence": 'read',
    "orchestrator": 'read',
    "relationship_intelligence": 'read',
    "repository_intelligence": 'read',
    "software_engineering": 'write',
    "testing_verification": 'execute',
    "visualization_spatial": 'read',
}

# Tool permission levels - must contain every tool name in TOOLSETS
TOOL_LEVELS = {
    "add_graph_edge": "write",
    "add_graph_node": "write",
    "analyze_annotations": "read",
    "analyze_architecture_boundaries": "read",
    "analyze_build_configuration": "read",
    "analyze_code_complexity": "read",
    "analyze_control_flow": "read",
    "analyze_data_flow": "read",
    "analyze_dependencies": "read",
    "analyze_dependencies_manifest": "read",
    "analyze_environment_configuration": "read",
    "analyze_exceptions": "read",
    "analyze_framework_component_relationships": "read",
    "analyze_framework_configuration": "read",
    "analyze_framework_dependency_injection": "read",
    "analyze_framework_event_handling": "read",
    "analyze_framework_lifecycle": "read",
    "analyze_framework_orm_integration": "read",
    "analyze_framework_runtime_instrumentation": "read",
    "analyze_generated_code": "read",
    "analyze_language_specific_features": "read",
    "analyze_macros": "read",
    "analyze_monorepo": "read",
    "analyze_project_configuration": "read",
    "analyze_repository_structure": "read",
    "answer_code_question": "read",
    "apply_architecture_change": "write",
    "apply_patch": "write",
    "apply_patch_to_worktree": "write",
    "ask_clarifying_question": "read",
    "browse_vr_folder": "read",
    "build_call_graph": "read",
    "build_class_relationship_graph": "read",
    "build_data_flow_graph": "read",
    "build_dependency_graph": "read",
    "build_reference_graph": "read",
    "calculate_change_impact": "read",
    "calculate_graph_centrality": "read",
    "calculate_graph_clusters": "read",
    "calculate_graph_depth": "read",
    "calculate_graph_layout": "read",
    "cancel_agent_task": "read",
    "check_task_completion": "read",
    "classify_request": "read",
    "collapse_graph_node": "read",
    "commit_worktree": "write",
    "compare_before_after": "read",
    "compare_code_elements": "read",
    "compare_graphs": "read",
    "compare_implementations": "read",
    "create_directory": "write",
    "create_file": "write",
    "create_graph": "read",
    "create_investigation_plan": "read",
    "create_worktree": "write",
    "decompose_task": "read",
    "delegate_task": "read",
    "delete_file": "write",
    "detect_build_system": "read",
    "detect_code_duplication": "read",
    "detect_dead_code": "read",
    "detect_frameworks": "read",
    "detect_languages": "read",
    "detect_package_manager": "read",
    "detect_project_type": "read",
    "detect_repository_changes": "read",
    "detect_speaker_intent": "read",
    "detect_voice_activity": "read",
    "dim_unrelated": "read",
    "discover_framework_components": "read",
    "discover_framework_middleware": "read",
    "discover_framework_routes": "read",
    "discover_tests": "read",
    "edit_file": "write",
    "execute_command": "execute",
    "execute_script": "execute",
    "exit_loop": "read",
    "expand_graph_neighborhood": "read",
    "expand_graph_node": "read",
    "expand_relationships": "read",
    "explain_algorithm": "read",
    "explain_call_resolution": "read",
    "explain_class": "read",
    "explain_code_element": "read",
    "explain_condition": "read",
    "explain_expression": "read",
    "explain_function": "read",
    "explain_graph_edge": "read",
    "explain_module": "read",
    "explain_variable": "read",
    "explain_visualization": "read",
    "extract_ast": "read",
    "extract_function": "write",
    "extract_function_contract": "read",
    "extract_function_signature": "read",
    "extract_language_symbols": "read",
    "extract_symbols": "read",
    "find_all_paths_between_symbols": "read",
    "find_callees": "read",
    "find_callers": "read",
    "find_circular_dependencies": "read",
    "find_dependents": "read",
    "find_implementations": "read",
    "find_indirect_callers": "read",
    "find_interface_implementations": "read",
    "find_shared_dependencies": "read",
    "find_tests_for_node": "read",
    "focus_camera": "read",
    "focus_on_code_element": "read",
    "focus_on_graph_node": "read",
    "focus_on_object": "read",
    "format_code": "write",
    "generate_api": "write",
    "generate_class": "write",
    "generate_code_summary": "read",
    "generate_component": "write",
    "generate_database_model": "write",
    "generate_documentation": "write",
    "generate_edge_case_tests": "write",
    "generate_function": "write",
    "generate_integration_tests": "write",
    "generate_module": "write",
    "generate_test_report": "write",
    "generate_unit_tests": "write",
    "get_agent_status": "read",
    "get_branch_info": "read",
    "get_call_hierarchy": "read",
    "get_call_sites": "read",
    "get_callees": "read",
    "get_callers": "read",
    "get_changed_files": "read",
    "get_cluster": "read",
    "get_coverage": "read",
    "get_current_selection": "read",
    "get_current_spatial_context": "read",
    "get_dependents": "read",
    "get_diff": "read",
    "get_exports": "read",
    "get_file_metadata": "read",
    "get_findings": "read",
    "get_framework_adapter": "read",
    "get_imports": "read",
    "get_language_adapter": "read",
    "get_node": "read",
    "get_repository_metadata": "read",
    "get_scope_information": "read",
    "get_selected_node_details": "read",
    "get_source": "read",
    "get_spatial_object_details": "read",
    "get_spatial_selection_context": "read",
    "get_symbol_definition": "read",
    "get_symbol_documentation": "read",
    "get_symbol_hover_info": "read",
    "get_symbol_references": "read",
    "get_type_hierarchy": "read",
    "get_worktree_diff": "read",
    "git_blame": "read",
    "git_branch": "read",
    "git_commit": "write",
    "git_create_branch": "write",
    "git_create_checkpoint": "write",
    "git_diff": "read",
    "git_log": "read",
    "git_revert": "write",
    "git_show": "read",
    "git_stash": "write",
    "git_status": "read",
    "highlight_callers": "read",
    "highlight_dependencies": "read",
    "highlight_path": "read",
    "highlight_vr_path": "read",
    "identify_data_leaks": "read",
    "identify_data_sinks": "read",
    "identify_data_sources": "read",
    "identify_entry_points": "read",
    "identify_external_services": "read",
    "identify_generated_files": "read",
    "identify_hidden_assumptions": "read",
    "identify_side_effects": "read",
    "identify_untested_paths": "read",
    "identify_validation_gaps": "read",
    "implement_interface": "write",
    "incremental_index_repository": "read",
    "index_repository": "read",
    "infer_code_intent": "read",
    "inspect_command_output": "read",
    "inspect_environment": "read",
    "install_dependency": "execute",
    "interrupt_current_response": "write",
    "invoke_code_understanding": "read",
    "invoke_conversational": "read",
    "invoke_data_flow_intelligence": "read",
    "invoke_relationship_intelligence": "read",
    "invoke_repository_intelligence": "read",
    "invoke_software_engineering": "read",
    "invoke_testing_verification": "read",
    "invoke_visualization_spatial": "read",
    "isolate_relationship_path": "read",
    "isolate_subgraph": "read",
    "list_changed_nodes": "read",
    "list_files": "read",
    "list_repositories": "read",
    "list_supported_frameworks": "read",
    "list_supported_languages": "read",
    "list_vr_repositories": "read",
    "manage_conversation": "write",
    "manage_conversation_preferences": "read",
    "manage_environment_variables": "write",
    "manage_processes": "execute",
    "manage_task_priority": "write",
    "map_tests_to_functions": "read",
    "measure_branch_coverage": "read",
    "measure_test_coverage": "read",
    "merge_agent_results": "read",
    "move_cluster": "read",
    "move_file": "write",
    "move_graph": "read",
    "move_panel": "read",
    "navigate_to_code_element": "read",
    "navigate_to_relationship": "read",
    "open_code_panel": "read",
    "open_repository": "read",
    "open_vr_file": "read",
    "open_vr_repository": "read",
    "organize_imports": "write",
    "parse_function": "read",
    "parse_language_ast": "read",
    "parse_source_code": "read",
    "query_graph_path": "read",
    "read_file": "read",
    "read_file_range": "read",
    "read_test_results": "read",
    "recenter_workspace": "read",
    "record_evidence": "write",
    "record_finding": "read",
    "refactor_function": "write",
    "register_framework_adapter": "write",
    "register_language_adapter": "write",
    "remove_dependency": "execute",
    "remove_graph_edge": "write",
    "remove_graph_node": "write",
    "rename_file": "write",
    "rename_symbol": "write",
    "request_approval": "read",
    "request_more_evidence": "read",
    "request_user_approval": "read",
    "reset_layout": "read",
    "resolve_conflicting_findings": "read",
    "resolve_dependency_versions": "read",
    "resolve_language_types": "read",
    "resolve_references": "read",
    "resolve_types": "read",
    "retrieve_conversation_context": "read",
    "retrieve_investigation_context": "read",
    "retry_agent_task": "read",
    "run_agents_parallel": "read",
    "run_agents_sequentially": "read",
    "run_build": "execute",
    "run_compiler": "execute",
    "run_end_to_end_tests": "execute",
    "run_formatter": "execute",
    "run_fuzz_tests": "execute",
    "run_integration_tests": "execute",
    "run_linter": "execute",
    "run_property_tests": "execute",
    "run_regression_tests": "execute",
    "run_tests": "execute",
    "run_type_checker": "execute",
    "run_typecheck": "execute",
    "run_unit_tests": "execute",
    "safe": "read",
    "scale_panel": "read",
    "search_and_replace": "write",
    "search_code": "read",
    "search_files": "read",
    "search_graph": "read",
    "search_graph_symbols": "read",
    "select_agents": "read",
    "select_code_element": "read",
    "set_cluster_collapsed": "read",
    "set_edge_style": "read",
    "set_mode": "read",
    "set_panel_state": "read",
    "show_approval_prompt": "read",
    "show_ghost_diff": "read",
    "show_test_badges": "read",
    "speech_to_text": "execute",
    "stream_voice_response": "execute",
    "summarize_graph": "read",
    "summarize_investigation": "read",
    "text_to_speech": "execute",
    "trace_api_data_flow": "read",
    "trace_call_chain": "read",
    "trace_cross_function_flow": "read",
    "trace_cross_module_relationships": "read",
    "trace_cross_service_flow": "read",
    "trace_cross_service_relationships": "read",
    "trace_database_reads": "read",
    "trace_database_writes": "read",
    "trace_file_operations": "read",
    "trace_function_logic": "read",
    "trace_parameter_flow": "read",
    "trace_path": "read",
    "trace_relationship_path": "read",
    "trace_return_value_flow": "read",
    "trace_state_changes": "read",
    "trace_taint_flow": "read",
    "trace_transformations": "read",
    "trace_variable_modifications": "read",
    "trace_variable_origin": "read",
    "trace_variable_usage": "read",
    "understand_user_intent": "read",
    "update_references": "write",
    "verify_citations": "read",
    "verify_compilation": "read",
    "verify_finding": "read",
    "verify_lint": "read",
    "verify_types": "read",
    "visualize_architecture": "read",
    "visualize_call_graph": "read",
    "visualize_change_impact": "read",
    "visualize_control_flow": "read",
    "visualize_data_flow": "read",
    "visualize_dependency_graph": "read",
    "visualize_test_coverage": "read",
    "visualize_unified_graph": "read",
    "wait_for_agent": "read",
    "watch_repository": "read",
    "zoom_graph": "read",
}

# Curated toolsets for each agent (using string names)
TOOLSETS: Dict[str, List[str]] = {
    "orchestrator": ['classify_request', 'understand_user_intent', 'create_investigation_plan', 'check_task_completion', 'merge_agent_results', 'resolve_conflicting_findings', 'invoke_repository_intelligence', 'invoke_code_understanding', 'invoke_relationship_intelligence', 'invoke_data_flow_intelligence', 'invoke_software_engineering', 'invoke_testing_verification', 'invoke_visualization_spatial', 'invoke_conversational', 'request_more_evidence', 'request_approval'],
    "conversational": ['answer_code_question', 'explain_visualization', 'summarize_investigation', 'retrieve_conversation_context', 'retrieve_investigation_context', 'ask_clarifying_question', 'compare_code_elements', 'manage_conversation_preferences'],
    "repository_intelligence": ['index_repository', 'incremental_index_repository', 'detect_languages', 'detect_frameworks', 'detect_build_system', 'detect_project_type', 'detect_package_manager', 'analyze_repository_structure', 'analyze_monorepo', 'identify_entry_points', 'identify_external_services', 'identify_generated_files', 'detect_repository_changes', 'analyze_dependencies_manifest', 'list_files', 'read_file', 'search_code', 'get_repository_metadata', 'get_changed_files'],
    "code_understanding": ['get_symbol_definition', 'get_symbol_references', 'get_symbol_hover_info', 'get_type_hierarchy', 'get_imports', 'get_exports', 'get_scope_information', 'parse_source_code', 'extract_symbols', 'resolve_types', 'explain_function', 'explain_class', 'explain_module', 'explain_condition', 'extract_function_contract', 'identify_side_effects', 'identify_hidden_assumptions', 'infer_code_intent', 'trace_function_logic', 'analyze_control_flow', 'read_file_range', 'record_finding', 'get_findings'],
    "relationship_intelligence": ['find_callers', 'find_callees', 'find_indirect_callers', 'trace_call_chain', 'get_call_sites', 'explain_call_resolution', 'build_call_graph', 'build_dependency_graph', 'find_dependents', 'find_all_paths_between_symbols', 'find_circular_dependencies', 'analyze_architecture_boundaries', 'calculate_change_impact', 'find_interface_implementations', 'trace_cross_module_relationships', 'trace_cross_service_relationships'],
    "data_flow_intelligence": ['trace_variable_origin', 'trace_variable_usage', 'trace_variable_modifications', 'trace_parameter_flow', 'trace_return_value_flow', 'trace_taint_flow', 'trace_transformations', 'trace_cross_function_flow', 'trace_cross_service_flow', 'trace_database_reads', 'trace_database_writes', 'trace_api_data_flow', 'trace_file_operations', 'trace_state_changes', 'build_data_flow_graph', 'identify_data_leaks', 'identify_data_sinks', 'identify_data_sources', 'identify_validation_gaps'],
    "software_engineering": ['create_worktree', 'apply_patch_to_worktree', 'get_worktree_diff', 'edit_file', 'apply_patch', 'search_and_replace', 'rename_symbol', 'extract_function', 'organize_imports', 'generate_function', 'generate_class', 'format_code', 'git_diff', 'read_file', 'search_code'],
    "testing_verification": ['discover_tests', 'map_tests_to_functions', 'identify_untested_paths', 'run_unit_tests', 'run_regression_tests', 'measure_test_coverage', 'verify_compilation', 'verify_lint', 'verify_types', 'compare_before_after', 'run_tests', 'run_typecheck', 'read_test_results'],
    "visualization_spatial": ['highlight_vr_path', 'dim_unrelated', 'focus_camera', 'open_code_panel', 'list_vr_repositories', 'open_vr_repository', 'browse_vr_folder', 'open_vr_file', 'move_cluster', 'move_graph', 'zoom_graph', 'move_panel', 'scale_panel', 'set_panel_state', 'set_cluster_collapsed', 'highlight_callers', 'recenter_workspace', 'reset_layout', 'set_mode', 'set_edge_style', 'show_ghost_diff', 'show_test_badges', 'create_graph', 'visualize_call_graph', 'visualize_change_impact', 'visualize_data_flow', 'visualize_test_coverage', 'visualize_architecture', 'visualize_dependency_graph', 'visualize_control_flow', 'visualize_unified_graph', 'explain_graph_edge', 'query_graph_path', 'expand_graph_neighborhood', 'expand_graph_node', 'collapse_graph_node', 'isolate_subgraph', 'calculate_graph_clusters', 'summarize_graph', 'get_current_selection', 'verify_citations', 'focus_on_graph_node', 'navigate_to_code_element', 'navigate_to_relationship', 'get_selected_node_details', 'get_current_spatial_context', 'focus_on_code_element'],
}

def get_toolset(agent_name: str) -> List:
    """
    Get the toolset for an agent, resolving string names to actual tool callables.
    """
    from .. import tools as tools_module

    tool_names = TOOLSETS.get(agent_name, [])
    tool_callables = []

    for tool_name in tool_names:
        if hasattr(tools_module, tool_name):
            tool_callables.append(getattr(tools_module, tool_name))
        else:
            raise ValueError(f"Tool not found: {tool_name}")

    return tool_callables


def validate_toolsets():
    """
    Validate that all tools in toolsets exist and have permission levels.
    Raises ValueError if validation fails.
    Call this explicitly during testing or startup, not on import.
    """
    # Get all available tools from the tools module
    from .. import tools as tools_module
    import inspect

    available_tools = set(
        name for name, obj in inspect.getmembers(tools_module)
        if callable(obj) and not name.startswith('_')
    )

    errors = []

    # Check that every tool in TOOLSETS has a level in TOOL_LEVELS
    all_tool_names = set()
    for agent_name, tool_list in TOOLSETS.items():
        # Check for duplicates within agent
        tool_names = [tool if isinstance(tool, str) else (tool.__name__ if hasattr(tool, '__name__') else str(tool)) for tool in tool_list]
        if len(tool_names) != len(set(tool_names)):
            duplicates = [name for name in tool_names if tool_names.count(name) > 1]
            errors.append(f"{agent_name}: Duplicate tools: {set(duplicates)}")

        # Check all tools exist and have permission levels
        for tool in tool_list:
            tool_name = tool if isinstance(tool, str) else (tool.__name__ if hasattr(tool, '__name__') else str(tool))
            all_tool_names.add(tool_name)
            
            if tool_name not in available_tools:
                errors.append(f"{agent_name}: Tool not found: {tool_name}")
            
            if tool_name not in TOOL_LEVELS:
                errors.append(f"{agent_name}: Tool {tool_name} missing from TOOL_LEVELS")

    # Check permission ceilings
    for agent_name, tool_list in TOOLSETS.items():
        permission_ceiling = PERMISSION_CEILINGS.get(agent_name, "read")
        for tool in tool_list:
            tool_name = tool if isinstance(tool, str) else (tool.__name__ if hasattr(tool, '__name__') else str(tool))
            tool_perm = TOOL_LEVELS.get(tool_name, "read")

            # Check if tool exceeds ceiling
            perm_order = {"read": 0, "execute": 1, "write": 2}
            if perm_order.get(tool_perm, 0) > perm_order.get(permission_ceiling, 0):
                errors.append(
                    f"{agent_name}: Tool {tool_name} requires {tool_perm} permission, "
                    f"but agent has {permission_ceiling} ceiling"
                )

    if errors:
        error_msg = "Toolset validation failed:\n" + "\n".join(errors)
        raise ValueError(error_msg)

    print(f"Toolset validation passed: {len(all_tool_names)} tools have permission levels")
    return True
