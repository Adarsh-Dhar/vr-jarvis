'''Layer 1: tool output must be bounded. Unbounded output overflows the model context and wrecks latency.'''
import json

import pytest

from tests.harness.context import FakeToolContext, installed_graph
from tests.harness.graphs import synthetic_graph, tiny_graph
from tests.harness.pkg import mod

gt = mod('tools.graph_tools')
common = mod('tools._common')

MAX_CHARS = 120_000      # roughly 30k tokens: the most one tool result should ever add to the context


@pytest.fixture(scope='module')
def hub():
    g = synthetic_graph(3300, hub_callers=3000, chain_depth=5)
    with installed_graph(g, write_sources=False) as env:
        yield env


def cap():
    assert hasattr(gt, 'MAX_RESULTS'), 'graph_tools needs a MAX_RESULTS constant that caps list results'
    return gt.MAX_RESULTS


def test_callers_of_a_hub_are_capped_and_flagged(hub):
    r = gt.get_callers('hub.core', FakeToolContext(), 1)
    assert len(r['callers']) <= cap()
    assert r.get('truncated') is True and r.get('total') == 3000


def test_dependents_of_a_hub_are_capped_and_small(hub):
    r = gt.get_dependents('hub.core', FakeToolContext(), 4)
    assert len(r['dependents']) <= cap() and r.get('truncated') is True
    assert len(json.dumps(r)) < MAX_CHARS


def test_big_cluster_is_capped(hub):
    r = gt.get_cluster('hub', FakeToolContext())
    assert len(r['members']) <= cap() and r.get('truncated') is True


def test_search_limit_cannot_be_used_to_dump_the_graph(hub):
    r = gt.search_symbols('hub', FakeToolContext(), limit=10 ** 6)
    assert len(r['matches']) <= cap()


def test_huge_depth_terminates_and_is_bounded(hub):
    r = gt.get_dependents('chain.c4', FakeToolContext(), 10 ** 9)
    assert len(json.dumps(r)) < MAX_CHARS


def test_negative_depth_returns_nothing(hub):
    assert gt.get_callers('hub.core', FakeToolContext(), -1)['callers'] == []


def test_evidence_list_stays_bounded_over_a_long_session(hub):
    assert hasattr(common, 'MAX_EVIDENCE'), 'tools/_common.py needs a MAX_EVIDENCE cap'
    ctx = FakeToolContext()
    for i in range(0, 3000, 100):
        gt.get_callers('hub.core', ctx, 1)
        gt.get_node('hub.caller%d' % i, ctx)
        ctx.state['evidence'] = ctx.state['evidence']          # session state is re-serialised every event
    for i in range(3000):
        common.record_evidence(ctx, ['hub.caller%d' % i])
    assert len(ctx.state['evidence']) <= common.MAX_EVIDENCE


def test_a_5000_line_function_is_truncated():
    g = tiny_graph()
    g['nodes'][0]['start'], g['nodes'][0]['end'] = 1, 5000
    with installed_graph(g, write_sources=False) as env:
        p = env.repo / g['nodes'][0]['file']
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('\n'.join('line %d' % i for i in range(1, 5001)))
        r = gt.get_source(g['nodes'][0]['id'], FakeToolContext())
    assert hasattr(gt, 'MAX_SOURCE_LINES'), 'graph_tools needs a MAX_SOURCE_LINES cap'
    assert len(r['source'].splitlines()) <= gt.MAX_SOURCE_LINES and r.get('truncated') is True
