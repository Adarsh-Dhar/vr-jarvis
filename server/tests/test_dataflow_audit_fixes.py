"""Tests for the data-flow audit fixes: approval gate, call binding,
callee resolution helpers, facts cache keys, file-op/state-change scoping
and origin status."""
import ast
import json
from pathlib import Path

import pytest


def _fn(src):
    return ast.parse(src).body[0]


# ---------------------------------------------------------------- review gate

def test_review_blockers_only_met_clears_acceptance():
    from ai_agents.tools.exec_tools import review_blockers
    base = {'code_review': {'verdict': 'approve', 'findings': [], 'acceptance': []}}
    assert review_blockers(dict(base), require_review=True) == []
    for status in ('not_met', 'unknown', '', 'maybe'):
        state = {'code_review': {'verdict': 'approve', 'findings': [],
                                 'acceptance': [{'criterion': 'c', 'status': status}]}}
        assert review_blockers(state), status
    state = {'code_review': {'verdict': 'approve', 'findings': [],
                             'acceptance': [{'criterion': 'c'}]}}
    assert review_blockers(state)
    state = {'code_review': {'verdict': 'approve', 'findings': [],
                             'acceptance': ['not-an-object']}}
    assert review_blockers(state)
    state = {'code_review': {'verdict': 'approve', 'findings': [],
                             'acceptance': [{'criterion': 'c', 'status': 'met'}]}}
    assert review_blockers(state) == []


# ------------------------------------------------------------- call binding

def test_bind_call_positional_and_keyword():
    from ai_agents.intelligence.dataflow.call_binding import bind_call
    fn = _fn('def f(a, b=2, *args, c, **kw):\n    pass\n')
    shape = {'callee': 'f',
             'positional': [{'kind': 'positional', 'name': None, 'starred': False,
                             'use_ids': ['u1'], 'operation_id': None}],
             'keywords': [{'kind': 'keyword', 'name': 'c', 'starred': False,
                           'use_ids': ['u2'], 'operation_id': None}]}
    out = bind_call(shape, fn)
    assert out['status'] == 'ok'
    bound = {b['param']: b for b in out['bindings'] if b['status'] == 'bound'}
    assert bound['a']['arg_index'] == 0
    assert bound['c']['keyword'] == 'c'
    assert 'b' in out['defaults']


def test_bind_call_method_skips_self():
    from ai_agents.intelligence.dataflow.call_binding import bind_call
    fn = _fn('class A:\n    def m(self, x):\n        pass\n')
    meth = fn.body[0]
    shape = {'callee': 'A.m',
             'positional': [{'kind': 'positional', 'name': None, 'starred': False,
                             'use_ids': ['u1'], 'operation_id': None}],
             'keywords': []}
    out = bind_call(shape, meth, is_method=True)
    assert out['status'] == 'ok'
    assert out['bindings'][0]['param'] == 'x'
    # without is_method the first arg would bind to self
    out2 = bind_call(shape, meth, is_method=False)
    assert out2['bindings'][0]['param'] == 'self'


def test_bind_call_starred_and_unknown_kwarg():
    from ai_agents.intelligence.dataflow.call_binding import bind_call
    fn = _fn('def f(a, *args):\n    pass\n')
    shape = {'callee': 'f',
             'positional': [{'kind': 'positional', 'name': None, 'starred': True,
                             'use_ids': ['u1'], 'operation_id': None}],
             'keywords': [{'kind': 'keyword', 'name': 'zzz', 'starred': False,
                           'use_ids': ['u2'], 'operation_id': None}]}
    out = bind_call(shape, fn)
    assert out['status'] == 'partial'
    params = {b['param']: b['status'] for b in out['bindings']}
    assert params['args'] == 'bound'
    assert any(s == 'unresolved' for s in params.values())
    assert out['unbound_arguments']


def test_bind_call_no_signature_unresolved():
    from ai_agents.intelligence.dataflow.call_binding import bind_call
    out = bind_call({'positional': [], 'keywords': []}, None)
    assert out['status'] == 'unresolved'


# ------------------------------------------------- evaluator call_shape

