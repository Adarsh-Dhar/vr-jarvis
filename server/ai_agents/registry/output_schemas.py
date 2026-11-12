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
             error_required=True, statuses=None):
    """Standard result envelope: ``status`` required, ``error`` required when
    status is 'error', and ``ok_required`` fields required when the tool
    reports success (``ok`` plus any ``extra_statuses``).

    ``statuses`` narrows the allowed status vocabulary per tool; without it
    the full STATUSES enum plus ``extra_statuses`` is allowed."""
    ok_statuses = ['ok'] + list(extra_statuses)
    allowed = list(statuses) if statuses else \
        STATUSES + [s for s in extra_statuses if s not in STATUSES]
    schema = {
        'type': 'object',
        'required': ['status'],
        'properties': {
            'status': {'enum': allowed},
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
# Cross-function flow edge: {source, target, resolution, file, line}.
_FLOW_EDGE = {'type': 'object',
              'properties': {'source': _STR, 'target': _STR,
                             'resolution': _STR, 'file': _STR,
                             'line': _INT}}

# Shared item contracts for list-valued result fields.
FINDING_ITEM = {'type': 'object',
                'required': ['severity', 'file', 'line', 'issue'],
                'properties': {'severity': {'enum': ['blocker', 'warning', 'info']},
                               'category': {'enum': ['logic', 'error_handling',
                                                     'security', 'quality',
                                                     'tests']},
                               'file': {'type': 'string', 'minLength': 1},
                               'line': {'type': 'integer', 'minimum': 1},
                               'issue': {'type': 'string', 'minLength': 1},
                               'suggestion': {'type': 'string'}}}
CALL_EDGE = {'type': 'object',
             'required': ['from', 'to', 'resolution'],
             'properties': {'from': _STR, 'to': _STR, 'resolution': RESOLUTION,
                            'file': _STR,
                            'line': {'type': 'integer', 'minimum': 1}}}

# The code reviewer's structured output (state['code_review']).
CODE_REVIEW_SCHEMA = {
    'type': 'object',
    'required': ['verdict', 'findings'],
    'properties': {
        'verdict': {'enum': ['approve', 'request_changes', 'block']},
        'summary': _STR,
        'findings': {'type': 'array', 'items': FINDING_ITEM},
        'acceptance': {'type': 'array',
                       'items': {'type': 'object',
                                 'required': ['criterion', 'status'],
                                 'properties': {
                                     'criterion_index': _INT,
                                     'criterion': _STR,
                                     'status': {'enum': ['met', 'not_met',
                                                         'unknown']}}}},
        'security': _OBJ,
    },
}

SECURITY_FINDING = {'type': 'object',
  'required': ['rule_id', 'category', 'severity', 'file', 'line', 'title',
               'evidence', 'remediation', 'confidence',
               'introduced_by_current_change'],
  'properties': {'rule_id': {'type': 'string',
                             'pattern': r'^PY-[A-Z]+-\d{3}$'},
                 'category': {'enum': ['dynamic_code_execution',
                     'command_execution', 'unsafe_deserialization',
                     'hardcoded_credentials', 'weak_crypto',
                     'certificate_verification_disabled', 'file_handling']},
                 'severity': {'enum': ['low', 'medium', 'high', 'critical']},
                 'file': {'type': 'string', 'minLength': 1},
                 'line': {'type': 'integer', 'minimum': 1},
                 'confidence': {'enum': ['low', 'medium', 'high']},
                 'introduced_by_current_change': {'type': 'boolean'}}}

# Tools that must have an explicit OUTPUT_SCHEMAS entry; a missing one fails
# registry construction at startup.
CORE_TOOLS = {
    # repository / code reading
    'get_symbol_definition', 'get_symbol_references', 'get_symbol_hover_info',
    'extract_symbols', 'parse_source_code', 'extract_function', 'get_imports',
    'get_exports', 'get_scope_information', 'get_type_hierarchy',
    # architecture
    'analyze_architecture_boundaries', 'verify_task_evidence',
    # call graph
    'find_indirect_callers', 'explain_call_resolution',
    'find_all_paths_between_symbols', 'find_interface_implementations',
    'query_graph_path', 'find_circular_dependencies',
    # DFG
    'trace_cross_module_relationships', 'identify_side_effects',
    # CFG
    'analyze_control_flow', 'trace_function_logic', 'explain_condition',
    # change impact
    'detect_repository_changes', 'incremental_index_repository',
    # code modification
    'generate_function', 'generate_class', 'rename_symbol',
    'organize_imports', 'format_code',
    # testing
    'discover_tests', 'map_tests_to_functions', 'identify_untested_paths',
    'measure_test_coverage', 'read_test_results', 'verify_compilation',
    'verify_lint', 'verify_types', 'run_unit_tests', 'run_integration_tests',
    'run_regression_tests',
    # review
    'merge_agent_results', 'resolve_conflicting_findings', 'verify_citations',
    # security
    'run_security_scan',
}

_RUN_TESTS_SCHEMA = {
    'type': 'object',
    'required': ['status'],
    'properties': {
        'status': {'enum': ['passed', 'failed', 'unverified', 'error', 'ok']},
        'passed': {'type': 'array'}, 'failed': {'type': 'array'},
        'skipped': {'type': 'array'}, 'checks_not_run': {'type': 'array'},
        'not_run': {'type': 'array'},
        'error': {'type': 'string'}, 'stderr': {'type': 'string'},
    },
    'allOf': [
        {'if': {'properties': {'status': {'enum': ['passed', 'failed']}}},
         'then': {'required': ['passed', 'failed']}},
        {'if': {'properties': {'status': {'const': 'error'}}},
         'then': {'required': ['error']}},
    ],
}

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
        ok_props={'outbound_argument_edges': {'type': 'array', 'items': _FLOW_EDGE},
                  'inbound_return_edges': {'type': 'array', 'items': _FLOW_EDGE},
                  'chain': {'type': 'array',
                            'items': {'type': 'array', 'items': _FLOW_EDGE}},
                  'max_depth': _INT,
                  'unresolved': _LIST},
        ok_required=['outbound_argument_edges', 'inbound_return_edges',
                     'chain', 'unresolved']),
    'generate_implementation_plan': envelope(
        ok_props={'tasks': _LIST, 'circular': _LIST, 'cycle_paths': _LIST},
        ok_required=['tasks']),
    # Worktree patch tools
    'create_worktree': envelope(ok_props={'worktree': _STR},
                                ok_required=['worktree']),
    'apply_patch_to_worktree': envelope(ok_props={'applied': {'type': 'boolean'},
                                                  'task_id': _STR},
                                        ok_required=['applied']),
    'get_worktree_diff': envelope(ok_props={'diff': _STR},
                                  ok_required=['diff']),
    'read_worktree_file': envelope(ok_props={'file': _STR, 'content': _STR},
                                   ok_required=['file', 'content']),
    'exit_loop': envelope({}),

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

    # ------------------------------------------------------------------
    # Core families (C8): explicit schemas so no core tool falls back to
    # the generic annotation schema.
    # ------------------------------------------------------------------
    'get_symbol_definition': envelope(
        ok_props={'symbol': _OBJ, 'definition': _OBJ}, ok_required=['symbol']),
    'get_symbol_references': envelope(
        ok_props={'references': _LIST, 'count': _INT},
        ok_required=['references']),
    'get_symbol_hover_info': envelope(
        ok_props={'hover': _STR, 'info': _OBJ}, ok_required=['hover']),
    'extract_symbols': envelope(
        ok_props={'symbols': _LIST, 'file': _STR}, ok_required=['symbols']),
    'parse_source_code': envelope(
        ok_props={'ast': _OBJ, 'symbols': _LIST, 'file': _STR},
        ok_required=['file']),
    'extract_function': envelope(
        ok_props={'function': _OBJ, 'code': _STR, 'file': _STR},
        ok_required=['function']),
    'get_imports': envelope(
        ok_props={'imports': _LIST, 'file': _STR}, ok_required=['imports']),
    'get_exports': envelope(
        ok_props={'exports': _LIST, 'file': _STR}, ok_required=['exports']),
    'get_scope_information': envelope(
        ok_props={'scopes': _LIST, 'scope': _OBJ}, ok_required=['scopes']),
    'get_type_hierarchy': envelope(
        ok_props={'hierarchy': _OBJ, 'types': _LIST},
        ok_required=['hierarchy']),
    'analyze_architecture_boundaries': envelope(
        ok_props={'boundaries': _LIST, 'modules': _LIST, 'violations': _LIST},
        ok_required=['boundaries']),
    'verify_task_evidence': envelope(
        ok_props={'claims': _LIST, 'verified': _LIST, 'failed': _LIST},
        ok_required=['claims']),
    'find_indirect_callers': envelope(
        ok_props={'callers': _LIST, 'indirect': _LIST},
        ok_required=['callers']),
    'explain_call_resolution': envelope(
        ok_props={'resolution': _STR, 'steps': _LIST, 'target': _STR},
        ok_required=['resolution']),
    'find_all_paths_between_symbols': envelope(
        ok_props={'paths': _LIST, 'source': _STR, 'target': _STR},
        ok_required=['paths']),
    'find_interface_implementations': envelope(
        ok_props={'implementations': _LIST, 'interface': _STR},
        ok_required=['implementations']),
    'query_graph_path': envelope(
        ok_props={'path': _LIST, 'nodes': _LIST, 'edges': _LIST},
        ok_required=['path']),
    'find_circular_dependencies': envelope(
        ok_props={'cycles': _LIST, 'circular': _LIST},
        ok_required=['cycles']),
    'trace_cross_module_relationships': envelope(
        ok_props={'relationships': _LIST, 'modules': _LIST},
        ok_required=['relationships']),
    'identify_side_effects': envelope(
        ok_props={'side_effects': _LIST, 'function_id': _STR},
        ok_required=['side_effects']),
    'analyze_control_flow': envelope(
        ok_props={'graph': _OBJ, 'paths': _LIST, 'node_count': _INT},
        ok_required=['graph']),
    'trace_function_logic': envelope(
        ok_props={'logic': _LIST, 'steps': _LIST, 'trace': _LIST},
        ok_required=['logic']),
    'explain_condition': envelope(
        ok_props={'condition': _STR, 'explanation': _STR, 'branches': _LIST},
        ok_required=['explanation']),
    'detect_repository_changes': envelope(
        ok_props={'changes': _LIST, 'changed_files': _LIST},
        ok_required=['changes']),
    'incremental_index_repository': envelope(
        ok_props={'indexed': _INT, 'updated': _LIST, 'node_count': _INT},
        ok_required=['updated']),
    'generate_function': envelope(
        ok_props={'code': _STR, 'file': _STR, 'function': _STR},
        ok_required=['code']),
    'generate_class': envelope(
        ok_props={'code': _STR, 'file': _STR, 'class_name': _STR},
        ok_required=['code']),
    'rename_symbol': envelope(
        ok_props={'renamed': _BOOL, 'occurrences': _INT, 'file': _STR},
        ok_required=['renamed']),
    'organize_imports': envelope(
        ok_props={'organized': _BOOL, 'file': _STR, 'changes': _LIST},
        ok_required=['organized']),
    'format_code': envelope(
        ok_props={'formatted': _BOOL, 'file': _STR, 'changes': _LIST},
        ok_required=['formatted']),
    'discover_tests': envelope(
        ok_props={'tests': _LIST, 'count': _INT, 'files': _LIST},
        ok_required=['tests']),
    'map_tests_to_functions': envelope(
        ok_props={'mapping': _LIST, 'tests': _LIST, 'functions': _LIST},
        ok_required=['mapping']),
    'identify_untested_paths': envelope(
        ok_props={'untested': _LIST, 'paths': _LIST, 'coverage': _OBJ},
        ok_required=['untested']),
    'measure_test_coverage': envelope(
        ok_props={'coverage': _NUM, 'covered': _LIST, 'total': _INT},
        ok_required=['coverage']),
    'read_test_results': envelope(
        ok_props={'results': _LIST, 'passed': _INT, 'failed': _INT},
        ok_required=['results']),
    'verify_compilation': envelope(
        ok_props={'compiled': _BOOL, 'errors': _LIST, 'output': _STR},
        ok_required=['compiled']),
    'verify_lint': envelope(
        ok_props={'lint': _STR, 'issues': _LIST, 'clean': _BOOL},
        ok_required=['issues']),
    'verify_types': envelope(
        ok_props={'typecheck': _STR, 'errors': _LIST, 'clean': _BOOL},
        ok_required=['errors']),
    # run_unit/integration/regression reuse the run_tests shape.
    'run_unit_tests': _RUN_TESTS_SCHEMA,
    'run_integration_tests': _RUN_TESTS_SCHEMA,
    'run_regression_tests': _RUN_TESTS_SCHEMA,
    'merge_agent_results': envelope(
        ok_props={'merged': _OBJ, 'total_results': _INT, 'result': _LIST},
        ok_required=['merged']),
    'resolve_conflicting_findings': envelope(
        ok_props={'resolved': _LIST, 'conflicts': _LIST, 'result': _OBJ},
        ok_required=['resolved']),
    'verify_citations': envelope(
        ok_props={'citations': _LIST, 'verified': _LIST, 'invalid': _LIST},
        ok_required=['citations']),
    'run_security_scan': envelope(
        ok_props={'scanner': _STR, 'scanner_version': _STR,
                  'ruleset_version': _STR, 'files_scanned': _INT,
                  'diff_hash': _STR, 'counts': _OBJ,
                  'unsupported_rules_ignored': _INT,
                  'unsupported_rule_ids': _OBJ,
                  'findings': {'type': 'array', 'items': SECURITY_FINDING}},
        ok_required=['scanner', 'findings', 'diff_hash'],
        statuses=['completed', 'failed', 'unavailable', 'error']),
}


