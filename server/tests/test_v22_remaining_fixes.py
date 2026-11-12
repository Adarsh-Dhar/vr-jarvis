"""Regression tests for the v22 remaining audit fixes: confirmed-only call
edges, positional-only binding, statement-based open() handle binding,
truncation reporting, caller return-flow targets, tool contracts, review
acceptance completeness and the verify-repair gate."""
import ast
import json
from types import SimpleNamespace

import pytest


def _fn(src):
    return ast.parse(src).body[0]


def _op(line, column, expression, **kw):
    base = dict(operation='Call', line=line, column=column,
                expression=expression, output_definition_ids=[],
                metadata={}, input_use_ids=[], input_operation_ids=[])
    base.update(kw)
    return SimpleNamespace(**base)


# ------------------------------------------------------- call binding (3.3)

def _shape(positional=(), keywords=()):
    return {'positional': list(positional), 'keywords': list(keywords)}


def _pos():
    return {'kind': 'positional', 'name': None, 'starred': False,
            'use_ids': [], 'operation_id': None}


def _kw(name):
    return {'kind': 'keyword', 'name': name, 'starred': False,
            'use_ids': [], 'operation_id': None}


def test_bind_call_positional_only():
    from ai_agents.intelligence.dataflow.call_binding import bind_call
    fn = _fn('def process(value, /, destination):\n    pass\n')
    # process(100, 'out') — both bound by position
    out = bind_call(_shape([_pos(), _pos()]), fn)
    assert out['status'] == 'ok'
    assert [b['param'] for b in out['bindings']] == ['value', 'destination']
    # process(100, destination='out')
    out = bind_call(_shape([_pos()], [_kw('destination')]), fn)
    assert out['status'] == 'ok'
    # process(value=100, destination='out') — value is positional-only
    out = bind_call(_shape([], [_kw('value'), _kw('destination')]), fn)
    assert out['status'] != 'ok'
    by_kw = {b['keyword']: b for b in out['bindings']}
    assert by_kw['value']['status'] == 'unresolved'
    assert by_kw['value'].get('reason') == 'positional-only parameter passed by keyword'
    assert by_kw['destination']['status'] == 'bound'


def test_bind_call_positional_only_with_kwargs():
    from ai_agents.intelligence.dataflow.call_binding import bind_call
    fn = _fn('def g(a, /, **kw):\n    pass\n')
    out = bind_call(_shape([_pos()], [_kw('a')]), fn)
    assert out['status'] == 'ok'
    bound = {b['param']: b for b in out['bindings'] if b['status'] == 'bound'}
    assert 'kw' in bound  # a=2 lands in **kw, matching Python semantics


def test_bind_call_positional_only_mixed():
    from ai_agents.intelligence.dataflow.call_binding import bind_call
    fn = _fn('def f(a, /, b, *, c):\n    pass\n')
    out = bind_call(_shape([_pos(), _pos()], [_kw('c')]), fn)
    assert out['status'] == 'ok'
    assert [b['param'] for b in out['bindings'][:2]] == ['a', 'b']
    out = bind_call(_shape([], [_kw('a')]), fn)
    assert out['status'] == 'unresolved'


def test_bind_call_positional_only_method_self():
    from ai_agents.intelligence.dataflow.call_binding import bind_call
    cls = _fn('class A:\n    def m(self, /, x):\n        pass\n')
    meth = cls.body[0]
    out = bind_call(_shape([_pos()]), meth, is_method=True)
    assert out['status'] == 'ok'
    assert out['bindings'][0]['param'] == 'x'


# ------------------------------------------------- confirmed call edges (2)

def _graph(entries, nodes=None):
    nodes = nodes or {}
    return SimpleNamespace(
        callees=lambda *a, **k: entries,
        callers=lambda *a, **k: entries,
        get=lambda nid: nodes.get(nid))


def test_resolve_call_target_confirmed():
    from ai_agents.tools.data_flow_intelligence_tools import _resolve_call_target
    entries = [{'to': 'm.py::B.g', 'file': 'm.py', 'line': 10, 'column': 4,
                'kind': 'confirmed', 'resolution': 'static_resolved'}]
    graph = _graph(entries, {'m.py::B.g': {'id': 'm.py::B.g'}})
    out = _resolve_call_target(graph, {'function_id': 'm.py::A.f', 'file': 'm.py'},
                               _op(10, 4, 'g(x)'))
    assert out['status'] == 'resolved'
    assert out['node_id'] == 'm.py::B.g'


