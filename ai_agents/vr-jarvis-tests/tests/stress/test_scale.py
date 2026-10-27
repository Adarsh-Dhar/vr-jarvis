'''Layer 5: scale. Tools must stay fast and bounded on graphs of 5k, 20k and 50k nodes.'''
import json
import random
import time
import tracemalloc

import pytest

from tests.harness.context import FakeToolContext, installed_graph
from tests.harness.graphs import synthetic_graph
from tests.harness.metrics import LATENCY_FACTOR, SCALE, summarize
from tests.harness.pkg import mod

gt = mod('tools.graph_tools')
pytestmark = pytest.mark.stress

SIZES = [int(5000 * SCALE), int(20000 * SCALE), int(50000 * SCALE)]
MAX_CHARS = 120_000
P95_BUDGET_S = 0.5 * LATENCY_FACTOR


@pytest.fixture(scope='module', params=SIZES, ids=lambda n: '%dk' % (n // 1000))
def big(request):
    g = synthetic_graph(request.param, hub_callers=min(3000, request.param // 10), chain_depth=60)
    with installed_graph(g, write_sources=False) as env:
        env.size = request.param
        yield env


def timed(fn, *a):
    t = time.perf_counter()
    r = fn(*a)
    return time.perf_counter() - t, r


def test_cold_load_time_and_memory(big):
    gt._graph.cache_clear()
    tracemalloc.start()
    t = time.perf_counter()
    gt._graph()
    elapsed = time.perf_counter() - t
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert elapsed < (2 + big.size / 5000) * LATENCY_FACTOR, 'cold load took %.1fs' % elapsed
    assert peak < 1.2e9, 'graph load peaked at %.0f MB' % (peak / 1e6)


def test_tool_latency_p95_and_output_size(big):
    rnd = random.Random(3)
    ids = [n['id'] for n in big.graph['nodes']]
    ctx = FakeToolContext()
    gt._graph()
    lat = {'callers': [], 'callees': [], 'dependents': [], 'node': [], 'search': [], 'tests': [], 'trace': []}
    sizes = []
    for _ in range(150):
        n, m = rnd.choice(ids), rnd.choice(ids)
        for name, fn, args in [('callers', gt.get_callers, (n, ctx, 2)), ('callees', gt.get_callees, (n, ctx, 2)),
                               ('dependents', gt.get_dependents, (n, ctx, 4)), ('node', gt.get_node, (n, ctx)),
                               ('search', gt.search_symbols, ('f1', ctx)), ('tests', gt.find_tests_for_node, (n, ctx)),
                               ('trace', gt.trace_path, (n, m, ctx))]:
            dt, r = timed(fn, *args)
            lat[name].append(dt)
            sizes.append(len(json.dumps(r)))
    for name, vals in lat.items():
        s = summarize(vals)
        assert s['p95'] < P95_BUDGET_S, '%s p95 %.3fs exceeds %.2fs on %d nodes' % (name, s['p95'], P95_BUDGET_S, big.size)
    assert max(sizes) < MAX_CHARS, 'a single tool result was %d characters' % max(sizes)


def test_hub_and_chain_stay_correct_and_bounded(big):
    ctx = FakeToolContext()
    r = gt.trace_path('chain.c0', 'chain.c59', ctx)
    assert r['status'] == 'ok' and len(r['path']) == 60
    deep = gt.get_dependents('chain.c59', ctx, 10 ** 6)
    assert {d['id'] for d in deep['dependents']} == {'chain.c%d' % i for i in range(59)}
    hub = gt.get_dependents('hub.core', ctx, 4)
    assert len(json.dumps(hub)) < MAX_CHARS, 'hub dependents produced %d characters' % len(json.dumps(hub))


def test_results_match_the_oracle_on_sampled_nodes(big):
    rnd = random.Random(11)
    ctx = FakeToolContext()
    for node in rnd.sample([n['id'] for n in big.graph['nodes'] if not n['id'].startswith('hub')], 25):
        got = {c['id']: c['depth'] for c in gt.get_callers(node, ctx, 2)['callers']}
        assert got == dict(big.oracle.callers(node, 2))