# run_security_scan: failed/unavailable results must carry 'error'.
OUTPUT_SCHEMAS['run_security_scan'].setdefault('allOf', []).append(
    {'if': {'properties': {'status': {'enum': ['failed', 'unavailable']}}},
     'then': {'required': ['error']}})


# ----------------------------------------------------------------------
# Strict reusable fragments (audit 2.4): nested graph/result objects are
# validated, not just envelopes.
# ----------------------------------------------------------------------
SOURCE_REFERENCE = {'type': 'object',
                    'required': ['file', 'line'],
                    'properties': {'file': _STR, 'line': _INT}}
GRAPH_NODE = {'type': 'object',
              'required': ['id', 'kind'],
              'properties': {'id': _STR, 'kind': _STR,
                             'file': _STR, 'line': _INT,
                             'source': SOURCE_REFERENCE}}
GRAPH_EDGE = {'type': 'object',
              'required': ['source', 'target', 'kind', 'resolution'],
              'properties': {'source': _STR, 'target': _STR,
                             'kind': _STR, 'resolution': RESOLUTION,
                             'file': _STR, 'line': _INT}}
DFG_EDGE = {'type': 'object',
            'required': ['source', 'target', 'kind', 'resolution'],
            'properties': {'source': _STR, 'target': _STR,
                           'kind': _STR, 'resolution': RESOLUTION,
                           'evidence': _EVIDENCE_ITEM}}
