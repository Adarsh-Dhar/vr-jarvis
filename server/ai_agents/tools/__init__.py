"""
JARVIS Tool Ecosystem
Comprehensive tool architecture for the JARVIS AI software engineering environment.

This module exports all tools organized by category:
- Shared Superpowers (repository access, code navigation, universal analysis)
- Agent-Specific Tools (Agents 1-12)
- Specialist Toolkits (API/database, documentation, Git history, external integrations)
- Language and Framework Adapters
- VR-Specific Tools
- Infrastructure Services
"""

# Shared Superpowers
from .repository_tools import (
    list_repositories,
    open_repository,
    list_files,
    read_file,
    read_file_range,
    search_files,
    search_code,
    get_file_metadata,
    get_repository_metadata,
    watch_repository,
    get_changed_files,
)

from .navigation_tools import (
    get_symbol_definition,
    get_symbol_references,
    get_symbol_hover_info,
    get_call_hierarchy,
    get_type_hierarchy,
    get_imports,
    get_exports,
    get_scope_information,
    get_symbol_documentation,
    find_implementations,
)

from .analysis_tools import (
    parse_source_code,
    extract_ast,
    extract_symbols,
    resolve_types,
    resolve_references,
    analyze_control_flow,
    analyze_data_flow,
    analyze_dependencies,
    analyze_code_complexity,
    detect_code_duplication,
    detect_dead_code,
    analyze_exceptions,
    analyze_annotations,
    analyze_macros,
    analyze_generated_code,
)

# Agent 1 - JARVIS Orchestrator
from .orchestrator_tools import (
    understand_user_intent,
    classify_request,
    create_investigation_plan,
    decompose_task,
    select_agents,
    delegate_task,
    run_agents_parallel,
    run_agents_sequentially,
    wait_for_agent,
    get_agent_status,
    cancel_agent_task,
    retry_agent_task,
    merge_agent_results,
    resolve_conflicting_findings,
    request_more_evidence,
    check_task_completion,
    request_user_approval,
    manage_task_priority,
    # Delegation tools for invoking specialist agents
    invoke_repository_intelligence,
    invoke_code_understanding,
    invoke_relationship_intelligence,
    invoke_data_flow_intelligence,
    invoke_software_engineering,
    invoke_testing_verification,
    invoke_visualization_spatial,
    invoke_conversational,
)

# Agent 2 - Conversational JARVIS
from .conversational_tools import (
    speech_to_text,
    text_to_speech,
    stream_voice_response,
    detect_speaker_intent,
    detect_voice_activity,
    manage_conversation,
    retrieve_conversation_context,
    retrieve_investigation_context,
    explain_code_element,
    explain_visualization,
    answer_code_question,
    compare_code_elements,
    summarize_investigation,
    ask_clarifying_question,
    interrupt_current_response,
    manage_conversation_preferences,
)

# Agent 3 - Repository Intelligence
from .repository_intelligence_tools import (
    detect_languages,
    detect_frameworks,
    detect_build_system,
    detect_package_manager,
    detect_project_type,
    identify_entry_points,
    analyze_repository_structure,
    analyze_monorepo,
    analyze_project_configuration,
    analyze_build_configuration,
    analyze_environment_configuration,
    analyze_dependencies_manifest,
    resolve_dependency_versions,
    identify_external_services,
    identify_generated_files,
    index_repository,
    incremental_index_repository,
    detect_repository_changes,
)

# Agent 4 - Code Understanding
from .code_understanding_tools import (
    parse_function,
    explain_function,
    explain_class,
    explain_module,
    explain_variable,
    explain_expression,
    explain_condition,
    explain_algorithm,
    extract_function_signature,
    extract_function_contract,
    identify_side_effects,
    identify_hidden_assumptions,
    infer_code_intent,
    compare_implementations,
    trace_function_logic,
    generate_code_summary,
)

# Agent 5 - Relationship Intelligence
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
    find_shared_dependencies,
    build_reference_graph,
    build_class_relationship_graph,
    find_interface_implementations,
    trace_cross_module_relationships,
    trace_cross_service_relationships,
    find_circular_dependencies,
    analyze_architecture_boundaries,
    calculate_change_impact,
    find_all_paths_between_symbols,
)

# Agent 6 - Data Flow Intelligence
from .data_flow_intelligence_tools import (
    trace_variable_origin,
    trace_variable_usage,
    trace_variable_modifications,
    trace_parameter_flow,
    trace_return_value_flow,
    trace_taint_flow,
    trace_transformations,
    trace_cross_function_flow,
    trace_cross_service_flow,
    trace_database_reads,
    trace_database_writes,
    trace_api_data_flow,
    trace_file_operations,
    trace_state_changes,
    build_data_flow_graph,
    identify_data_leaks,
    identify_data_sinks,
    identify_data_sources,
    identify_validation_gaps,
    visualize_data_flow,
)




