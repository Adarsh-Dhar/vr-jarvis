"""
Agent Toolsets
Curated tool mappings for each of the 12 JARVIS agents.
Each agent gets 8-22 tools (176 unique tools total).

Uses string names for tools to avoid slow imports. Tools are resolved
when needed by calling get_toolset().
"""

from typing import List, Dict

# Permission ceilings for each agent
PERMISSION_CEILINGS = {
    "orchestrator": "read",
    "conversational": "read",
    "repository_intelligence": "read",
    "code_understanding": "read",
    "relationship_intelligence": "read",
    "data_flow_intelligence": "read",
    "runtime_intelligence": "execute",  # sandbox only
    "debugging_intelligence": "execute",  # sandbox only
    "security_quality": "read",
    "software_engineering": "write",  # worktree only
    "testing_verification": "execute",  # sandbox only
    "visualization_spatial": "read",
}

# Tool permission levels - must contain every tool name in TOOLSETS
# This is generated from the toolsets to ensure completeness
TOOL_LEVELS = {
    # Write tools
    "edit_file": "write",
    "apply_patch": "write",
    "create_file": "write",
    "delete_file": "write",
    "git_commit": "write",
    "commit_changes": "write",
    "merge_branch": "write",
    "search_and_replace": "write",
    "rename_symbol": "write",
    "extract_function": "write",
    "organize_imports": "write",
    "generate_function": "write",
    "generate_class": "write",
    "format_code": "write",
    "apply_patch_to_worktree": "write",
    "create_worktree": "write",
    "rename_file": "write",
    "move_file": "write",
    "create_directory": "write",
    # Execute tools
    "start_application": "execute",
    "stop_application": "execute",
    "run_tests": "execute",
    "run_typecheck": "execute",
    "run_unit_tests": "execute",
    "run_regression_tests": "execute",
    "execute_command": "execute",
    "execute_script": "execute",
    "install_dependency": "execute",
    "remove_dependency": "execute",
    "run_compiler": "execute",
    "run_build": "execute",
    "run_linter": "execute",
    "attach_runtime_profiler": "execute",
    "attach_debugger": "execute",
    "set_breakpoint": "execute",
    "remove_breakpoint": "execute",
    "step_into": "execute",
    "step_over": "execute",
    "step_out": "execute",
    "reproduce_bug": "execute",
    # Read tools (most tools) - listed explicitly for validation
    "analyze_architecture_boundaries": "read",
    "analyze_attack_surface": "read",
    "analyze_authentication": "read",
    "analyze_authorization": "read",
    "analyze_control_flow": "read",
    "analyze_cryptography": "read",
    "analyze_dependencies_manifest": "read",
    "analyze_injection_risks": "read",
    "analyze_input_validation": "read",
    "analyze_maintainability": "read",
    "analyze_monorepo": "read",
    "analyze_permissions": "read",
    "analyze_repository_structure": "read",
    "analyze_stack_trace": "read",
    "answer_code_question": "read",
    "ask_clarifying_question": "read",
    "build_call_graph": "read",
    "build_data_flow_graph": "read",
    "build_dependency_graph": "read",
    "calculate_change_impact": "read",
    "calculate_cognitive_complexity": "read",
    "calculate_complexity": "read",
    "calculate_graph_clusters": "read",
    "capture_application_logs": "read",
    "capture_exception": "read",
    "capture_runtime_events": "read",
    "check_task_completion": "read",
    "classify_request": "read",
    "collapse_graph_node": "read",
    "collect_execution_trace": "read",
    "compare_before_after": "read",
    "compare_code_elements": "read",
    "compare_execution_traces": "read",
    "compare_success_failure": "read",
    "create_graph": "read",
    "create_investigation_plan": "read",
    "detect_anti_patterns": "read",
    "detect_build_system": "read",
    "detect_code_smells": "read",
    "detect_duplicates": "read",
    "detect_frameworks": "read",
    "detect_languages": "read",
    "detect_package_manager": "read",
    "detect_project_type": "read",
    "detect_repository_changes": "read",
    "dim_unrelated": "read",
    "discover_api_endpoints": "read",
    "discover_tests": "read",
    "evaluate_debug_expression": "read",
    "expand_graph_node": "read",
    "explain_class": "read",
    "explain_condition": "read",
    "explain_function": "read",
    "explain_module": "read",
    "explain_visualization": "read",
    "extract_docstrings": "read",
    "extract_function_contract": "read",
    "extract_symbols": "read",
    "filter_graph": "read",
    "find_all_paths_between_symbols": "read",
    "find_callees": "read",
    "find_callers": "read",
    "find_circular_dependencies": "read",
    "find_dependents": "read",
    "find_error_origin": "read",
    "find_indirect_callers": "read",
    "find_interface_implementations": "read",
    "focus_camera": "read",
    "generate_quality_report": "read",
    "generate_security_report": "read",
    "get_changed_files": "read",
    "get_current_selection": "read",
    "get_exports": "read",
    "get_imports": "read",
    "get_repository_metadata": "read",
    "get_scope_information": "read",
    "get_symbol_definition": "read",
    "get_symbol_hover_info": "read",
    "get_symbol_references": "read",
    "get_type_hierarchy": "read",
    "get_worktree_diff": "read",
    "git_diff": "read",
    "highlight_vr_path": "read",
    "identify_data_leaks": "read",
    "identify_data_sinks": "read",
    "identify_data_sources": "read",
    "identify_entry_points": "read",
    "identify_external_services": "read",
    "identify_failure_path": "read",
    "identify_generated_files": "read",
    "identify_hidden_assumptions": "read",
    "identify_root_cause": "read",
    "identify_side_effects": "read",
    "identify_technical_debt": "read",
    "identify_untested_paths": "read",
    "identify_validation_gaps": "read",
    "incremental_index_repository": "read",
    "index_repository": "read",
    "infer_code_intent": "read",
    "inspect_call_stack": "read",
    "inspect_variables": "read",
    "isolate_subgraph": "read",
    "list_files": "read",
    "manage_conversation_preferences": "read",
    "map_api_to_database": "read",
    "map_tests_to_functions": "read",
    "measure_test_coverage": "read",
    "merge_agent_results": "read",
    "open_code_panel": "read",
    "parse_source_code": "read",
    "read_file": "read",
    "read_file_range": "read",
    "read_test_results": "read",
    "record_async_tasks": "read",
    "record_cpu_usage": "read",
    "record_database_activity": "read",
    "record_execution_timing": "read",
    "record_function_arguments": "read",
    "record_function_calls": "read",
    "record_function_returns": "read",
    "record_memory_usage": "read",
    "record_network_activity": "read",
    "record_thread_activity": "read",
    "record_variable_state": "read",
    "replay_execution_trace": "read",
    "request_approval": "read",
    "request_more_evidence": "read",
    "resolve_conflicting_findings": "read",
    "resolve_types": "read",
    "retrieve_conversation_context": "read",
    "retrieve_investigation_context": "read",
    "scan_dependency_vulnerabilities": "read",
    "scan_secrets": "read",
    "scan_security_vulnerabilities": "read",
    "scan_vulnerabilities": "read",
    "search_code": "read",
    "set_edge_style": "read",
    "show_ghost_diff": "read",
    "show_test_badges": "read",
    "suggest_debugging_actions": "read",
    "summarize_graph": "read",
    "summarize_investigation": "read",
    "trace_api_data_flow": "read",
    "trace_call_chain": "read",
    "trace_cross_function_flow": "read",
    "trace_cross_module_relationships": "read",
    "trace_cross_service_flow": "read",
    "trace_cross_service_relationships": "read",
    "trace_database_reads": "read",
    "trace_database_writes": "read",
    "trace_error_propagation": "read",
    "trace_file_operations": "read",
    "trace_function_logic": "read",
    "trace_parameter_flow": "read",
    "trace_request_lifecycle": "read",
    "trace_return_value_flow": "read",
    "trace_sensitive_data": "read",
    "trace_state_changes": "read",
    "trace_taint_flow": "read",
    "trace_transformations": "read",
    "trace_variable_modifications": "read",
    "trace_variable_origin": "read",
    "trace_variable_usage": "read",
    "understand_user_intent": "read",
    "verify_citations": "read",
    "verify_compilation": "read",
    "verify_lint": "read",
    "verify_security": "read",
    "verify_types": "read",
    "visualize_call_graph": "read",
    "visualize_change_impact": "read",
    "visualize_data_flow": "read",
    "visualize_test_coverage": "read",
    "watch_expression": "read",
}

