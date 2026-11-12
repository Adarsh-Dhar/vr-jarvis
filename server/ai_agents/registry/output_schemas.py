"""Explicit output schemas for core tools.

The generic return-annotation fallback in tool_registry cannot express the
status envelope these tools actually return, so each covered tool gets a
schema here. Schemas describe the envelope and the fields guaranteed on
``status == 'ok'`` (or the tool's own success vocabulary); everything else
stays permissive so richer results still validate. Validation is fail-closed:
a result that violates its schema is replaced by a structured error.
"""

STATUSES = ['ok', 'error', 'not_found', 'unresolved', 'not_applicable',
            'blocked', 'ambiguous', 'verified', 'unverified', 'unknown',
            'unsupported_language', 'unavailable', 'resolved', 'possible',
            'failed', 'pending', 'none', 'no_path', 'missing', 'draft',
            'awaiting_user_approval', 'active']

# Parameters allowed to stay unrestricted (schema {} or x-unresolved) at
# registration. Keyed by (tool_name, param_name); value is the reason.
# Anything unresolved and NOT listed here fails registration.
UNRESTRICTED_PARAMS = {
}

# Shared contract fragments (audit item 2.16 G).
RESOLUTION = {'enum': ['confirmed', 'possible', 'ambiguous', 'unresolved']}
SOURCE_REF = {'type': 'object',
              'required': ['file', 'line'],
              'properties': {'file': {'type': 'string'},
                             'line': {'type': 'integer'}}}


def envelope(ok_props=None, ok_required=(), extra_statuses=(),
             error_required=True):
    """Standard result envelope: ``status`` required, ``error`` required when
    status is 'error', and ``ok_required`` fields required when the tool
    reports success (``ok`` plus any ``extra_statuses``)."""
    ok_statuses = ['ok'] + list(extra_statuses)
    schema = {
        'type': 'object',
        'required': ['status'],
        'properties': {
            'status': {'enum': STATUSES + [s for s in extra_statuses
                                           if s not in STATUSES]},
            'error': {'type': 'string'},
            **(ok_props or {}),
        },
        'allOf': [
            {'if': {'properties': {'status': {'enum': ok_statuses}}},
             'then': {'required': list(ok_required)}},
        ],
    }
    if error_required:
        schema['allOf'].append(
            {'if': {'properties': {'status': {'const': 'error'}}},
             'then': {'required': ['error']}})
    return schema


_LIST = {'type': 'array'}
_OBJ = {'type': 'object'}
_STR = {'type': 'string'}
_INT = {'type': 'integer'}
_NUM = {'type': 'number'}
_BOOL = {'type': 'boolean'}

# Evidence/edge item contracts shared by the core families. Evidence items
# are kept as plain objects: existing tools emit heterogeneous evidence
# shapes (file/line vs file/start/end), and fail-closed validation must not
# reject legitimate richer evidence. SOURCE_REF/RESOLUTION are the contract
# for NEW evidence producers (runtime traces, security findings).
_EVIDENCE_ITEM = {'type': 'object'}
_EVIDENCE_LIST = {'type': 'array', 'items': _EVIDENCE_ITEM}
_EDGE_LIST = {'type': 'array',
              'items': {'type': 'object', 'properties': {'resolution': RESOLUTION}}}

