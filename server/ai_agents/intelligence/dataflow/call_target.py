"""Shared confirmed-call resolver.

One implementation used by the data-flow tools, the interprocedural summary
engine and the call-site connector, so a 'possible' or 'ambiguous' call edge
can never be upgraded to 'confirmed' on any analysis path.
"""

# Call-edge entries from graph.callees/graph.callers carry 'kind'
# ('confirmed' for static calls edges, 'possible'/'ambiguous' for may_call)
# and 'resolution' (the indexer's result status: 'static_resolved',
# 'polymorphic', 'ambiguous', ...). Only a statically confirmed edge may
# produce a confirmed data-flow edge.
CONFIRMED_RESOLUTIONS = {'confirmed', 'static_resolved'}


def edge_is_confirmed(e):
    kind = e.get('kind')
    if kind:
        return kind == 'confirmed'
    return e.get('resolution') in CONFIRMED_RESOLUTIONS


def resolve_call_target(graph, function_id, file, line, column):
    """Resolve the callee of a call site through the index's call-site edges,
    matched on file, line and column. Never picks a first match:

    - exactly one statically confirmed target -> {'status': 'resolved', ...}
    - several candidate targets / ambiguous edge -> {'status': 'ambiguous', ...}
    - only possible (unconfirmed) edges       -> {'status': 'possible', ...}
    - no usable call-site edge                -> {'status': 'unresolved', ...}
    """
    try:
        entries = graph.callees(function_id, depth=1,
                                include_possible=True, include_ambiguous=True)
    except Exception:
        entries = []
    candidates = [e for e in entries
                  if e.get('file') == file and e.get('line') == line]
    if not candidates:
        return {'status': 'unresolved',
                'reason': 'no call-site edge recorded at %s:%s' % (file, line)}
    exact = [e for e in candidates
             if column is not None and e.get('column') == column]
    if exact:
        candidates = exact
    elif len(candidates) > 1:
        return {'status': 'ambiguous',
                'candidates': sorted({e.get('to') for e in candidates
                                      if e.get('to')})}
    targets = []
    for e in candidates:
        t = e.get('to')
        if t and t not in targets:
            targets.append(t)
    if any(e.get('resolution') == 'ambiguous' for e in candidates) \
            or len(targets) > 1:
        return {'status': 'ambiguous', 'candidates': targets,
                'edges': candidates}
    if not targets:
        return {'status': 'unresolved', 'reason': 'call-site edge has no target'}
    confirmed = [e for e in candidates if edge_is_confirmed(e)]
    if not confirmed:
        return {'status': 'possible', 'candidates': targets,
                'reason': 'call edge is not statically resolved',
                'edges': candidates}
    return {'status': 'resolved', 'target_id': targets[0],
            'edge': confirmed[0]}