FUNCTION_RESULT = {'type': 'object',
                   'required': ['id', 'name', 'file'],
                   'properties': {'id': _STR, 'name': _STR, 'file': _STR,
                                  'line': _INT}}
IMPLEMENTATION_TASK = {'type': 'object',
                       'required': ['id', 'title', 'status'],
                       'properties': {'id': _STR, 'title': _STR,
                                      'description': _STR, 'status': _STR,
                                      'dependencies': _LIST,
                                      'acceptance_criteria': _LIST}}
PATCH_RESULT = {'type': 'object',
                'required': ['operation_id', 'worktree', 'status'],
                'properties': {'operation_id': _STR, 'worktree': _STR,
                               'status': _STR, 'diff': _STR,
                               'resulting_diff': _STR}}

# Strict edge/evidence lists built on the fragments above.
_GRAPH_NODE_LIST = {'type': 'array', 'items': GRAPH_NODE}
_GRAPH_EDGE_LIST = {'type': 'array', 'items': GRAPH_EDGE}
_DFG_EDGE_LIST = {'type': 'array', 'items': DFG_EDGE}

# ----------------------------------------------------------------------
# Repository-intelligence tools (MVP)
# ----------------------------------------------------------------------
OUTPUT_SCHEMAS.update({
    'analyze_dependencies_manifest': envelope(
        ok_props={'manifest': _STR, 'dependencies': _LIST,
                  'file': _STR},
        ok_required=['dependencies']),
    'analyze_repository_structure': envelope(
        ok_props={'directories': _LIST, 'files': _LIST, 'tree': _OBJ},
        ok_required=['directories', 'files']),
    'detect_build_system': envelope(
        ok_props={'build_system': _STR, 'files': _LIST,
                  'detected': _LIST},
        ok_required=['detected']),
    'detect_frameworks': envelope(
        ok_props={'frameworks': _LIST, 'detected': _LIST},
        ok_required=['detected']),
    'detect_languages': envelope(
        ok_props={'languages': _LIST, 'counts': _OBJ},
        ok_required=['languages']),
    'detect_package_manager': envelope(
        ok_props={'package_manager': _STR, 'detected': _LIST,
                  'files': _LIST},
        ok_required=['detected']),
    'detect_project_type': envelope(
        ok_props={'project_type': _STR, 'detected': _LIST,
                  'confidence': _NUM},
        ok_required=['detected']),
    'extract_function_contract': envelope(
        ok_props={'contract': _OBJ, 'function_id': _STR, 'file': _STR},
        ok_required=['contract']),
    'identify_entry_points': envelope(
        ok_props={'entry_points': _LIST, 'count': _INT},
        ok_required=['entry_points']),
    'identify_external_services': envelope(
        ok_props={'services': _LIST, 'external_services': _LIST},
        ok_required=['services']),
    'identify_generated_files': envelope(
        ok_props={'generated_files': _LIST, 'files': _LIST},
        ok_required=['generated_files']),
    'identify_hidden_assumptions': envelope(
        ok_props={'assumptions': _LIST, 'hidden_assumptions': _LIST},
        ok_required=['assumptions']),
    'record_task_targets': envelope(
        ok_props={'tasks': _LIST, 'targets': _LIST, 'recorded': _BOOL},
        ok_required=['targets']),
    'resolve_types': envelope(
        ok_props={'types': _LIST, 'resolved': _LIST, 'file': _STR},
        ok_required=['types']),
    'compare_code_elements': envelope(
        ok_props={'comparison': _OBJ, 'differences': _LIST,
                  'similarities': _LIST, 'elements': _LIST},
        ok_required=['comparison']),
})

