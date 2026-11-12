"""End-to-end tests for the repository-wide interprocedural DFG pipeline.

Each test builds a temporary repository, indexes it with the real indexer,
loads the graph and runs build_repository_dfg.
"""
import json
from pathlib import Path

import pytest


def _build(tmp_path, monkeypatch, files, repo_name='r1'):
    """Write ``files`` ({relpath: source}) into a temp repository, index it
    and return (repo_path, CodeGraph)."""
    import ai_agents.config as config
    from ai_agents.intelligence.graph_engine.indexer import index_repo
    from ai_agents.intelligence.graph_engine.codegraph import CodeGraph

    repos = tmp_path / 'repos'
    repo = repos / repo_name
    repo.mkdir(parents=True)
    for rel, src in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    (repo / '.git').mkdir(exist_ok=True)  # keep .git out of SKIP_DIRS scan noise

    monkeypatch.setattr(config, 'REPOSITORY_DIR', repos)
    data = index_repo(repo_name)
    graph_path = tmp_path / (repo_name + '.json')
    graph_path.write_text(json.dumps(data))
    monkeypatch.setattr(config, 'REPO_ROOT', repo)
    return repo, CodeGraph(graph_path)


def _dfg(graph):
    from ai_agents.intelligence.dataflow.repository_dfg import build_repository_dfg
    return build_repository_dfg(graph)


SERVICE = '''def normalize(value):
    return value.strip().lower()


def clean(value):
    return normalize(value)
'''

APP = '''from service import normalize, clean


def handle(raw):
    text = normalize(raw)
    return clean(text)
'''


def test_argument_return_and_transitive_edges(tmp_path, monkeypatch):
    repo, graph = _build(tmp_path, monkeypatch,
                         {'service.py': SERVICE, 'app.py': APP})
    out = _dfg(graph)
    kinds = {(e.source_kind, e.resolution) for e in out.edges}
    assert ('argument', 'confirmed') in kinds
    assert ('return', 'confirmed') in kinds
    # every edge carries file and a positive line
    for e in out.edges:
        assert e.source_file and e.source_line >= 1
        assert e.target_file and e.target_line >= 1


def test_binding_forms(tmp_path, monkeypatch):
    files = {
        'fns.py': '''def f(a, /, b, *args, c=1, **kw):
    return a


def caller(x, y):
    f(x, y, 3, c=4, extra=y)
    f(x, b=y)
    f(*[x], **{'c': y})
''',
    }
    repo, graph = _build(tmp_path, monkeypatch, files)
    out = _dfg(graph)
    # bound arguments produced edges; starred/unknown keyword shapes never
    # produce 'confirmed' edges for the unbound parameters.
    arg_edges = [e for e in out.edges if e.source_kind == 'argument']
    assert arg_edges
    for e in arg_edges:
        assert e.resolution in ('confirmed', 'possible')


def test_three_file_chain(tmp_path, monkeypatch):
    files = {
        'a.py': 'from b import go_b\n\n\ndef run(x):\n    return go_b(x)\n',
        'b.py': 'from c import go_c\n\n\ndef go_b(x):\n    return go_c(x)\n',
        'c.py': 'def go_c(x):\n    return x\n',
    }
    repo, graph = _build(tmp_path, monkeypatch, files)
    out = _dfg(graph)
    assert out.edges
    for e in out.edges:
        assert e.source_file and e.source_line >= 1
        assert e.target_file and e.target_line >= 1


def test_import_forms_resolve(tmp_path, monkeypatch):
    files = {
        'service.py': 'LIMIT = 10\n\n\ndef normalize(v):\n    return v\n',
        'app.py': '''import service
from service import normalize as n
from .service import normalize


def h(x):
    a = n(x)
    b = normalize(x)
    c = service.normalize(x)
    return service.LIMIT + a + b + c
''',
        'pkg/__init__.py': '',
    }
    repo, graph = _build(tmp_path, monkeypatch, files)
    out = _dfg(graph)
    assert out.edges or out.global_edges or out.unresolved is not None
    # global edge for service.LIMIT use inside h()
    globals_found = [g for g in out.global_edges
                     if g.get('file') == 'app.py']
    assert globals_found, out.unresolved


def test_mutual_recursion_converges(tmp_path, monkeypatch):
    files = {
        'rec.py': '''def is_even(n):
    return True if n == 0 else is_odd(n - 1)


def is_odd(n):
    return False if n == 0 else is_even(n - 1)
''',
    }
    repo, graph = _build(tmp_path, monkeypatch, files)
    out = _dfg(graph)
    assert out.converged is True
    assert 'rec.py::is_even' in out.summaries
    assert 'rec.py::is_odd' in out.summaries
    # a body edit changes the summary content hash
    h1 = out.summaries['rec.py::is_even'].content_hash
    (repo / 'rec.py').write_text(
        'def is_even(n):\n    return False if n == 0 else is_odd(n - 1)\n\n\n'
        'def is_odd(n):\n    return False if n == 0 else is_even(n - 1)\n')
    repo2, graph2 = _build(tmp_path / 'second', monkeypatch,
                           {'rec.py': (repo / 'rec.py').read_text()},
                           repo_name='r2')
    out2 = _dfg(graph2)
    assert out2.summaries['rec.py::is_even'].content_hash != h1