# Agent 10 - Software Engineering
from .software_engineering_tools import (
    # File editing tools
    create_file,
    edit_file,
    apply_patch,
    delete_file,
    rename_file,
    move_file,
    create_directory,
    search_and_replace,
    format_code,
    organize_imports,
    # Terminal and build tools
    execute_command,
    execute_script,
    install_dependency,
    remove_dependency,
    run_compiler,
    run_build,
    run_linter,
    run_formatter,
    run_type_checker,
    inspect_environment,
    manage_environment_variables,
    manage_processes,
    inspect_command_output,
    # Git tools
    git_status,
    git_diff,
    git_log,
    git_show,
    git_branch,
    git_create_branch,
    git_commit,
    git_stash,
    git_revert,
    git_blame,
    git_create_checkpoint,
    # Implementation tools
    generate_function,
    generate_class,
    generate_module,
    generate_api,
    generate_database_model,
    generate_component,
    refactor_function,
    extract_function,
    rename_symbol,
    update_references,
    implement_interface,
    generate_documentation,
    apply_architecture_change,
)

# Agent 11 - Testing & Verification
from .testing_verification_tools import (
    discover_tests,
    run_unit_tests,
    run_integration_tests,
    run_end_to_end_tests,
    run_regression_tests,
    run_property_tests,
    run_fuzz_tests,
    generate_unit_tests,
    generate_edge_case_tests,
    generate_integration_tests,
    measure_test_coverage,
    measure_branch_coverage,
    map_tests_to_functions,
    identify_untested_paths,
    verify_compilation,
    verify_types,
    verify_lint,
    compare_before_after,
    generate_test_report,
)

# Agent 12 - Visualization & Spatial Intelligence
from .visualization_spatial_tools import (
    # Graph tools
    create_graph,
    add_graph_node,
    remove_graph_node,
    add_graph_edge,
    remove_graph_edge,
    expand_graph_node,
    collapse_graph_node,
    search_graph,
    highlight_path,
    highlight_dependencies,
    isolate_subgraph,
    compare_graphs,
    calculate_graph_layout,
    calculate_graph_clusters,
    calculate_graph_centrality,
    calculate_graph_depth,
    summarize_graph,
    # Visualization tools
    visualize_call_graph,
    visualize_dependency_graph,
    visualize_control_flow,
    visualize_unified_graph,
    visualize_architecture,
    visualize_test_coverage,
    visualize_change_impact,
    # Spatial tools
    get_current_selection,
    get_spatial_selection_context,
    select_code_element,
    focus_on_object,
    expand_relationships,
    trace_relationship_path,
    isolate_relationship_path,
    get_spatial_object_details,
    # Aliases for missing spatial tools
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





# Language and Framework Adapters
from .language_adapters import (
    # Language adapters
    register_language_adapter,
    get_language_adapter,
    list_supported_languages,
    parse_language_ast,
    resolve_language_types,
    extract_language_symbols,
    analyze_language_specific_features,
    # Framework adapters
    register_framework_adapter,
    get_framework_adapter,
    list_supported_frameworks,
    discover_framework_routes,
    analyze_framework_lifecycle,
    discover_framework_components,
    analyze_framework_dependency_injection,
    discover_framework_middleware,
    analyze_framework_event_handling,
    analyze_framework_component_relationships,
    analyze_framework_orm_integration,
    analyze_framework_configuration,
    analyze_framework_runtime_instrumentation,
)

# VR-Specific Tools
# Note: Spatial tools (select_code_element, focus_on_object, etc.) are in visualization_spatial_tools.py


# Existing tools (preserved for compatibility)
from .graph_tools import (
    search_graph_symbols,
    get_node,
    get_callers,
    get_callees,
    get_dependents,
    trace_path,
    get_cluster,
    get_source,
    find_tests_for_node,
    get_coverage,
    verify_citations,
)

from .exec_tools import (
    run_tests,
    run_typecheck,
    read_test_results,
)

from .git_tools import (
    get_diff,
    list_changed_nodes,
    get_branch_info,
    create_worktree,
    apply_patch_to_worktree,
    get_worktree_diff,
    commit_worktree,
)


from .scene_tools import (
    highlight_vr_path,
    dim_unrelated,
    focus_camera,
    open_code_panel,
    set_edge_style,
    show_ghost_diff,
    show_test_badges,
    show_approval_prompt,
    set_mode,
    list_vr_repositories,
    open_vr_repository,
    browse_vr_folder,
    open_vr_file,
    move_cluster,
    move_graph,
    zoom_graph,
    move_panel,
    scale_panel,
    set_panel_state,
    set_cluster_collapsed,
    highlight_callers,
    recenter_workspace,
    reset_layout,
)

from .control_tools import (
    request_approval,
    exit_loop,
)

# Common utilities
from ._common import record_evidence
from ._safe import safe

# Findings tools
from .findings_tools import (
    record_finding,
    get_findings,
    verify_finding,
)

# Dynamically generate __all__ from actual imports
__all__ = sorted(n for n, v in globals().items()
                 if callable(v) and not n.startswith('_')
                 and getattr(v, '__module__', '').startswith(__name__))
