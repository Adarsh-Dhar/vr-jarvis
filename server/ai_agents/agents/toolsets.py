"""
Agent Toolsets
Curated tool mappings for each of the JARVIS agents.
Each agent gets a focused set of MVP tools.

Uses string names for tools to avoid slow imports. Tools are resolved
when needed by calling get_toolset().
"""

import re
from typing import List, Dict

# Permission ceilings for each agent
PERMISSION_CEILINGS = {
    "architecture_design": 'write',
    "code_understanding": 'read',
    "conversational": 'read',
    "data_flow_intelligence": 'read',
    "orchestrator": 'read',
    "relationship_intelligence": 'read',
    "repository_intelligence": 'read',
    "software_engineering": 'write',
    "testing_verification": 'execute',
    "visualization_spatial": 'read',
    # fix_pipeline agents (agents/fix.py). Without these entries the guard defaults to 'read'
    # and blocks create_worktree / apply_patch_to_worktree / run_tests.
    "patch_agent": 'write',
    "patch_repair_agent": 'write',
    "verifier_agent": 'execute',
    "code_reviewer": 'read',
}

# Tool permission levels - must contain every tool name in TOOLSETS
TOOL_LEVELS = {
    "analyze_architecture_boundaries": "read",
    "compare_to_repository": "read",
    "extract_requirements": "read",
    "generate_implementation_plan": "read",
    "propose_architecture": "read",
    "verify_task_evidence": "read",
    "analyze_control_flow": "read",
    "analyze_dependencies_manifest": "read",
    "analyze_repository_structure": "read",
    "answer_code_question": "read",
    "apply_patch": "write",
    "apply_patch_to_worktree": "write",
    "add_component": "write",
    "add_relationship": "write",
    "ask_clarifying_question": "read",
    "browse_vr_folder": "read",
    "build_call_graph": "read",
    "build_data_flow_graph": "read",
    "build_dependency_graph": "read",
    "calculate_change_impact": "read",
    "check_task_completion": "read",
    "classify_request": "read",
    "collapse_graph_node": "read",
    "compare_before_after": "read",
    "compare_code_elements": "read",
    "create_graph": "read",
    "create_investigation_plan": "read",
    "create_worktree": "write",
    "detect_build_system": "read",
    "detect_frameworks": "read",
    "detect_languages": "read",
    "detect_package_manager": "read",
    "detect_project_type": "read",
    "detect_repository_changes": "read",
    "dim_unrelated": "read",
    "discover_tests": "read",
    "edit_file": "write",
    "expand_graph_neighborhood": "read",
    "expand_graph_node": "read",
    "explain_call_resolution": "read",
    "explain_class": "read",
    "explain_condition": "read",
    "explain_function": "read",
    "explain_graph_edge": "read",
    "explain_module": "read",
    "explain_visualization": "read",
    "extract_function": "write",
    "extract_function_contract": "read",
    "extract_symbols": "read",
    "find_all_paths_between_symbols": "read",
    "find_callees": "read",
    "find_callers": "read",
    "find_circular_dependencies": "read",
    "find_dependents": "read",
    "find_indirect_callers": "read",
    "find_interface_implementations": "read",
    "focus_camera": "read",
    "focus_on_code_element": "read",
    "focus_on_graph_node": "read",
    "format_code": "write",
    "generate_class": "write",
    "generate_function": "write",
    "get_call_sites": "read",
    "get_proposed_architecture": "read",
    "get_recent_commits": "read",
    "get_changed_files": "read",
    "get_current_selection": "read",
    "get_current_spatial_context": "read",
    "get_exports": "read",
    "get_findings": "read",
    "get_imports": "read",
    "get_repository_metadata": "read",
    "get_scope_information": "read",
    "get_selected_node_details": "read",
    "get_symbol_definition": "read",
    "get_symbol_hover_info": "read",
    "get_symbol_references": "read",
    "get_type_hierarchy": "read",
    "get_worktree_diff": "read",
    "git_branch": "read",
    "git_diff": "read",
    "git_status": "read",
    "highlight_callers": "read",
    "highlight_vr_path": "read",
    "identify_entry_points": "read",
    "identify_external_services": "read",
    "identify_generated_files": "read",
    "identify_hidden_assumptions": "read",
    "identify_side_effects": "read",
    "identify_untested_paths": "read",
    "incremental_index_repository": "read",
    "index_repository": "read",
    "infer_code_intent": "read",
    "isolate_subgraph": "read",
    "list_files": "read",
    "list_vr_repositories": "read",
    "manage_conversation_preferences": "read",
    "map_tests_to_functions": "read",
    "measure_test_coverage": "read",
    "merge_agent_results": "read",
    "remove_component": "write",
    "remove_relationship": "write",
    "move_graph": "read",
    "move_panel": "read",
    "navigate_to_code_element": "read",
    "navigate_to_relationship": "read",
    "open_code_panel": "read",
    "open_vr_file": "read",
    "open_vr_repository": "read",
    "organize_imports": "write",
    "parse_source_code": "read",
    "query_graph_path": "read",
    "read_file": "read",
    "read_file_range": "read",
    "read_test_results": "read",
    "read_worktree_file": "read",
    "record_task_targets": "write",
    "recenter_workspace": "read",
    "record_finding": "read",
    "rename_symbol": "write",
    "request_approval": "read",
    "request_more_evidence": "read",
    "reset_layout": "read",
    "resolve_conflicting_findings": "read",
    "resolve_types": "read",
    "retrieve_conversation_context": "read",
    "retrieve_investigation_context": "read",
    "run_integration_tests": "execute",
    "run_regression_tests": "execute",
    "run_tests": "execute",
    "run_typecheck": "execute",
    "run_unit_tests": "execute",
    "scale_panel": "read",
    "search_and_replace": "write",
    "search_code": "read",
    "set_edge_style": "read",
    "set_mode": "read",
    "set_panel_state": "read",
    "show_ghost_diff": "read",
    "show_test_badges": "read",
    "summarize_graph": "read",
    "summarize_investigation": "read",
    "trace_call_chain": "read",
    "trace_cross_function_flow": "read",
    "trace_cross_module_relationships": "read",
    "trace_file_operations": "read",
    "trace_function_logic": "read",
    "trace_parameter_flow": "read",
    "trace_return_value_flow": "read",
    "trace_state_changes": "read",
    "trace_transformations": "read",
    "trace_variable_modifications": "read",
    "trace_variable_origin": "read",
    "trace_variable_usage": "read",
    "understand_user_intent": "read",
    "update_component": "write",
    "update_relationship": "write",
    "validate_architecture": "read",
    "verify_citations": "read",
    "verify_compilation": "read",
    "verify_lint": "read",
    "verify_types": "read",
    "visualize_architecture": "read",
    "visualize_call_graph": "read",
    "visualize_change_impact": "read",
    "visualize_control_flow": "read",
    "visualize_data_flow": "read",
    "visualize_dependency_graph": "read",
    "visualize_unified_graph": "read",
    "zoom_graph": "read",
}