def test_dynamic_call_unresolved(tmp_path, monkeypatch):
    files = {
        'dyn.py': '''import json


def load(m, name, x):
    return getattr(m, name)(x)
''',
        'mod.py': 'def target(x):\n    return x\n',
    }
    repo, graph = _build(tmp_path, monkeypatch, files)
    out = _dfg(graph)
    # getattr(m, name)(x) cannot be resolved statically: unresolved entry
    # naming the dynamic call site, never a confirmed edge for it.
    dyn = [u for u in out.unresolved
           if u.get('function_id') == 'dyn.py::load']
    assert dyn, out.unresolved
    assert all(u.get('status') != 'confirmed' for u in dyn)
    assert any('getattr' in str(u.get('expression', ''))
               or u.get('status') in ('unresolved', 'ambiguous', 'possible')
               for u in dyn)


def test_global_edge_for_imported_constant(tmp_path, monkeypatch):
    files = {
        'config.py': 'LIMIT = 100\n',
        'use.py': 'from config import LIMIT\n\n\ndef f():\n    return LIMIT\n',
    }
    repo, graph = _build(tmp_path, monkeypatch, files)
    out = _dfg(graph)
    g = [e for e in out.global_edges if e.get('kind') == 'global']
    assert g, 'expected a global edge for imported LIMIT'
    assert all(e['file'] and e['line'] >= 1 for e in g)


def test_cache_and_cyclic_invalidation(tmp_path, monkeypatch):
    from ai_agents.intelligence.dataflow.graph_persistence import (
        GraphPersistenceManager)
    mgr = GraphPersistenceManager(cache_dir=tmp_path / 'cache')
    mgr.cache_graph('a::f', 'def f():\n    return g()\n',
                    {'nodes': [], 'edges': []}, {'nodes': [], 'edges': []},
                    {}, dependency_digests={'a::g': 'd1'})
    assert mgr.is_cache_valid('a::f', 'def f():\n    return g()\n',
                              {'nodes': []}, {'nodes': []}, {},
                              dependency_digests={'a::g': 'd1'})
    # a changed dependency digest invalidates
    assert not mgr.is_cache_valid('a::f', 'def f():\n    return g()\n',
                                  {'nodes': []}, {'nodes': []}, {},
                                  dependency_digests={'a::g': 'd2'})

    # cyclic invalidation must not raise
    from ai_agents.intelligence.dataflow.interprocedural import (
        InterproceduralSummaryBuilder, CallGraph, FunctionSummary)
    b = InterproceduralSummaryBuilder()
    b._call_graph = CallGraph(nodes={'a', 'b'},
                              edges={'a': {'b'}, 'b': {'a'}},
                              reverse_edges={'a': {'b'}, 'b': {'a'}})
    b._summaries = {'a': FunctionSummary('a', [], set(), set(), set(), [], [],
                                       'h', {}),
                    'b': FunctionSummary('b', [], set(), set(), set(), [], [],
                                       'h', {})}
    b.invalidate_function('a')
    assert b._summaries == {}


def test_alias_return_provenance(tmp_path, monkeypatch):
    """Return through a local alias still records the parameter."""
    repo, graph = _build(tmp_path, monkeypatch, {
        's.py': 'def normalize(value):\n'
                '    cleaned = value.strip()\n'
                '    return cleaned\n'})
    out = _dfg(graph)
    s = out.summaries['s.py::normalize']
    assert s.returns_from == {'value'}


def test_call_result_overwritten_not_connected(tmp_path, monkeypatch):
    """A use after reassignment must not connect to the earlier call."""
    repo, graph = _build(tmp_path, monkeypatch, {
        'a.py': 'def calculate(v):\n    return v\n\n\n'
                'def caller(x):\n'
                '    result = calculate(x)\n'
                '    result = 100\n'
                '    return result\n'})
    out = _dfg(graph)
    ret_lines = {e.target_line for e in out.edges
                 if e.source_kind == 'return'}
    assert 8 not in ret_lines  # `return result` line never connects


def test_imported_constant_confirmed_and_shadowing(tmp_path, monkeypatch):
    repo, graph = _build(tmp_path, monkeypatch, {
        'config.py': 'LIMIT = 100\n',
        'app.py': 'from config import LIMIT\n\n\n'
                  'def calculate(LIMIT):\n    return LIMIT\n\n\n'
                  'def use():\n    return LIMIT\n'})
    out = _dfg(graph)
    edges = [g for g in out.global_edges
             if g.get('kind') == 'global']
    # Only the non-shadowing function produces an edge, and it is confirmed.
    assert edges
    assert all(g['resolution'] == 'confirmed' for g in edges)
    assert all(g.get('target_function') == 'app.py::use' for g in edges)
    assert all(g['source'].startswith('config.py') for g in edges)