# Curated toolsets for each agent (using string names)
TOOLSETS: Dict[str, List[str]] = {
    # Agent 1: Orchestrator
    "orchestrator": [
        "classify_request",
        "understand_user_intent",
        "create_investigation_plan",
        "check_task_completion",
        "merge_agent_results",
        "resolve_conflicting_findings",
        "request_more_evidence",
        "request_approval",
        # Other specialists will be added as AgentTool instances
    ],

    # Agent 2: Conversational JARVIS
    "conversational": [
        "answer_code_question",
        "explain_visualization",
        "summarize_investigation",
        "retrieve_conversation_context",
        "retrieve_investigation_context",
        "ask_clarifying_question",
        "compare_code_elements",
        "manage_conversation_preferences",
    ],

    # Agent 3: Repository Intelligence
    "repository_intelligence": [
        "index_repository",
        "incremental_index_repository",
        "detect_languages",
        "detect_frameworks",
        "detect_build_system",
        "detect_project_type",
        "detect_package_manager",
        "analyze_repository_structure",
        "analyze_monorepo",
        "identify_entry_points",
        "identify_external_services",
        "identify_generated_files",
        "detect_repository_changes",
        "analyze_dependencies_manifest",
        "list_files",
        "read_file",
        "search_code",
        "get_repository_metadata",
        "get_changed_files",
    ],

    # Agent 4: Code Understanding
    "code_understanding": [
        "get_symbol_definition",
        "get_symbol_references",
        "get_symbol_hover_info",
        "get_type_hierarchy",
        "get_imports",
        "get_exports",
        "get_scope_information",
        "parse_source_code",
        "extract_symbols",
        "resolve_types",
        "explain_function",
        "explain_class",
        "explain_module",
        "explain_condition",
        "extract_function_contract",
        "identify_side_effects",
        "identify_hidden_assumptions",
        "infer_code_intent",
        "trace_function_logic",
        "analyze_control_flow",
        "extract_docstrings",
        "read_file_range",
    ],

    # Agent 5: Relationship Intelligence
    "relationship_intelligence": [
        "find_callers",
        "find_callees",
        "find_indirect_callers",
        "trace_call_chain",
        "build_call_graph",
        "build_dependency_graph",
        "find_dependents",
        "find_all_paths_between_symbols",
        "find_circular_dependencies",
        "analyze_architecture_boundaries",
        "calculate_change_impact",
        "find_interface_implementations",
        "trace_cross_module_relationships",
        "trace_cross_service_relationships",
        "discover_api_endpoints",
        "map_api_to_database",
        "trace_request_lifecycle",
    ],

    # Agent 6: Data Flow Intelligence
    "data_flow_intelligence": [
        "trace_variable_origin",
        "trace_variable_usage",
        "trace_variable_modifications",
        "trace_parameter_flow",
        "trace_return_value_flow",
        "trace_taint_flow",
        "trace_transformations",
        "trace_cross_function_flow",
        "trace_cross_service_flow",
        "trace_database_reads",
        "trace_database_writes",
        "trace_api_data_flow",
        "trace_file_operations",
        "trace_state_changes",
        "build_data_flow_graph",
        "identify_data_leaks",
        "identify_data_sinks",
        "identify_data_sources",
        "identify_validation_gaps",
    ],

    # Agent 7: Runtime Intelligence
    "runtime_intelligence": [
        "start_application",
        "stop_application",
        "attach_runtime_profiler",
        "attach_debugger",
        "collect_execution_trace",
        "record_function_calls",
        "record_function_arguments",
        "record_function_returns",
        "record_execution_timing",
        "record_variable_state",
        "record_memory_usage",
        "record_cpu_usage",
        "record_network_activity",
        "record_database_activity",
        "record_async_tasks",
        "record_thread_activity",
        "capture_application_logs",
        "capture_runtime_events",
        "compare_execution_traces",
        "replay_execution_trace",
    ],

    # Agent 8: Debugging Intelligence
    "debugging_intelligence": [
        "capture_exception",
        "analyze_stack_trace",
        "find_error_origin",
        "trace_error_propagation",
        "identify_failure_path",
        "set_breakpoint",
        "remove_breakpoint",
        "step_into",
        "step_over",
        "step_out",
        "inspect_variables",
        "evaluate_debug_expression",
        "inspect_call_stack",
        "watch_expression",
        "reproduce_bug",
        "compare_success_failure",
        "identify_root_cause",
        "suggest_debugging_actions",
    ],

    # Agent 9: Security and Quality
    "security_quality": [
        "scan_secrets",
        "scan_vulnerabilities",
        "scan_security_vulnerabilities",
        "scan_dependency_vulnerabilities",
        "analyze_authentication",
        "analyze_authorization",
        "analyze_permissions",
        "analyze_input_validation",
        "analyze_injection_risks",
        "analyze_cryptography",
        "trace_sensitive_data",
        "analyze_attack_surface",
        "calculate_complexity",
        "calculate_cognitive_complexity",
        "detect_code_smells",
        "detect_duplicates",
        "detect_anti_patterns",
        "analyze_maintainability",
        "identify_technical_debt",
        "generate_security_report",
        "generate_quality_report",
    ],

    # Agent 10: Software Engineering
    "software_engineering": [
        "create_worktree",
        "apply_patch_to_worktree",
        "get_worktree_diff",
        "edit_file",
        "apply_patch",
        "search_and_replace",
        "rename_symbol",
        "extract_function",
        "organize_imports",
        "generate_function",
        "generate_class",
        "format_code",
        "git_diff",
        "read_file",
        "search_code",
    ],

    # Agent 11: Testing and Verification
    "testing_verification": [
        "discover_tests",
        "map_tests_to_functions",
        "identify_untested_paths",
        "run_unit_tests",
        "run_regression_tests",
        "measure_test_coverage",
        "verify_compilation",
        "verify_lint",
        "verify_types",
        "verify_security",
        "compare_before_after",
        "run_tests",
        "run_typecheck",
        "read_test_results",
    ],

    # Agent 12: Visualization and Spatial Intelligence
    "visualization_spatial": [
        "highlight_vr_path",
        "dim_unrelated",
        "focus_camera",
        "open_code_panel",
        "set_edge_style",
        "show_ghost_diff",
        "show_test_badges",
        "create_graph",
        "visualize_call_graph",
        "visualize_change_impact",
        "visualize_data_flow",
        "visualize_test_coverage",
        "expand_graph_node",
        "collapse_graph_node",
        "isolate_subgraph",
        "filter_graph",
        "calculate_graph_clusters",
        "summarize_graph",
        "get_current_selection",
        "verify_citations",
    ],
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
