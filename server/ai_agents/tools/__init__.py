"""
JARVIS Tool Ecosystem
Comprehensive tool architecture for the JARVIS AI software engineering environment.

This module exports the MVP tool surface: the union of every agent toolset
in agents/toolsets.py. Tools that are not part of an agent toolset are not
exported here (they remain importable from their submodules for internal use).
"""

from .repository_tools import (
    list_files,
    read_file,
    read_file_range,
    search_code,
    get_repository_metadata,
    get_changed_files,
)

from .navigation_tools import (
    get_symbol_definition,
    get_symbol_references,
    get_symbol_hover_info,
    get_type_hierarchy,
    get_imports,
    get_exports,
    get_scope_information,
)

from .analysis_tools import (
    parse_source_code,
    extract_symbols,
    resolve_types,
    analyze_control_flow,
)

from .orchestrator_tools import (
    understand_user_intent,
    classify_request,
    create_investigation_plan,
    merge_agent_results,
    resolve_conflicting_findings,
    request_more_evidence,
    check_task_completion,
    invoke_repository_intelligence,
    invoke_code_understanding,
    invoke_relationship_intelligence,
    invoke_data_flow_intelligence,
    invoke_software_engineering,
    invoke_testing_verification,
    invoke_visualization_spatial,
    invoke_conversational,
    invoke_architecture_design,
)

from .architecture_tools import (
    extract_requirements,
    propose_architecture,
    compare_to_repository,
    generate_implementation_plan,
    verify_task_evidence,
)

from .conversational_tools import (
    retrieve_conversation_context,
    retrieve_investigation_context,
    explain_visualization,
    answer_code_question,
    compare_code_elements,
    summarize_investigation,
    ask_clarifying_question,
    manage_conversation_preferences,
)

from .repository_intelligence_tools import (
    detect_languages,
    detect_frameworks,
    detect_build_system,
    detect_package_manager,
    detect_project_type,
    identify_entry_points,
    analyze_repository_structure,
    analyze_dependencies_manifest,
    identify_external_services,
    identify_generated_files,
    index_repository,
    incremental_index_repository,
    detect_repository_changes,
)

from .code_understanding_tools import (
    explain_function,
    explain_class,
    explain_module,
    explain_condition,
    extract_function_contract,
    identify_side_effects,
    identify_hidden_assumptions,
    infer_code_intent,
    trace_function_logic,
)

from .relationship_intelligence_tools import (
    build_call_graph,
    find_callers,
    find_callees,
    get_call_sites,
    explain_call_resolution,
    trace_call_chain,
    find_indirect_callers,
    build_dependency_graph,
    find_dependents,
    find_interface_implementations,
    trace_cross_module_relationships,
    find_circular_dependencies,
    analyze_architecture_boundaries,
    calculate_change_impact,
    find_all_paths_between_symbols,
)

from .data_flow_intelligence_tools import (
    trace_variable_origin,
    trace_variable_usage,
    trace_variable_modifications,
    trace_parameter_flow,
    trace_return_value_flow,
    trace_transformations,
    trace_cross_function_flow,
    trace_file_operations,
    trace_state_changes,
    build_data_flow_graph,
    visualize_data_flow,
)

from .software_engineering_tools import (
    edit_file,
    apply_patch,
    search_and_replace,
    format_code,
    organize_imports,
    git_status,
    git_diff,
    git_branch,
    generate_function,
    generate_class,
    extract_function,
    rename_symbol,
)

from .testing_verification_tools import (
    discover_tests,
    run_unit_tests,
    run_regression_tests,
    measure_test_coverage,
    map_tests_to_functions,
    identify_untested_paths,
    verify_compilation,
    verify_types,
    verify_lint,
    compare_before_after,
)

from .visualization_spatial_tools import (
    create_graph,
    expand_graph_node,
    collapse_graph_node,
    isolate_subgraph,
    summarize_graph,
    visualize_call_graph,
    visualize_dependency_graph,
    visualize_control_flow,
    visualize_unified_graph,
    visualize_architecture,
    visualize_change_impact,
    get_current_selection,
    focus_on_graph_node,
    navigate_to_code_element,
    navigate_to_relationship,
    get_selected_node_details,
    get_current_spatial_context,
    explain_graph_edge,
    query_graph_path,
    expand_graph_neighborhood,
    focus_on_code_element,
)

from .graph_tools import (
    verify_citations,
)

from .exec_tools import (
    run_tests,
    run_typecheck,
    read_test_results,
)

from .git_tools import (
    create_worktree,
    apply_patch_to_worktree,
    get_worktree_diff,
)

from .scene_tools import (
    highlight_vr_path,
    dim_unrelated,
    focus_camera,
    open_code_panel,
    set_edge_style,
    show_ghost_diff,
    show_test_badges,
    set_mode,
    list_vr_repositories,
    open_vr_repository,
    browse_vr_folder,
    open_vr_file,
    move_graph,
    zoom_graph,
    move_panel,
    scale_panel,
    set_panel_state,
    highlight_callers,
    recenter_workspace,
    reset_layout,
)

from .control_tools import (
    request_approval,
)

from .findings_tools import (
    record_finding,
    get_findings,
)

# Dynamically generate __all__ from actual imports
__all__ = sorted(n for n, v in globals().items()
                 if callable(v) and not n.startswith('_')
                 and getattr(v, '__module__', '').startswith(__name__))