def test_call_shape_recorded_on_call_op():
    from ai_agents.intelligence.dataflow.recursive_expression_evaluator import (
        RecursiveExpressionEvaluator, ExpressionEvaluationContext)
    from ai_agents.intelligence.dataflow.models import DefUseFacts
    from ai_agents.intelligence.dataflow.ids import IdAllocator

    src = 'def f(a, b):\n    return g(a, key=b)\n'
    tree = ast.parse(src)
    ret = tree.body[0].body[0]
    call = ret.value
    facts = DefUseFacts(function_id='f', file='m.py')
    ids = IdAllocator('f')
    ctx = ExpressionEvaluationContext(
        function_id='f', file='m.py', local_vars={'a', 'b'},
        cfg_node_map={}, ast_index=None, facts=facts, ids=ids)
    ev = RecursiveExpressionEvaluator(ctx)
    ev.evaluate(call)
    op = [o for o in facts.operations if o.operation == 'Call'][0]
    shape = op.metadata['call_shape']
    assert shape['callee'] == 'g'
    assert len(shape['positional']) == 1
    assert shape['keywords'][0]['name'] == 'key'
    assert shape['positional'][0]['use_ids']


# ------------------------------------------------------------- cache keys

def test_facts_cache_key_changes_with_source(tmp_path, monkeypatch):
    import ai_agents.config as config
    import ai_agents.tools.data_flow_intelligence_tools as dft

    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'm.py').write_text('def f():\n    return 1\n')
    graph = tmp_path / 'g.json'
    graph.write_text('{}')
    monkeypatch.setattr(config, 'REPO_ROOT', repo)
    monkeypatch.setattr(config, 'GRAPH_PATH', graph)
    ctx = {'node': {'id': 'm.py::f'}, 'file': 'm.py',
           'source': 'def f():\n    return 1\n'}
    k1 = dft._facts_cache_key(ctx)
    ctx2 = dict(ctx, source='def f():\n    return 2\n')
    assert dft._facts_cache_key(ctx2) != k1
    dft.clear_facts_cache()
    assert dft._FACTS_CACHE == {}


# ------------------------------------------------------- state-change scope

def test_state_changes_use_dotted_qualnames(tmp_path, monkeypatch):
    import ai_agents.config as config
    import ai_agents.tools.data_flow_intelligence_tools as dft

    repo = tmp_path / 'repo'
    repo.mkdir()
    src = ('class Store:\n'
           '    def add(self):\n'
           '        def inner():\n'
           '            self.count += 1\n'
           '        self.total = 0\n')
    (repo / 's.py').write_text(src)
    graph = tmp_path / 'g.json'
    graph.write_text(json.dumps({'meta': {'schema_version': 3}, 'nodes': [], 'edges': []}))
    monkeypatch.setattr(config, 'REPO_ROOT', repo)
    monkeypatch.setattr(config, 'GRAPH_PATH', graph)
    monkeypatch.setattr(config, 'INDEX_DIR', tmp_path)
    from ai_agents.intelligence.graph_engine import codegraph as cg
    cg.clear_cache()

    out = dft.trace_state_changes(str(repo / 's.py'), tool_context=None)
    assert out['status'] == 'ok'
    scopes = {m['function'] for m in out['state_changes']}
    assert 'Store.add.inner' in scopes
    assert 'Store.add' in scopes
    inner = [m for m in out['state_changes'] if m['function'] == 'Store.add.inner']
    assert inner and inner[0]['kind'] == 'augmented_assignment' or \
        inner and inner[0]['kind'] in ('attribute_write', 'augmented')


# ------------------------------------------------------------ schema check

def test_validate_arguments_nested():
    from ai_agents.registry.tool_registry import ToolRegistry
    reg = ToolRegistry.__new__(ToolRegistry)
    reg._type_errors = ToolRegistry._type_errors
    schema = {'type': 'object',
              'properties': {'items': {'type': 'array',
                                       'items': {'type': 'object',
                                                 'properties': {'n': {'type': 'integer'}},
                                                 'required': ['n']}}},
              'required': []}
    assert reg._type_errors({'items': [{'n': 1}]}, schema, 'arg x') == []
    errs = reg._type_errors({'items': [{'n': 's'}]}, schema, 'arg x')
    assert errs and 'integer' in errs[0]
    errs = reg._type_errors({'items': [{'m': 1}]}, schema, 'arg x')
    assert any('required' in e for e in errs)