# ----------------------------------------------------------------------
# Visualization tools (MVP)
# ----------------------------------------------------------------------
OUTPUT_SCHEMAS.update({
    'visualize_architecture': envelope(
        ok_props={'node_count': _INT, 'edge_count': _INT, 'scope': _STR},
        ok_required=['node_count', 'edge_count']),
    'visualize_call_graph': envelope(
        ok_props={'function_id': _STR, 'nodes': _LIST, 'edges': _LIST,
                  'node_count': _INT, 'edge_count': _INT},
        ok_required=['nodes', 'edges']),
    'visualize_dependency_graph': envelope(
        ok_props={'nodes': _GRAPH_NODE_LIST, 'edges': _GRAPH_EDGE_LIST,
                  'node_count': _INT, 'edge_count': _INT},
        ok_required=['nodes', 'edges']),
    'visualize_data_flow': envelope(
        ok_props={'function_id': _STR, 'nodes': _LIST, 'edges': _LIST,
                  'graph': _OBJ, 'node_count': _INT, 'edge_count': _INT},
        ok_required=['edges']),
    'visualize_control_flow': envelope(
        ok_props={'function_id': _STR, 'nodes': _LIST, 'edges': _LIST,
                  'node_count': _INT, 'edge_count': _INT},
        ok_required=['nodes', 'edges']),
    'visualize_unified_graph': envelope(
        ok_props={'function_id': _STR, 'nodes': _LIST, 'edges': _LIST,
                  'node_count': _INT, 'edge_count': _INT,
                  'scope': _STR, 'summarized': _BOOL,
                  'graph_type': _STR},
        ok_required=['nodes', 'edges']),
    'visualize_change_impact': envelope(
        ok_props={'element_id': _STR, 'impacted': _LIST, 'nodes': _LIST,
                  'edges': _LIST, 'node_count': _INT, 'edge_count': _INT},
        ok_required=['impacted']),
})