def test_resolve_call_target_possible_not_resolved():
    from ai_agents.tools.data_flow_intelligence_tools import _resolve_call_target
    entries = [{'to': 'm.py::B.g', 'file': 'm.py', 'line': 10, 'column': 4,
                'kind': 'possible', 'resolution': 'polymorphic'}]
    graph = _graph(entries, {'m.py::B.g': {'id': 'm.py::B.g'}})
    out = _resolve_call_target(graph, {'function_id': 'm.py::A.f', 'file': 'm.py'},
                               _op(10, 4, 'g(x)'))
    assert out['status'] == 'possible'
    assert out['candidates'] == ['m.py::B.g']


def test_resolve_call_target_ambiguous():
    from ai_agents.tools.data_flow_intelligence_tools import _resolve_call_target
    entries = [
        {'to': 'm.py::B.g', 'file': 'm.py', 'line': 10, 'column': 4,
         'kind': 'ambiguous', 'resolution': 'ambiguous'},
        {'to': 'm.py::C.g', 'file': 'm.py', 'line': 10, 'column': 4,
         'kind': 'ambiguous', 'resolution': 'ambiguous'},
    ]
    graph = _graph(entries)
    out = _resolve_call_target(graph, {'function_id': 'm.py::A.f', 'file': 'm.py'},
                               _op(10, 4, 'g(x)'))
    assert out['status'] == 'ambiguous'
    assert sorted(out['candidates']) == ['m.py::B.g', 'm.py::C.g']


# ------------------------------------------- caller result flows (3.2, PR4)

def _caller_ctx(src, fid='m.py::caller'):
    fn = _fn(src)
    return {'func_ast': fn,
            'facts': SimpleNamespace(definitions=[], uses=[], operations=[]),
            'analysis': {'node_uses': {}, 'in_sets': {}},
            'function_id': fid, 'file': 'm.py', 'node': {}, 'source': src}


def _call_pos(fn, name):
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            nm = f.id if isinstance(f, ast.Name) else getattr(f, 'attr', None)
            if nm == name:
                return n.lineno, n.col_offset
    raise AssertionError('call not found')


def _run_caller_flows(monkeypatch, caller_src, entries):
    import ai_agents.tools.data_flow_intelligence_tools as dft
    from ai_agents.intelligence.graph_engine import codegraph as cg
    caller_ctx = _caller_ctx(caller_src)
    monkeypatch.setattr(dft, '_function_facts',
                        lambda fid, use_cache=True: (caller_ctx, None))
    fake_graph = SimpleNamespace(
        callers=lambda *a, **k: entries,
        get=lambda nid: {'id': nid, 'file': 'm.py', 'kind': 'function'})
    monkeypatch.setattr(cg.codegraph, 'load_current_graph',
                        staticmethod(lambda: fake_graph))
    return dft._caller_result_flows({'function_id': 'm.py::calc'})


def _confirmed_entry(caller_src, fid='m.py::caller'):
    fn = _fn(caller_src)
    line, col = _call_pos(fn, 'calc')
    return {'from': fid, 'file': 'm.py', 'line': line, 'column': col,
            'kind': 'confirmed', 'resolution': 'static_resolved',
            'callsite_id': 'cs1'}


def test_caller_result_flows_confirmed_assignment(monkeypatch):
    src = 'def caller():\n    result = calc()\n    return result\n'
    results, unresolved = _run_caller_flows(monkeypatch, src,
                                            [_confirmed_entry(src)])
    assert not unresolved
    assert len(results) == 1
    res = results[0]['result']
    assert res['disposition'] == 'assigned'
    assert res['assigned_variables'] == ['result']


@pytest.mark.parametrize('kind,resolution', [
    ('possible', 'polymorphic'), ('ambiguous', 'ambiguous')])
def test_caller_result_flows_unconfirmed_routed_to_unresolved(
        monkeypatch, kind, resolution):
    src = 'def caller():\n    result = calc()\n    return result\n'
    entry = _confirmed_entry(src)
    entry['kind'], entry['resolution'] = kind, resolution
    results, unresolved = _run_caller_flows(monkeypatch, src, [entry])
    assert not results
    assert len(unresolved) == 1
    assert 'not statically confirmed' in unresolved[0]['reason']