OUTPUT_SCHEMAS = {
    # run_tests reports passed/failed/unverified/error, not the generic
    # envelope; cached runs carry the same keys minus skipped/checks_not_run.
    'run_tests': {
        'type': 'object',
        'required': ['status'],
        'properties': {
            'status': {'enum': ['passed', 'failed', 'unverified', 'error', 'ok']},
            'passed': _LIST, 'failed': _LIST, 'skipped': _LIST,
            'checks_not_run': _LIST, 'not_run': _LIST,
            'error': _STR, 'stderr': _STR,
        },
        'allOf': [
            {'if': {'properties': {'status': {'enum': ['passed', 'failed']}}},
             'then': {'required': ['passed', 'failed']}},
            {'if': {'properties': {'status': {'const': 'error'}}},
             'then': {'required': ['error']}},
        ],
    },
    'run_typecheck': envelope(
        ok_props={'typecheck': {'enum': ['passed', 'failed', 'not_applicable']}},
        ok_required=['typecheck'],
        extra_statuses=['ok']),
    'build_data_flow_graph': envelope(
        ok_props={'graph': _OBJ, 'validation': _OBJ, 'diagnostics': _LIST,
                  'metadata': _OBJ},
        ok_required=['graph', 'validation', 'diagnostics', 'metadata']),
    'trace_cross_function_flow': envelope(
        ok_props={'outbound_argument_edges': _LIST,
                  'inbound_return_edges': _LIST, 'unresolved': _LIST},
        ok_required=['outbound_argument_edges', 'inbound_return_edges',
                     'unresolved']),
    'generate_implementation_plan': envelope(
        ok_props={'tasks': _LIST, 'circular': _LIST, 'cycle_paths': _LIST},
        ok_required=['tasks']),
    # Worktree patch tools
    # create_worktree/apply_patch_to_worktree report subprocess failures with
    # 'stderr' and no 'error' key, so the error-requirement is relaxed there.
    'create_worktree': envelope(ok_props={'worktree': _STR},
                                ok_required=['worktree'],
                                error_required=False),
    'apply_patch_to_worktree': envelope(ok_props={'applied': {'type': 'boolean'},
                                                  'task_id': _STR},
                                        ok_required=['applied'],
                                        error_required=False),
    'get_worktree_diff': envelope(ok_props={'diff': _STR},
                                  ok_required=['diff']),
    'read_worktree_file': envelope(ok_props={'file': _STR, 'content': _STR},
                                   ok_required=['file', 'content']),

    # ------------------------------------------------------------------
    # Repository family
    # ------------------------------------------------------------------
    'index_repository': envelope(
        ok_props={'repository': _STR, 'node_count': _INT, 'edge_count': _INT,
                  'test_count': _INT},
        ok_required=['node_count', 'edge_count']),
    'list_files': envelope(
        ok_props={'directory': _STR, 'files': _LIST, 'total': _INT,
                  'truncated': _BOOL},
        ok_required=['files']),
    'read_file': envelope(
        ok_props={'file_path': _STR, 'content': _STR, 'line_count': _INT,
                  'truncated': _BOOL},
        ok_required=['content']),
    'read_file_range': envelope(
        ok_props={'file_path': _STR, 'start_line': _INT, 'end_line': _INT,
                  'content': _STR},
        ok_required=['file_path', 'start_line', 'end_line', 'content']),
    'search_code': envelope(
        ok_props={'matches': _LIST, 'total': _INT},
        ok_required=['matches']),
    'get_repository_metadata': envelope(
        ok_props={'repository_path': _STR, 'branches': _LIST, 'remotes': _LIST,
                  'languages': _LIST},
        ok_required=['repository_path']),
    'get_changed_files': envelope(
        ok_props={'since_revision': _STR, 'changed_files': _LIST},
        ok_required=['changed_files']),
    'get_recent_commits': envelope(
        ok_props={'commits': _LIST},
        ok_required=['commits']),

    # ------------------------------------------------------------------
    # Graph / relationship family
    # ------------------------------------------------------------------
    'build_call_graph': envelope(
        ok_props={'scope': _STR, 'call_graph': _OBJ, 'node_count': _INT,
                  'edge_count': _INT},
        ok_required=['call_graph']),
    'find_callers': envelope(
        ok_props={'function_id': _STR, 'confirmed_callers': _LIST,
                  'possible_callers': _LIST, 'depth': _INT},
        ok_required=['confirmed_callers', 'possible_callers']),
    'find_callees': envelope(
        ok_props={'function_id': _STR, 'confirmed_callees': _LIST,
                  'possible_callees': _LIST},
        ok_required=['confirmed_callees', 'possible_callees']),
    'trace_call_chain': envelope(
        ok_props={'function_id': _STR, 'chains': _LIST, 'depth': _INT,
                  'include_possible': _BOOL, 'truncated': _BOOL},
        ok_required=['chains']),
    'get_call_sites': envelope(
        ok_props={'function_id': _STR, 'call_sites': _LIST, 'count': _INT},
        ok_required=['call_sites']),
    'build_dependency_graph': envelope(
        ok_props={'repository_path': _STR, 'nodes': _LIST, 'edges': _LIST,
                  'nodes_count': _INT, 'edges_count': _INT},
        ok_required=['nodes', 'edges']),
    'find_dependents': envelope(
        ok_props={'component_id': _STR, 'dependents': _LIST,
                  'dependent_count': _INT},
        ok_required=['dependents']),

    # ------------------------------------------------------------------
    # Architecture family
    # ------------------------------------------------------------------
    'extract_requirements': envelope(
        ok_props={'source': _STR, 'requirements': _LIST},
        ok_required=['requirements']),
    'propose_architecture': envelope(
        ok_props={'source': _STR, 'components': _LIST,
                  'relationships': _LIST},
        ok_required=['components', 'relationships']),
    'compare_to_repository': envelope(
        ok_props={'matched': _LIST, 'missing': _LIST, 'ambiguous': _LIST,
                  'extra': _LIST, 'relationships': _LIST,
                  'design_revision': _INT, 'repo': _STR},
        ok_required=['matched', 'missing', 'ambiguous', 'extra',
                     'relationships']),
    'validate_architecture': envelope(
        ok_props={'problems': _LIST},
        ok_required=['problems']),
    'get_proposed_architecture': envelope(
        ok_props={'architecture': _OBJ},
        ok_required=['architecture']),
    'add_component': envelope(
        ok_props={'revision': _INT, 'architecture': _OBJ},
        ok_required=['architecture']),
    'remove_component': envelope(
        ok_props={'revision': _INT, 'architecture': _OBJ},
        ok_required=['architecture']),
    'update_component': envelope(
        ok_props={'revision': _INT, 'architecture': _OBJ},
        ok_required=['architecture']),
    'add_relationship': envelope(
        ok_props={'revision': _INT, 'architecture': _OBJ},
        ok_required=['architecture']),
    'remove_relationship': envelope(
        ok_props={'revision': _INT, 'architecture': _OBJ},
        ok_required=['architecture']),
    'update_relationship': envelope(
        ok_props={'revision': _INT, 'architecture': _OBJ},
        ok_required=['architecture']),

    # ------------------------------------------------------------------
    # Data-flow family
    # ------------------------------------------------------------------
    'trace_variable_origin': envelope(
        ok_props={'variable_id': _STR, 'function_id': _STR,
                  'is_parameter': _BOOL, 'origin': _OBJ, 'origin_status': _STR,
                  'origins': _LIST, 'affected_uses': _LIST,
                  'use_count': _INT, 'evidence': _EVIDENCE_LIST},
        ok_required=['origins']),
    'trace_variable_usage': envelope(
        ok_props={'variable_id': _STR, 'function_id': _STR, 'uses': _LIST,
                  'use_count': _INT, 'evidence': _EVIDENCE_LIST},
        ok_required=['uses']),
    'trace_variable_modifications': envelope(
        ok_props={'variable_id': _STR, 'function_id': _STR, 'writes': _LIST,
                  'write_count': _INT, 'reads': _LIST, 'read_count': _INT,
                  'evidence': _EVIDENCE_LIST},
        ok_required=['writes', 'reads']),
    'trace_parameter_flow': envelope(
        ok_props={'function_id': _STR, 'parameter': _STR,
                  'parameter_definitions': _LIST, 'flow': _OBJ,
                  'use_count': _INT, 'evidence': _EVIDENCE_LIST},
        ok_required=['flow']),
    'trace_return_value_flow': envelope(
        ok_props={'function_id': _STR, 'return_flows': _LIST,
                  'call_sites': _LIST, 'call_count': _INT,
                  'unresolved': _LIST, 'evidence': _EVIDENCE_LIST},
        ok_required=['return_flows']),
    'trace_transformations': envelope(
        ok_props={'variable_id': _STR, 'function_id': _STR,
                  'transformations': _LIST, 'count': _INT,
                  'evidence': _EVIDENCE_LIST},
        ok_required=['transformations']),
    'trace_file_operations': envelope(
        ok_props={'file_path': _STR, 'operations': _LIST,
                  'data_relationships': _LIST, 'source_count': _INT,
                  'sink_count': _INT, 'handle_count': _INT,
                  'skipped_functions': _LIST, 'evidence': _EVIDENCE_LIST},
        ok_required=['operations']),
    'trace_state_changes': envelope(
        ok_props={'component_id': _STR, 'file': _STR, 'state_changes': _LIST,
                  'count': _INT, 'evidence': _EVIDENCE_LIST},
        ok_required=['state_changes']),

    # ------------------------------------------------------------------
    # Impact
    # ------------------------------------------------------------------
    'calculate_change_impact': envelope(
        ok_props={'element_id': _STR, 'direct_callers': _LIST,
                  'indirect_dependents': _LIST, 'possible_callers': _LIST,
                  'import_dependents': _LIST, 'direct_count': _INT,
                  'indirect_count': _INT, 'possible_count': _INT,
                  'import_count': _INT, 'total_affected': _INT,
                  'covering_tests': _LIST, 'untested': _LIST,
                  'risk_level': _STR, 'test_mapping': _LIST,
                  'risk_basis': _STR},
        ok_required=['direct_callers', 'indirect_dependents',
                     'possible_callers', 'import_dependents']),

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------
    # record_finding returns a string message; @safe wraps non-dict results
    # into {'status': 'ok', 'result': <value>}.
    'record_finding': envelope(ok_props={'result': {}},
                               ok_required=['result']),
    # get_findings likewise returns a list wrapped under 'result'.
    'get_findings': envelope(ok_props={'result': _LIST},
                             ok_required=['result']),

    # ------------------------------------------------------------------
    # Modification
    # ------------------------------------------------------------------
    'edit_file': envelope(
        ok_props={'file_path': _STR, 'edited': _BOOL, 'changes': _LIST},
        ok_required=['edited']),
    'apply_patch': envelope(
        ok_props={'patch_length': _INT, 'applied': _BOOL, 'method': _STR},
        ok_required=['applied']),
    'search_and_replace': envelope(
        ok_props={'file_pattern': _STR, 'replacements': _INT,
                  'files_affected': _LIST},
        ok_required=['replacements', 'files_affected']),
    'git_status': envelope(
        ok_props={'repository_path': _STR, 'branch': _STR,
                  'modified': _LIST, 'untracked': _LIST},
        ok_required=['modified', 'untracked']),
    'git_diff': envelope(
        ok_props={'repository_path': _STR, 'file_path': _STR, 'diff': _STR,
                  'exit_code': _INT},
        ok_required=['diff']),
    'git_branch': envelope(
        ok_props={'repository_path': _STR, 'branches': _LIST,
                  'current': _STR},
        ok_required=['branches', 'current']),
}
