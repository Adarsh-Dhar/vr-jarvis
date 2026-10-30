'''Layer 1: property tests on random graphs. These find edge cases hand-written cases miss.'''
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.harness.context import FakeToolContext, installed_graph
from tests.harness.pkg import mod

gt = mod('tools.graph_tools')


@st.composite
def graphs(draw):
    n = draw(st.integers(min_value=1, max_value=18))
    ids = ['n%d' % i for i in range(n)]
    edge = st.tuples(st.integers(0, n - 1), st.integers(0, n - 1),
                     st.sampled_from(['calls', 'imports']), st.sampled_from(['confirmed', 'inferred']))
    raw = draw(st.lists(edge, max_size=40))
    nodes = [{'id': i, 'name': i, 'kind': 'function', 'file': 'src/%s.ts' % i, 'start': 1, 'end': 3,
              'cluster': 'c', 'complexity': 1, 'churn': 0} for i in ids]
    edges = [{'src': ids[a], 'dst': ids[b], 'type': t, 'kind': k} for a, b, t, k in raw if a != b]
    return {'nodes': nodes, 'edges': edges, 'tests': [], 'coverage': {}}


SETTINGS = dict(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@settings(**SETTINGS)
@given(graphs())
def test_tools_agree_with_oracle_on_random_graphs(graph):
    with installed_graph(graph, write_sources=False) as env:
        ctx = FakeToolContext()
        for node in env.oracle.ids:
            for depth in (1, 3):
                callers = {c['id']: c['depth'] for c in gt.get_callers(node, ctx, depth)['callers']}
                assert callers == dict(env.oracle.callers(node, depth))
                callees = {c['id']: c['depth'] for c in gt.get_callees(node, ctx, depth)['callees']}
                assert callees == dict(env.oracle.callees(node, depth))
                deps = {c['id']: c['depth'] for c in gt.get_dependents(node, ctx, depth)['dependents']}
                assert deps == dict(env.oracle.dependents(node, depth))


@settings(**SETTINGS)
@given(graphs())
def test_structural_properties(graph):
    with installed_graph(graph, write_sources=False) as env:
        ctx = FakeToolContext()
        for node in env.oracle.ids:
            callees = [c['id'] for c in gt.get_callees(node, ctx, 1)['callees']]
            assert len(callees) == len(set(callees)) and node not in callees       # unique, no self
            for other in callees:                                                   # symmetry
                assert node in [c['id'] for c in gt.get_callers(other, ctx, 1)['callers']]
            small = {c['id'] for c in gt.get_dependents(node, ctx, 1)['dependents']}
            large = {c['id'] for c in gt.get_dependents(node, ctx, 4)['dependents']}
            assert small <= large                                                   # depth is monotonic
            callers = {c['id'] for c in gt.get_callers(node, ctx, 1)['callers']}
            assert callers <= small                                                 # dependents include callers


@settings(**SETTINGS)
@given(graphs())
def test_trace_path_properties(graph):
    with installed_graph(graph, write_sources=False) as env:
        ctx = FakeToolContext()
        ids = env.oracle.ids
        for src in ids[:6]:
            for dst in ids[:6]:
                r = gt.trace_path(src, dst, ctx)
                expected = env.oracle.shortest(src, dst)
                if expected is None:
                    assert r['status'] == 'no_path'
                else:
                    assert len(r['path']) - 1 == expected
                    for hop in r['hops']:
                        assert env.oracle.has_edge(hop['from'], hop['to'])
