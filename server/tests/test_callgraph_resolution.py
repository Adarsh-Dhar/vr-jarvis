"""Strict tests for call-graph resolution using the callgraph_shop fixture.

These tests assert exact resolution outcomes — no skipped cases, no
"unresolved is acceptable" fallbacks.
"""
import json
import pytest
from pathlib import Path
from ai_agents import config
from ai_agents.intelligence.graph_engine.indexer import index_repo


@pytest.fixture
def shop_graph(tmp_path):
    """Index the callgraph_shop fixture as a temporary repository."""
    fixture_dir = Path(__file__).parent / "fixtures" / "callgraph_shop"
    repo_dir = tmp_path / "callgraph_shop"
    repo_dir.mkdir()
    for py_file in fixture_dir.glob("*.py"):
        (repo_dir / py_file.name).write_text(py_file.read_text())

    original = config.REPOSITORY_DIR
    config.REPOSITORY_DIR = tmp_path
    try:
        yield index_repo("callgraph_shop")
    finally:
        config.REPOSITORY_DIR = original


def _node(graph, node_id):
    return next((n for n in graph['nodes'] if n['id'] == node_id), None)


def _call_edges(graph, src):
    return [e for e in graph['edges'] if e.get('src') == src and e.get('type') == 'calls']


def _call_site(graph, callsite_id):
    return next((c for c in graph['call_sites'] if c['id'] == callsite_id), None)


def test_schema_version_and_call_sites(shop_graph):
    assert shop_graph['meta']['schema_version'] == 3
    assert len(shop_graph['call_sites']) > 0
    # every call site has source-location evidence
    for cs in shop_graph['call_sites']:
        assert cs['file'] and cs['line'] > 0
        assert cs['resolution'] in (
            'static_resolved', 'polymorphic', 'ambiguous',
            'unresolved', 'external', 'dynamic')


def test_duplicate_validate_resolution(shop_graph):
    """Both validate() calls in checkout resolve to payments.validate via import."""
    checkout = 'main.py::checkout'
    edges = _call_edges(shop_graph, checkout)
    validate_edges = [e for e in edges if e['dst'] == 'payments.py::validate']
    # two separate call sites (lines 11 and 24) -> two distinct edges
    assert len(validate_edges) == 2
    callsite_ids = {e['callsite_id'] for e in validate_edges}
    assert callsite_ids == {'main.py:11:4', 'main.py:24:4'}
    for e in validate_edges:
        assert e['resolution'] == 'static_resolved'
        assert e['kind'] == 'confirmed'
        assert e['confidence'] == 1.0


def test_aliased_import_resolution(shop_graph):
    """auth_validate -> authentication.validate, validate_order -> orders.validate."""
    edges = _call_edges(shop_graph, 'main.py::checkout')
    by_dst = {e['dst']: e for e in edges}
    assert by_dst['authentication.py::validate']['callsite_id'] == 'main.py:14:4'
    assert by_dst['orders.py::validate']['callsite_id'] == 'main.py:17:4'
    assert by_dst['authentication.py::validate']['resolution'] == 'static_resolved'
    assert by_dst['orders.py::validate']['resolution'] == 'static_resolved'


def test_constructor_and_typed_receiver(shop_graph):
    """payment = CardPayment(); payment.process() resolves to CardPayment.process."""
    edges = _call_edges(shop_graph, 'main.py::checkout')
    ctor = next(e for e in edges if e['callsite_id'] == 'main.py:20:14')
    assert ctor['dst'] == 'payments.py::CardPayment'
    assert ctor['resolution'] == 'static_resolved'

    process = next(e for e in edges if e['callsite_id'] == 'main.py:21:4')
    assert process['dst'] == 'payments.py::CardPayment.process'
    assert process['resolution'] == 'static_resolved'
    assert process['call_type'] == 'method'


def test_self_and_super_resolution(shop_graph):
    """super().process() in CardPayment resolves to Payment.process."""
    edges = _call_edges(shop_graph, 'payments.py::CardPayment.process')
    super_edge = next(e for e in edges if e['callsite_id'] == 'payments.py:24:15')
    assert super_edge['dst'] == 'payments.py::Payment.process'
    assert super_edge['resolution'] == 'static_resolved'
    assert super_edge['resolution_method'] == 'mro_super'


def test_inherited_direct_call(shop_graph):
    """Payment.process calls auth_validate -> authentication.validate."""
    edges = _call_edges(shop_graph, 'payments.py::Payment.process')
    assert any(e['dst'] == 'authentication.py::validate' for e in edges)