# DFG result: 'graph' must be a real graph object with node/edge lists, not
# an arbitrary object.
OUTPUT_SCHEMAS['build_data_flow_graph']['properties']['graph'] = {
    'type': 'object',
    'required': ['nodes', 'edges'],
    'properties': {'nodes': _LIST, 'edges': _LIST}}

# Conversational / orchestration / spatial helpers: envelope contracts.
# Their results are scene commands or text payloads consumed structurally;
# the envelope still enforces the status field fail-closed.
for _t in [
    'answer_code_question', 'ask_clarifying_question', 'browse_vr_folder',
    'check_task_completion', 'classify_request', 'collapse_graph_node',
    'compare_before_after', 'create_graph', 'create_investigation_plan',
    'dim_unrelated', 'expand_graph_neighborhood', 'expand_graph_node',
    'explain_class', 'explain_function', 'explain_graph_edge',
    'explain_module', 'explain_visualization', 'focus_camera',
    'focus_on_code_element', 'focus_on_graph_node',
    'get_current_selection', 'get_current_spatial_context',
    'get_selected_node_details', 'highlight_callers', 'highlight_vr_path',
    'infer_code_intent', 'isolate_subgraph', 'list_vr_repositories',
    'manage_conversation_preferences', 'move_graph', 'move_panel',
    'navigate_to_code_element', 'navigate_to_relationship',
    'open_code_panel', 'open_vr_file', 'open_vr_repository',
    'recenter_workspace', 'request_approval', 'request_more_evidence',
    'reset_layout', 'retrieve_conversation_context',
    'retrieve_investigation_context', 'scale_panel', 'set_edge_style',
    'set_mode', 'set_panel_state', 'show_ghost_diff', 'show_test_badges',
    'summarize_graph', 'summarize_investigation', 'understand_user_intent',
    'zoom_graph',
]:
    OUTPUT_SCHEMAS.setdefault(_t, envelope())