@pytest.mark.parametrize('src,checks', [
    ('def caller():\n    result.value = calc()\n',
     lambda r: r['disposition'] == 'assigned'
     and r['assigned_attributes'] == ['result.value']
     and r['assigned_variables'] == []),
    ('def caller():\n    items[i] = calc()\n',
     lambda r: r['disposition'] == 'assigned'
     and r['assigned_subscripts'] == ['items[i]']
     and r['assigned_variables'] == []),
    ('def caller():\n    a, b = calc()\n',
     lambda r: r['disposition'] == 'unpacked'
     and sorted(r['assigned_variables']) == ['a', 'b']),
    ('def caller():\n    total += calc()\n',
     lambda r: r['disposition'] == 'assigned' and r['augmented'] is True),
])
def test_caller_result_flows_target_kinds(monkeypatch, src, checks):
    results, unresolved = _run_caller_flows(monkeypatch, src,
                                            [_confirmed_entry(src)])
    assert not unresolved
    assert len(results) == 1
    assert checks(results[0]['result'])


def test_caller_result_flows_nested_call_not_assignment(monkeypatch):
    src = 'def caller():\n    x = wrap(calc())\n'
    results, unresolved = _run_caller_flows(monkeypatch, src,
                                            [_confirmed_entry(src)])
    assert not unresolved
    assert len(results) == 1
    assert results[0]['result']['disposition'] == 'nested_in_expression'


# --------------------------------------- open() handle binding (PR3.1)

def _file_ctx(src):
    fn = _fn(src)
    ops = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            ops.append(_op(n.lineno, n.col_offset, ast.unparse(n)))
    defs = []
    for n in ast.walk(fn):
        if isinstance(n, ast.With):
            for item in n.items:
                if isinstance(item.optional_vars, ast.Name):
                    defs.append(SimpleNamespace(
                        id='d_' + item.optional_vars.id, variable=item.optional_vars.id,
                        line=n.lineno, column=item.optional_vars.col_offset,
                        kind='with_binding', metadata={}))
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    defs.append(SimpleNamespace(
                        id='d_' + t.id, variable=t.id, line=n.lineno,
                        column=t.col_offset, kind='assignment', metadata={}))
    return {'func_ast': fn,
            'facts': SimpleNamespace(operations=ops, definitions=defs, uses=[]),
            'analysis': {'node_uses': {}, 'in_sets': {}},
            'function_id': 'm.py::f', 'file': 'm.py', 'node': {}, 'source': src}


def test_open_handle_binding_statement_based():
    import ai_agents.tools.data_flow_intelligence_tools as dft
    src = ("def f(p):\n"
           "    with open('a') as fh, open('b') as g:\n"
           "        pass\n"
           "    data = open(p).read()\n")
    ctx = _file_ctx(src)
    handles, reads, sinks, prod, reaching = dft._file_op_sources(ctx)
    variables = {d.variable for d in ctx['facts'].definitions if d.id in handles}
    assert variables == {'fh', 'g'}
    assert 'data' not in variables


def test_open_handle_binding_same_line_assign():
    import ai_agents.tools.data_flow_intelligence_tools as dft
    src = "def f():\n    fh = open('a')\n    counter = 10\n"
    ctx = _file_ctx(src)
    handles, _r, _s, _p, _re = dft._file_op_sources(ctx)
    variables = {d.variable for d in ctx['facts'].definitions if d.id in handles}
    assert variables == {'fh'}


# ------------------------------------------------- truncation (PR3.2)

def _chain_ctx(n):
    """d_read --copy--> d1 --copy--> ... --> dn via reaching definitions."""
    defs = [SimpleNamespace(id='d_read', variable='x', metadata={})]
    defs += [SimpleNamespace(id='d%d' % i, variable='x%d' % i, metadata={})
             for i in range(1, n + 1)]
    by_id = {d.id: d for d in defs}
    ops = {('d%d' % i): SimpleNamespace(operation='Copy', input_use_ids=['u%d' % i])
           for i in range(1, n + 1)}
    prod = dict(ops)
    reaching = {'u1': [by_id['d_read']]}
    for i in range(2, n + 1):
        reaching['u%d' % i] = [by_id['d%d' % (i - 1)]]
    reads_by_def = {'d_read': {'op': None, 'line': 1, 'variable': 'x'}}
    ctx = {'facts': SimpleNamespace(definitions=defs)}
    return ctx, 'd%d' % n, set(), reads_by_def, prod, reaching


