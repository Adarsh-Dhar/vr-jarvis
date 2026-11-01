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

# Tool permission levels
TOOL_PERMISSIONS = {
    # Read tools (most tools)
    "read": [
        # Repository and navigation
        "list_files", "read_file", "read_file_range", "search_files", "search_code",
        "get_symbol_definition", "get_symbol_references", "get_symbol_hover_info",
        # Analysis
        "parse_source_code", "extract_symbols", "resolve_types",
        # Most other tools...
    ],
    # Execute tools (run things, but only in sandbox)
    "execute": [
        "start_application", "stop_application", "collect_execution_trace",
        "run_tests", "run_typecheck", "run_unit_tests", "run_regression_tests",
        # Runtime and debugging tools
    ],
    # Write tools (modify files, only in worktree)
    "write": [
        "edit_file", "apply_patch", "create_file", "delete_file",
        "git_commit", "commit_changes", "merge_branch",
    ],
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
    Validate that all tools in toolsets exist and are within permission ceilings.
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

    for agent_name, tool_list in TOOLSETS.items():
        # Check for duplicates within agent
        tool_names = [tool.__name__ if hasattr(tool, '__name__') else str(tool) for tool in tool_list]
        if len(tool_names) != len(set(tool_names)):
            duplicates = [name for name in tool_names if tool_names.count(name) > 1]
            errors.append(f"{agent_name}: Duplicate tools: {set(duplicates)}")

        # Check all tools exist
        for tool in tool_list:
            tool_name = tool.__name__ if hasattr(tool, '__name__') else str(tool)
            if tool_name not in available_tools:
                errors.append(f"{agent_name}: Tool not found: {tool_name}")

        # Check permission ceiling
        permission_ceiling = PERMISSION_CEILINGS.get(agent_name, "read")
        for tool in tool_list:
            tool_name = tool.__name__ if hasattr(tool, '__name__') else str(tool)
            # Determine tool permission level
            tool_perm = "read"  # default
            for perm_level, perm_tools in TOOL_PERMISSIONS.items():
                if tool_name in perm_tools:
                    tool_perm = perm_level
                    break

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

    print("Toolset validation passed: All tools exist and are within permission ceilings")
    return True
