"""Every registered tool that returns a dict must have an explicit output
schema in registry/output_schemas.py (or the legacy family table), unless it
is allowlisted here. The allowlist is limited to helpers whose results are
consumed structurally (spatial/scene commands, conversational text, agent
orchestration) rather than analyzed downstream."""
from ai_agents.agents.toolsets import TOOL_LEVELS
from ai_agents.registry import tool_registry as tr
from ai_agents.registry.output_schemas import OUTPUT_SCHEMAS

# Tools without an explicit output schema. Grouped by why they are exempt.
ALLOWLIST_NO_EXPLICIT_SCHEMA = {
    # Spatial / scene / VR presentation helpers: results are scene commands,
    # not analyzed data.
    'browse_vr_folder', 'collapse_graph_node', 'dim_unrelated',
    'expand_graph_neighborhood', 'expand_graph_node', 'focus_camera',
    'focus_on_code_element', 'focus_on_graph_node', 'get_current_selection',
    'get_current_spatial_context', 'get_selected_node_details',
    'highlight_callers', 'highlight_vr_path', 'isolate_subgraph',
    'list_vr_repositories', 'move_graph', 'move_panel', 'navigate_to_code_element',
    'navigate_to_relationship', 'open_code_panel', 'open_vr_file',
    'open_vr_repository', 'recenter_workspace', 'reset_layout', 'scale_panel',
    'set_edge_style', 'set_mode', 'set_panel_state', 'show_ghost_diff',
    'show_test_badges', 'zoom_graph',
    # Visualization renderers: emit render payloads for the VR client.
    'compare_before_after', 'create_graph', 'visualize_architecture',
    'visualize_call_graph', 'visualize_change_impact',
    'visualize_control_flow', 'visualize_data_flow',
    'visualize_dependency_graph', 'visualize_unified_graph',
    # Conversational / orchestration helpers: text or plan payloads.
    'answer_code_question', 'ask_clarifying_question', 'check_task_completion',
    'classify_request', 'create_investigation_plan', 'exit_loop',
     'explain_class', 
    'explain_function', 'explain_graph_edge', 'explain_module',
    'explain_visualization', 'infer_code_intent', 'manage_conversation_preferences',
      'request_approval',
    'request_more_evidence', 
    'retrieve_conversation_context', 'retrieve_investigation_context',
    'summarize_graph', 'summarize_investigation', 'understand_user_intent',
    
    # Repository intelligence / navigation read helpers pending explicit
    # schemas (tracked for a follow-up pass).
     
    'analyze_dependencies_manifest', 'analyze_repository_structure',
    'detect_build_system', 'detect_frameworks', 'detect_languages',
    'detect_package_manager', 'detect_project_type',
     
    'extract_function_contract',  
     
      
      
      
      'identify_entry_points',
    'identify_external_services', 'identify_generated_files',
    'identify_hidden_assumptions', 
     
      
      'record_task_targets',
     'resolve_types', 
      
      
    'compare_code_elements',
}


def _explicit_schema_names():
    return set(OUTPUT_SCHEMAS) | set(tr._FAMILY_OUTPUT_SCHEMAS)


def test_all_dict_tools_have_explicit_output_schema():
    missing = [n for n in TOOL_LEVELS
               if n not in _explicit_schema_names()
               and n not in ALLOWLIST_NO_EXPLICIT_SCHEMA]
    assert not missing, (
        'registered tools lack an explicit output schema and are not '
        'allowlisted: %s' % sorted(missing))


def test_allowlist_has_no_stale_entries():
    stale = [n for n in ALLOWLIST_NO_EXPLICIT_SCHEMA
             if n not in TOOL_LEVELS
             or n in _explicit_schema_names()]
    assert not stale, 'allowlist entries that are registered-with-schema '
    'or no longer exist: %s' % sorted(stale)
