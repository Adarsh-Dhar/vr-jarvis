"""Explicit output schemas for core tools.

The generic return-annotation fallback in tool_registry cannot express the
status envelope these tools actually return, so each covered tool gets a
schema here. Schemas describe the envelope and the fields guaranteed on
``status == 'ok'`` (or the tool's own success vocabulary); everything else
stays permissive so richer results still validate. Validation is fail-closed:
a result that violates its schema is replaced by a structured error.
"""

STATUSES = ['ok', 'error', 'not_found', 'unresolved', 'not_applicable']


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
}