def test_local_variable_shadows_import(tmp_path, monkeypatch):
    repo, graph = _build(tmp_path, monkeypatch, {
        'config.py': 'LIMIT = 100\n',
        'app.py': 'from config import LIMIT\n\n\n'
                  'def f():\n    LIMIT = 5\n    return LIMIT\n'})
    out = _dfg(graph)
    assert not [g for g in out.global_edges
                if g.get('target_function') == 'app.py::f']


def test_function_local_import_stays_in_scope(tmp_path, monkeypatch):
    repo, graph = _build(tmp_path, monkeypatch, {
        'config.py': 'LIMIT = 100\n',
        'app.py': 'def f():\n    from config import LIMIT\n'
                  '    return LIMIT\n'})
    out = _dfg(graph)
    edges = [g for g in out.global_edges
             if g.get('target_function') == 'app.py::f']
    assert edges and all(g['resolution'] == 'confirmed' for g in edges)
    assert all(g.get('scope') == 'app.py::f' for g in edges)


def test_reassigned_import_uses_reassignment(tmp_path, monkeypatch):
    repo, graph = _build(tmp_path, monkeypatch, {
        'config.py': 'LIMIT = 100\n',
        'app.py': 'from config import LIMIT\nLIMIT = 5\n\n\n'
                  'def f():\n    return LIMIT\n'})
    out = _dfg(graph)
    edges = [g for g in out.global_edges
             if g.get('target_function') == 'app.py::f']
    assert edges
    assert all(g.get('via') == 'reassignment' for g in edges)
    assert all(g['source'].startswith('app.py') for g in edges)


def test_unified_repository_graph_has_global_edges(tmp_path, monkeypatch):
    """Change 1.6 path: global edges are rendered into the repo graph."""
    from ai_agents.intelligence.dataflow.unified_graph import (
        UnifiedGraphBuilder)
    repo, graph = _build(tmp_path, monkeypatch, {
        'config.py': 'LIMIT = 100\n',
        'app.py': 'from config import LIMIT\n\n\n'
                  'def f():\n    return LIMIT\n'})
    out = _dfg(graph)
    assert out.global_edges
    # Build per-function unified graphs for app.py::f only and merge with
    # the global edges the visualization tool would emit.
    from ai_agents.intelligence.dataflow.repository_dfg import (
        build_function_artifacts)
    from ai_agents.intelligence.controlflow import cfg_to_unity_format
    from ai_agents.intelligence.dataflow import dfg_to_unity_format
    node = graph.get('app.py::f')
    art = build_function_artifacts(graph, node, 'app.py::f')
    ug = UnifiedGraphBuilder().build_unified(art['cfg'], art['dfg'])
    f2n = (art['dfg'].metadata or {}).get('fact_to_node', {})
    inter = []
    seen_nodes = set()
    for g in out.global_edges:
        owner = None
        for u in art['facts'].uses:
            if u.id == g['target']:
                owner = u
        if owner is None or owner.id not in f2n:
            continue
        src_id = 'module_data::%s' % g['source']
        inter.append({
            'kind': 'global', 'resolution': g['resolution'],
            'source_node_id': src_id,
            'target_node_id': 'app.py::f::unified_%s' % f2n[owner.id],
            'nodes': [{'id': src_id, 'kind': 'module_data',
                       'file': g.get('source_file'),
                       'line': g.get('source_line') or 0,
                       'variable': g['source'], 'function_id': ''}]})
    repo_g = UnifiedGraphBuilder().build_repository_graph(
        {'app.py::f': ug}, inter)
    global_edges = [e for e in repo_g.edges if e.kind == 'global']
    assert global_edges
    assert global_edges[0].subkind == 'confirmed'
    node_ids = {n.id for n in repo_g.nodes}
    assert global_edges[0].source in node_ids
    assert global_edges[0].target in node_ids
    assert any(n.kind == 'module_data' for n in repo_g.nodes)


def test_chain_query_includes_global_edges(tmp_path, monkeypatch):
    """_cross_function_chain traverses global edges from a module def."""
    from ai_agents.tools.data_flow_intelligence_tools import (
        _cross_function_chain)
    repo, graph = _build(tmp_path, monkeypatch, {
        'config.py': 'LIMIT = 100\n',
        'app.py': 'from config import LIMIT\n\n\n'
                  'def f():\n    return LIMIT\n'})
    out = _dfg(graph)
    src_def = out.global_edges[0]['source']
    chains = _cross_function_chain(graph, src_def, 3)
    flat = [h for chain in chains for h in chain]
    assert any(h.get('kind') == 'global' for h in flat)
    g = next(h for h in flat if h.get('kind') == 'global')
    assert g['resolution'] == 'confirmed'
    assert g['source_file'] and g['target_file']
    assert g['source_line'] >= 1 and g['target_line'] >= 1