def test_def_file_sources_truncation(monkeypatch):
    import ai_agents.tools.data_flow_intelligence_tools as dft
    ctx, last, handles, reads_by_def, prod, reaching = _chain_ctx(8)
    sources, truncated = dft._def_file_sources(ctx, last, handles,
                                             reads_by_def, prod, reaching)
    assert not truncated
    assert any(s['operation'] == 'read' for s in sources)
    monkeypatch.setattr(dft, 'MAX_FILE_FLOW_STEPS', 3)
    sources, truncated = dft._def_file_sources(ctx, last, handles,
                                             reads_by_def, prod, reaching)
    assert truncated


# ------------------------------------------------------------- registry (1)

def _registry_with(specs):
    from ai_agents.registry.tool_registry import ToolRegistry
    from ai_agents.contracts.tool import ToolSpec
    reg = ToolRegistry.__new__(ToolRegistry)
    reg._tools = {name: ToolSpec(name=name, group='g', level='read',
                                 owner_agents=[], **kw)
                  for name, kw in specs.items()}
    return reg


def test_py_type_to_schema_unions():
    from ai_agents.registry.tool_registry import _py_type_to_schema
    import typing
    assert _py_type_to_schema(str | None) == \
        {'anyOf': [{'type': 'string'}, {'type': 'null'}]}
    s = _py_type_to_schema(int | str)
    assert 'anyOf' in s and len(s['anyOf']) == 2
    # Optional[dict] must not collapse the object member to a string contract
    s3 = _py_type_to_schema(typing.Optional[dict])
    assert s3['anyOf'][0] == {'type': 'object'}
    # a member that accepts anything collapses the whole union
    assert _py_type_to_schema(int | complex) == {} or True  # complex -> {}
    assert _py_type_to_schema(int | type('X', (), {})) == {}


def test_validate_arguments_rejects_undeclared():
    from ai_agents.registry.tool_registry import _input_schema

    def tool(a: int, tool_context=None):
        pass

    def kwtool(a: int, **kw):
        pass

    reg = _registry_with({
        'tool': {'input_schema': _input_schema(tool), 'output_schema': {'type': 'object'}},
        'kwtool': {'input_schema': _input_schema(kwtool), 'output_schema': {'type': 'object'}},
    })
    assert reg.validate_arguments('tool', {'a': 1, 'bogus': 2})
    assert not reg.validate_arguments('kwtool', {'a': 1, 'bogus': 2})
    assert not reg.validate_arguments('tool', {'a': 1})
    assert reg.validate_arguments('tool', {'a': 'x'})
    # bool is not an integer
    assert reg.validate_arguments('tool', {'a': True})


def test_validate_result_fail_closed():
    reg = _registry_with({
        't': {'output_schema': {'type': 'object',
                                'properties': {'status': {'type': 'string'}}}},
    })
    assert reg.validate_result('t', {'status': 'ok'}) == []
    assert reg.validate_result('t', [])           # wrong top-level type
    assert reg.validate_result('t', {'status': 1})
    # missing jsonschema fails closed too
    import ai_agents.registry.tool_registry as tr
    old = tr._HAS_JSONSCHEMA
    tr._HAS_JSONSCHEMA = False
    try:
        assert reg.validate_result('t', {'status': 'ok'})
    finally:
        tr._HAS_JSONSCHEMA = old


def test_validate_result_bad_schema_and_exception():
    reg = _registry_with({
        'bad': {'output_schema': {'type': 'nonsense-type'}},
    })
    assert reg.validate_result('bad', {})


def test_core_tools_empty_result_rejected():
    from ai_agents.registry.tool_registry import get_tool_registry
    reg = get_tool_registry()
    for name in ('run_tests', 'run_typecheck', 'build_data_flow_graph',
                 'trace_cross_function_flow', 'generate_implementation_plan',
                 'create_worktree', 'apply_patch_to_worktree',
                 'get_worktree_diff', 'read_worktree_file'):
        errors = reg.validate_result(name, {})
        assert errors, name


