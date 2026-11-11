"""Shared architecture edit operations."""

import copy

COMPONENT_KINDS = {'service', 'library', 'ui', 'data', 'external'}
RELATIONSHIP_KINDS = {'calls', 'reads', 'publishes'}


def _valid_design_id(value):
    v = (value or '').strip()
    return bool(v) and len(v) <= 64 and all(ch.isalnum() or ch in '_.-' for ch in v)


def _question_matches(questions, text):
    if not text:
        return []
    exact = [i for i, q in enumerate(questions) if q == text]
    if exact:
        return exact
    low = text.lower()
    ci = [i for i, q in enumerate(questions) if q.lower() == low]
    if ci:
        return ci
    return [i for i, q in enumerate(questions) if low in q.lower()]


def _next_id(prefix, items, key='id'):
    used = {str(x.get(key)) for x in items}
    i = 1
    while '%s%d' % (prefix, i) in used:
        i += 1
    return '%s%d' % (prefix, i)


def apply_design_op(arch, op):
    """Apply one edit op to a deep copy of the architecture. Returns (arch, error)."""
    import copy
    arch = copy.deepcopy(arch)
    comps = arch.setdefault('components', [])
    rels = arch.setdefault('relationships', [])
    comp_ids = {c.get('id') for c in comps}
    op_type = (op.op or '').strip()

    if op_type == 'add_component':
        if not op.name.strip():
            return arch, 'add_component requires a name'
        cid = op.id.strip() or _next_id('c', comps)
        if not _valid_design_id(cid):
            return arch, 'invalid component id: ' + cid
        if cid in comp_ids:
            return arch, 'component id already exists: ' + cid
        kind = op.component_kind or 'service'
        if kind not in COMPONENT_KINDS:
            return arch, 'invalid component kind: ' + kind
        comps.append({'id': cid, 'name': op.name.strip(),
                      'responsibility': op.responsibility,
                      'kind': kind,
                      'requirement_ids': [str(x) for x in op.requirement_ids]})
    elif op_type == 'remove_component':
        if op.id not in comp_ids:
            return arch, 'unknown component: ' + op.id
        dangling = [r for r in rels if r.get('src') == op.id or r.get('dst') == op.id]
        if dangling:
            return arch, 'component %s has %d relationship(s); remove them first' % (op.id, len(dangling))
        arch['components'] = [c for c in comps if c.get('id') != op.id]
    elif op_type == 'update_component':
        comp = next((c for c in comps if c.get('id') == op.id), None)
        if comp is None:
            return arch, 'unknown component: ' + op.id
        for field, val in (('name', op.name), ('responsibility', op.responsibility), ('kind', op.component_kind)):
            if val:
                if field == 'kind' and val not in COMPONENT_KINDS:
                    return arch, 'invalid component kind: ' + val
                comp[field] = val
        if op.requirement_ids:
            comp['requirement_ids'] = [str(x) for x in op.requirement_ids]
    elif op_type == 'add_relationship':
        if op.src not in comp_ids or op.dst not in comp_ids:
            return arch, 'relationship endpoints must be existing component ids'
        if op.src == op.dst:
            return arch, 'a component cannot relate to itself'
        rid = op.id.strip() or _next_id('e', rels)
        if not _valid_design_id(rid):
            return arch, 'invalid relationship id: ' + rid
        if any(r.get('id') == rid for r in rels):
            return arch, 'relationship id already exists: ' + rid
        kind = op.kind or 'calls'
        if kind not in RELATIONSHIP_KINDS:
            return arch, 'invalid relationship kind: ' + kind
        rels.append({'id': rid, 'src': op.src, 'dst': op.dst,
                     'kind': kind, 'label': op.label})
    elif op_type == 'remove_relationship':
        before = len(rels)
        arch['relationships'] = [r for r in rels
                                 if r.get('id') != op.id
                                 and not (op.src and op.dst and r.get('src') == op.src and r.get('dst') == op.dst)]
        if len(arch['relationships']) == before:
            return arch, 'relationship not found'
    elif op_type == 'update_relationship':
        rel = next((r for r in rels if r.get('id') == op.id), None)
        if rel is None:
            return arch, 'unknown relationship: ' + op.id
        for field, val in (('kind', op.kind), ('label', op.label), ('src', op.src), ('dst', op.dst)):
            if val:
                if field == 'kind' and val not in RELATIONSHIP_KINDS:
                    return arch, 'invalid relationship kind: ' + val
                rel[field] = val
        comp_ids = {c.get('id') for c in arch['components']}
        if rel.get('src') not in comp_ids or rel.get('dst') not in comp_ids:
            return arch, 'relationship would dangle: unknown component id'
    elif op_type == 'resolve_question':
        questions = arch.setdefault('open_questions', [])
        idx = _question_matches(questions, op.question)
        if not idx:
            return arch, 'open question not found: ' + (op.question or '<empty>')
        answer = (op.answer or '').strip()
        if not answer:
            return arch, ('resolve_question requires a non-empty answer. '
                          'Pass the developer\'s resolution in "answer", or use '
                          'op "defer_question" with a reason to postpone it.')
        resolved = arch.setdefault('resolved_questions', [])
        for i in sorted(idx, reverse=True):
            # Keep the decision on record: the question, the developer's
            # answer/rationale and the revision it resolved at.
            resolved.append({'question': questions[i], 'answer': answer,
                             'revision': int(arch.get('revision') or 0) + 1})
            questions.pop(i)
    elif op_type == 'defer_question':
        # Explicit decision to postpone a question: it leaves the approval
        # gate but stays on record with the reason it was deferred.
        questions = arch.setdefault('open_questions', [])
        idx = _question_matches(questions, op.question)
        if not idx:
            return arch, 'open question not found: ' + (op.question or '<empty>')
        reason = (op.answer or op.label or '').strip()
        if not reason:
            return arch, 'defer_question requires a reason in "answer"'
        deferred = arch.setdefault('deferred_questions', [])
        for i in sorted(idx, reverse=True):
            deferred.append({'question': questions[i], 'reason': reason,
                             'revision': int(arch.get('revision') or 0) + 1})
            questions.pop(i)
    elif op_type == 'reopen_question':
        # Move a deferred or resolved question back to open_questions so it
        # blocks approval again.
        questions = arch.setdefault('open_questions', [])
        for key in ('deferred_questions', 'resolved_questions'):
            entries = arch.get(key) or []
            hit = next((e for e in entries
                        if _question_matches([e.get('question', '')], op.question)), None)
            if hit is not None:
                entries.remove(hit)
                text = hit.get('question', '')
                if text and text not in questions:
                    questions.append(text)
                return arch, None
        return arch, 'no deferred or resolved question matches: ' + (op.question or '<empty>')
    elif op_type == 'update_question':
        questions = arch.setdefault('open_questions', [])
        idx = _question_matches(questions, op.question)
        if not idx:
            return arch, 'open question not found: ' + (op.question or '<empty>')
        if not op.new_question.strip():
            return arch, 'update_question requires new_question text'
        questions[idx[0]] = op.new_question.strip()
    elif op_type == 'add_question':
        text = (op.question or op.new_question).strip()
        if not text:
            return arch, 'add_question requires question text'
        questions = arch.setdefault('open_questions', [])
        if text not in questions:
            questions.append(text)
    else:
        return arch, 'unknown op: ' + op_type

    # Final validation: no dangling relationships may survive any op sequence.
    comp_ids = {c.get('id') for c in arch.get('components', [])}
    for r in arch.get('relationships', []):
        if r.get('src') not in comp_ids or r.get('dst') not in comp_ids:
            return arch, 'dangling relationship: %s -> %s' % (r.get('src'), r.get('dst'))
    return arch, None