# Curated toolsets for each agent (using string names)
TOOLSETS: Dict[str, List[str]] = {
    "architecture_design": ['extract_requirements', 'propose_architecture', 'compare_to_repository', 'generate_implementation_plan', 'get_proposed_architecture', 'validate_architecture', 'add_component', 'remove_component', 'update_component', 'add_relationship', 'remove_relationship', 'update_relationship'],
    "orchestrator": ['classify_request', 'understand_user_intent', 'create_investigation_plan', 'check_task_completion', 'merge_agent_results', 'resolve_conflicting_findings', 'request_more_evidence', 'request_approval'],
    "conversational": ['answer_code_question', 'explain_visualization', 'summarize_investigation', 'retrieve_conversation_context', 'retrieve_investigation_context', 'ask_clarifying_question', 'compare_code_elements', 'manage_conversation_preferences'],
    "repository_intelligence": ['index_repository', 'incremental_index_repository', 'detect_languages', 'detect_frameworks', 'detect_build_system', 'detect_project_type', 'detect_package_manager', 'analyze_repository_structure', 'identify_entry_points', 'identify_external_services', 'identify_generated_files', 'detect_repository_changes', 'analyze_dependencies_manifest', 'list_files', 'read_file', 'search_code', 'get_repository_metadata', 'get_changed_files', 'get_recent_commits', 'record_finding', 'get_findings'],
    "code_understanding": ['get_symbol_definition', 'get_symbol_references', 'get_symbol_hover_info', 'get_type_hierarchy', 'get_imports', 'get_exports', 'get_scope_information', 'parse_source_code', 'extract_symbols', 'resolve_types', 'explain_function', 'explain_class', 'explain_module', 'explain_condition', 'extract_function_contract', 'identify_side_effects', 'identify_hidden_assumptions', 'infer_code_intent', 'trace_function_logic', 'analyze_control_flow', 'read_file_range', 'record_finding', 'get_findings'],
    "relationship_intelligence": ['find_callers', 'find_callees', 'find_indirect_callers', 'trace_call_chain', 'get_call_sites', 'explain_call_resolution', 'build_call_graph', 'build_dependency_graph', 'find_dependents', 'find_all_paths_between_symbols', 'find_circular_dependencies', 'analyze_architecture_boundaries', 'calculate_change_impact', 'find_interface_implementations', 'trace_cross_module_relationships', 'record_finding', 'get_findings'],
    "data_flow_intelligence": ['trace_variable_origin', 'trace_variable_usage', 'trace_variable_modifications', 'trace_parameter_flow', 'trace_return_value_flow', 'trace_transformations', 'trace_cross_function_flow', 'trace_file_operations', 'trace_state_changes', 'build_data_flow_graph', 'record_finding', 'get_findings'],
    "software_engineering": ['create_worktree', 'apply_patch_to_worktree', 'get_worktree_diff', 'edit_file', 'apply_patch', 'search_and_replace', 'organize_imports', 'format_code', 'git_status', 'git_branch', 'git_diff', 'read_file', 'search_code', 'record_task_targets', 'get_recent_commits'],
    "testing_verification": ['discover_tests', 'map_tests_to_functions', 'identify_untested_paths', 'run_unit_tests', 'run_integration_tests', 'run_regression_tests', 'measure_test_coverage', 'verify_compilation', 'verify_lint', 'verify_types', 'compare_before_after', 'run_tests', 'run_typecheck', 'read_test_results', 'record_finding', 'get_findings'],
    "visualization_spatial": ['highlight_vr_path', 'dim_unrelated', 'focus_camera', 'open_code_panel', 'list_vr_repositories', 'open_vr_repository', 'browse_vr_folder', 'open_vr_file', 'move_graph', 'zoom_graph', 'move_panel', 'scale_panel', 'set_panel_state', 'highlight_callers', 'recenter_workspace', 'reset_layout', 'set_mode', 'set_edge_style', 'show_ghost_diff', 'show_test_badges', 'create_graph', 'visualize_call_graph', 'visualize_change_impact', 'visualize_data_flow', 'visualize_architecture', 'visualize_dependency_graph', 'visualize_control_flow', 'visualize_unified_graph', 'explain_graph_edge', 'query_graph_path', 'expand_graph_neighborhood', 'expand_graph_node', 'collapse_graph_node', 'isolate_subgraph', 'summarize_graph', 'get_current_selection', 'verify_citations', 'focus_on_graph_node', 'navigate_to_code_element', 'navigate_to_relationship', 'get_selected_node_details', 'get_current_spatial_context', 'focus_on_code_element'],
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


def validate_instruction_tools(instructions):
    errors = []
    for agent, text in instructions.items():
        allowed = set(TOOLSETS.get(agent, []))
        for name in sorted(TOOL_LEVELS):
            pattern = r'(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])' % re.escape(name)
            if re.search(pattern, text) and name not in allowed:
                errors.append('%s: instruction mentions %s but its toolset lacks it' % (agent, name))
    return errors