def test_dynamic_callable_param(shop_graph):
    """func() inside twice() is dynamic — no fabricated edge."""
    cs1 = _call_site(shop_graph, 'main.py:29:4')
    cs2 = _call_site(shop_graph, 'main.py:30:4')
    assert cs1['resolution'] == 'dynamic'
    assert cs2['resolution'] == 'dynamic'
    # no calls edges from twice
    assert _call_edges(shop_graph, 'main.py::twice') == []


def test_external_library_call(shop_graph):
    """requests.get() is classified external — no internal edge."""
    cs = _call_site(shop_graph, 'main.py:45:11')
    assert cs['resolution'] == 'external'
    assert cs['callee_name'] == 'get'
    assert cs['receiver'] == 'requests'
    assert _call_edges(shop_graph, 'main.py::fetch_data') == []


def test_recursive_call(shop_graph):
    """recursive(n-1) resolves to itself with its own call site."""
    edges = _call_edges(shop_graph, 'main.py::recursive')
    self_edge = next(e for e in edges if e['dst'] == 'main.py::recursive')
    assert self_edge['callsite_id'] == 'main.py:39:4'
    assert self_edge['resolution'] == 'static_resolved'


def test_builtin_calls_external(shop_graph):
    """len() calls are external, not internal edges."""
    for csid in ('orders.py:6:11', 'payments.py:15:15', 'payments.py:28:15', 'payments.py:41:11'):
        cs = _call_site(shop_graph, csid)
        assert cs is not None, f'missing call site {csid}'
        assert cs['resolution'] == 'external'


def test_no_fabricated_edges(shop_graph):
    """Unresolved/dynamic/external call sites never produce call edges."""
    bad = [c for c in shop_graph['call_sites']
           if c['resolution'] in ('unresolved', 'dynamic', 'external')
           and c['targets']]
    assert bad == []
    # every 'calls' edge must be static_resolved and have a real callsite
    for e in shop_graph['edges']:
        if e.get('type') == 'calls':
            assert e.get('resolution') == 'static_resolved'
            assert e.get('callsite_id')


def test_expected_edges_match(shop_graph):
    """Ground-truth assertion against expected_edges.json."""
    fixture = Path(__file__).parent / "fixtures" / "callgraph_shop" / "expected_edges.json"
    expected = json.loads(fixture.read_text())['callgraph_shop']

    # multiple call sites may share (src, dst); match on callsite line
    call_edges = [e for e in shop_graph['edges'] if e.get('type') == 'calls']
    actual_sites = {c['id']: c for c in shop_graph['call_sites']}

    for exp in expected['edges']:
        src, dst = exp['src'], exp['dst']
        if dst == 'external':
            src_file = src.split('::')[0]
            cs = next((c for c in shop_graph['call_sites']
                       if c['file'] == src_file and c['line'] == exp['line']
                       and c['caller_node_id'] == src), None)
            assert cs is not None, f"missing call site for {src} line {exp['line']}"
            assert cs['resolution'] == 'external'
            continue
        edge = next((e for e in call_edges
                     if e['src'] == src and e['dst'] == dst
                     and actual_sites.get(e.get('callsite_id'), {}).get('line') == exp['line']), None)
        assert edge is not None, f"missing confirmed edge {src} -> {dst} at line {exp['line']}"
        assert edge['resolution'] == exp['resolution']
        cs = actual_sites.get(edge['callsite_id'])
        assert cs is not None
        assert cs['line'] == exp['line']

    # every expected node exists
    for node in expected['nodes']:
        assert _node(shop_graph, node['id']) is not None, f"missing node {node['id']}"


def test_subgraph_preserves_parallel_call_sites(shop_graph, tmp_path):
    """P0: two validate() call sites from checkout must both survive subgraph()."""
    import json as _json
    from ai_agents.intelligence.graph_engine.codegraph import CodeGraph
    gp = tmp_path / 'graph.json'
    gp.write_text(_json.dumps(shop_graph))
    g = CodeGraph(gp)
    sub = g.subgraph(['main.py::checkout', 'payments.py::validate'], include_edges=True)
    call_edges = [e for e in sub['edges'] if e.get('type') == 'calls'
                  and e['dst'] == 'payments.py::validate']
    assert len(call_edges) == 2
    assert {e['callsite_id'] for e in call_edges} == {'main.py:11:4', 'main.py:24:4'}