# ----------------------------------------------------------------------
# Tools bound directly to fix_pipeline / analyst agents (v26 Phase 1).
# Entries use the shared fragments defined above.
# ----------------------------------------------------------------------
_GNODE_LIST = {'type': 'array', 'items': GRAPH_NODE}
OUTPUT_SCHEMAS.update({
    'search_graph_symbols': envelope(
        ok_props={'matches': _GNODE_LIST}, ok_required=['matches']),
    'get_source': envelope(
        ok_props={'id': _STR, 'file': _STR, 'first_line': _INT,
                  'source': _STR, 'total_lines': _INT, 'truncated': _BOOL},
        ok_required=['file', 'first_line', 'source']),
    'get_callers': envelope(
        ok_props={'node': _STR, 'callers': _GNODE_LIST, 'total': _INT,
                  'truncated': _BOOL},
        ok_required=['callers']),
    'find_tests_for_node': envelope(
        ok_props={'node': _STR, 'tests': _LIST, 'untested': _BOOL},
        ok_required=['tests']),
    'get_call_hierarchy': envelope(
        ok_props={'symbol_name': _STR, 'symbol_id': _STR,
                  'incoming_calls': _LIST, 'outgoing_calls': _LIST},
        ok_required=['incoming_calls', 'outgoing_calls'],
        extra_statuses=['not_found']),
    'search_symbols': envelope(
        ok_props={'symbol_name': _STR,
                  'matches': {'type': 'array', 'items': _OBJ}},
        ok_required=['matches']),
    'get_node': envelope(
        ok_props={'id': _STR, 'name': _STR, 'file': _STR, 'cluster': _STR,
                  'coverage': {'type': ['number', 'null']}},
        ok_required=['id']),
    'get_callees': envelope(
        ok_props={'node': _STR, 'callees': _GNODE_LIST, 'total': _INT,
                  'truncated': _BOOL},
        ok_required=['callees']),
    'get_dependents': envelope(
        ok_props={'node': _STR, 'dependents': _GNODE_LIST, 'total': _INT,
                  'truncated': _BOOL},
        ok_required=['dependents']),
    'trace_path': envelope(
        ok_props={'path': _LIST, 'hops': _LIST},
        ok_required=['path'], extra_statuses=['no_path']),
    'get_cluster': envelope(
        ok_props={'cluster': _STR,
                  'members': {'type': 'array', 'items': GRAPH_NODE},
                  'total': _INT, 'truncated': _BOOL},
        ok_required=['members']),
    'get_coverage': envelope(
        ok_props={'node': _STR, 'coverage': {'type': ['number', 'null']}},
        ok_required=['coverage']),
    'get_diff': envelope(
        ok_props={'branch': _STR, 'diff': _STR},
        ok_required=['branch', 'diff']),
    'list_changed_nodes': envelope(
        ok_props={'changed_nodes': _LIST},
        ok_required=['changed_nodes']),
    'analyze_dependencies': envelope(
        ok_props={'file_path': _STR, 'dependencies': _LIST},
        ok_required=['dependencies']),
    # Runtime tracing (Phase 3). Events carry names/locations only.
    'start_runtime_trace': envelope(
        ok_props={'trace_id': _STR}, ok_required=['trace_id']),
    'stop_runtime_trace': envelope(ok_props={'trace_id': _STR}),
    'get_runtime_trace': envelope(
        ok_props={'trace_id': _STR,
                  'events': {'type': 'array', 'items': {
                      'type': 'object',
                      'required': ['sequence', 'kind', 'function', 'file',
                                   'line'],
                      'properties': {
                          'sequence': _INT,
                          'kind': {'enum': ['call', 'return', 'exception']},
                          'function': _STR, 'file': _STR, 'line': _INT,
                          'module': _STR, 'exception_type': _STR}}},
                  'call_edges': {'type': 'array', 'items': {
                      'type': 'object',
                      'required': ['source', 'target']}},
                  'exit_code': {'type': ['integer', 'null']},
                  'truncated': _BOOL},
        ok_required=['trace_id'],
        extra_statuses=['running', 'completed', 'failed', 'stopped',
                        'timed_out']),
})