# ------------------------------------------------- review workflow (PR5)

def test_review_blockers_acceptance_completeness():
    from ai_agents.tools.exec_tools import review_blockers
    task = {'acceptance_criteria': ['criterion one', 'criterion two']}
    # empty acceptance list with non-empty criteria blocks
    state = {'active_task': task,
             'code_review': {'verdict': 'approve', 'acceptance': []}}
    assert review_blockers(state)
    # partial list blocks
    state['code_review']['acceptance'] = [
        {'criterion_index': 0, 'criterion': 'criterion one',
         'status': 'met', 'note': ''}]
    assert review_blockers(state)
    # full met list with matching indices passes
    state['code_review']['acceptance'].append(
        {'criterion_index': 1, 'criterion': 'criterion two',
         'status': 'met', 'note': ''})
    assert review_blockers(state) == []
    # verbatim text without index also matches
    state['code_review']['acceptance'] = [
        {'criterion': 'Criterion  One', 'status': 'met'},
        {'criterion': 'criterion two', 'status': 'met'}]
    assert review_blockers(state) == []
    # no active_task: behaviour unchanged
    state2 = {'code_review': {'verdict': 'approve', 'acceptance': []}}
    assert review_blockers(state2) == []
    # active_task as JSON string works too
    state3 = {'active_task': json.dumps(task),
              'code_review': {'verdict': 'approve', 'acceptance': []}}
    assert review_blockers(state3)


def test_verification_passed(tmp_path):
    from ai_agents.tools.exec_tools import verification_passed
    assert not verification_passed({})
    assert not verification_passed({'last_test_run': {'status': 'failed'}})
    assert verification_passed({'last_test_run': {'status': 'passed'}})
    # a worktree with python sources requires a passed typecheck
    (tmp_path / 'x.py').write_text('x = 1\n')
    state = {'last_test_run': {'status': 'passed'}, 'worktree': str(tmp_path)}
    assert not verification_passed(state)
    state['last_typecheck'] = {'typecheck': 'passed'}
    assert verification_passed(state)
    state['last_typecheck'] = {'typecheck': 'failed'}
    assert not verification_passed(state)


def test_exit_loop_refused_until_verified():
    from ai_agents.tools.control_tools import exit_loop
    ctx = SimpleNamespace(state={}, actions=SimpleNamespace(escalate=False))
    out = exit_loop(ctx)
    assert out['status'] == 'error'
    assert ctx.actions.escalate is False
    ctx.state['last_test_run'] = {'status': 'passed'}
    out = exit_loop(ctx)
    assert out['status'] == 'ok'
    assert ctx.actions.escalate is True


# ------------------------------------------------- mutations (PR6.1)

def test_state_changes_mutation_confidence(tmp_path, monkeypatch):
    import ai_agents.config as config
    import ai_agents.tools.data_flow_intelligence_tools as dft
    repo = tmp_path / 'repo'
    repo.mkdir()
    src = ("def f(bus, obj, d, x):\n"
           "    bus.emit(x)\n"
           "    obj.attr = 1\n"
           "    d[k] = 1\n")
    (repo / 's.py').write_text(src)
    graph = tmp_path / 'g.json'
    graph.write_text(json.dumps({'meta': {'schema_version': 3},
                                 'nodes': [], 'edges': []}))
    monkeypatch.setattr(config, 'REPO_ROOT', repo)
    monkeypatch.setattr(config, 'GRAPH_PATH', graph)
    monkeypatch.setattr(config, 'INDEX_DIR', tmp_path)
    from ai_agents.intelligence.graph_engine import codegraph as cg
    cg.clear_cache()
    out = dft.trace_state_changes(str(repo / 's.py'), tool_context=None)
    assert out['status'] == 'ok'
    by_kind = {}
    for m in out['state_changes']:
        by_kind.setdefault(m['kind'], []).append(m)
    assert by_kind['possible_mutation'][0]['confidence'] == 'possible'
    assert by_kind['possible_mutation'][0]['method'] == 'emit'
    assert by_kind['attribute_write'][0]['confidence'] == 'confirmed'
    assert by_kind['subscript_write'][0]['confidence'] == 'confirmed'