def finalize_edit(old_arch, new_arch, edited_by):
    new_arch['revision'] = int(old_arch.get('revision') or 1) + 1
    new_arch[edited_by] = True
    if new_arch.get('status') == 'approved':
        new_arch['status'] = 'draft'
        new_arch['approved_by'] = ''
        new_arch['approved_version'] = 0
        new_arch['approved_revision'] = 0
    return new_arch


def validate_architecture_structure(arch):
    problems = []
    comps = (arch or {}).get('components') or []
    rels = (arch or {}).get('relationships') or []
    if not comps:
        problems.append('The architecture has no components.')
    ids = [c.get('id') for c in comps]
    for cid in set(ids):
        if ids.count(cid) > 1:
            problems.append('Duplicate component id: %s' % cid)
    for c in comps:
        if c.get('kind') not in COMPONENT_KINDS:
            problems.append('Component %s has invalid kind %s' % (c.get('id'), c.get('kind')))
        if not str(c.get('responsibility') or '').strip():
            problems.append('Component %s has no responsibility' % c.get('id'))
    known = set(ids)
    for r in rels:
        if r.get('src') not in known or r.get('dst') not in known:
            problems.append('Relationship %s points at a missing component' % r.get('id'))
        if r.get('kind') not in RELATIONSHIP_KINDS:
            problems.append('Relationship %s has invalid kind %s' % (r.get('id'), r.get('kind')))
    return problems
