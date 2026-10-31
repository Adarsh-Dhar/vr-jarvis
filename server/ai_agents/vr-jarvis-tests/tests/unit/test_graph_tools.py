'''Layer 1: every graph tool against an independent networkx oracle on a hand-checked graph.'''
import itertools

import pytest

from tests.harness.graphs import tiny_ids
from tests.harness.pkg import mod

gt = mod('tools.graph_tools')
IDS = tiny_ids()


@pytest.mark.parametrize('node', IDS)
@pytest.mark.parametrize('depth', [1, 2, 3, 10])
def test_callers_match_oracle(env, ctx, node, depth):
    got = {c['id']: c['depth'] for c in gt.get_callers(node, ctx, depth)['callers']}
    assert got == dict(env.oracle.callers(node, depth))


@pytest.mark.parametrize('node', IDS)
@pytest.mark.parametrize('depth', [1, 2, 3, 10])
def test_callees_match_oracle(env, ctx, node, depth):
    got = {c['id']: c['depth'] for c in gt.get_callees(node, ctx, depth)['callees']}
    assert got == dict(env.oracle.callees(node, depth))


@pytest.mark.parametrize('node', IDS)
@pytest.mark.parametrize('depth', [1, 2, 4, 10])
def test_dependents_match_oracle(env, ctx, node, depth):
    got = {c['id']: c['depth'] for c in gt.get_dependents(node, ctx, depth)['dependents']}
    assert got == dict(env.oracle.dependents(node, depth))


@pytest.mark.parametrize('src,dst', list(itertools.permutations(IDS, 2)))
def test_trace_path_matches_oracle(env, ctx, src, dst):
    r = gt.trace_path(src, dst, ctx)
    expected = env.oracle.shortest(src, dst)
    if expected is None:
        assert r['status'] == 'no_path'
        return
    assert r['status'] == 'ok'
    assert r['path'][0] == src and r['path'][-1] == dst
    assert len(r['path']) - 1 == expected
    for hop in r['hops']:
        assert env.oracle.has_edge(hop['from'], hop['to'])


def test_trace_path_to_self_is_trivial(env, ctx):
    r = gt.trace_path('util.log', 'util.log', ctx)
    assert r['status'] == 'ok' and r['path'] == ['util.log']


def test_cycle_terminates_and_includes_both_members(env, ctx):
    ids = {c['id'] for c in gt.get_callees('util.retry', ctx, 50)['callees']}
    assert 'util.backoff' in ids and 'util.retry' not in ids


def test_parallel_edges_do_not_duplicate_results(env, ctx):
    ids = [c['id'] for c in gt.get_dependents('auth.createSession', ctx, 1)['dependents']]
    assert ids.count('api.login') == 1


def test_depth_zero_returns_nothing(env, ctx):
    assert gt.get_callers('auth.validateSession', ctx, 0)['callers'] == []
    assert gt.get_dependents('auth.validateSession', ctx, 0)['dependents'] == []


def test_inferred_edges_are_labelled_inferred(env, ctx):
    callers = {c['id']: c['edge_kind'] for c in gt.get_callers('auth.checkOwnership', ctx)['callers']}
    assert callers == {'api.deleteAccount': 'inferred'}
    assert env.oracle.edge_kind('api.deleteAccount', 'auth.checkOwnership') == {'inferred'}


@pytest.mark.parametrize('tool,args', [
    ('get_node', ()), ('get_callers', ()), ('get_callees', ()), ('get_dependents', ()),
    ('get_source', ()), ('find_tests_for_node', ()), ('get_coverage', ()),
])
def test_unknown_node_returns_error_not_exception(env, ctx, tool, args):
    fn = getattr(gt, tool)
    r = fn('no.such.node', ctx, *args) if tool not in ('find_tests_for_node', 'get_coverage') else fn('no.such.node', ctx)
    if tool in ('find_tests_for_node', 'get_coverage'):
        assert r['status'] == 'ok'          # these accept unknown ids and report empty/null
    else:
        assert r['status'] == 'error' and 'no.such.node' in r['error']


def test_trace_path_unknown_ids(env, ctx):
    assert gt.trace_path('no.src', 'util.log', ctx)['status'] == 'error'
    assert gt.trace_path('util.log', 'no.dst', ctx)['status'] == 'error'


def test_evidence_is_recorded_without_duplicates(env, ctx):
    gt.get_callers('auth.validateSession', ctx, 1)
    gt.get_callers('auth.validateSession', ctx, 1)
    ev = ctx.state['evidence']
    assert len(ev) == len(set(ev))
    assert {'auth.validateSession', 'api.deleteAccount', 'api.getProfile'} <= set(ev)


def test_search_symbols(env, ctx):
    r = gt.search_graph_symbols('validate session', ctx)
    assert r['matches'][0]['id'] == 'auth.validateSession'
    assert len(gt.search_graph_symbols('a', ctx, limit=3)['matches']) <= 3
    assert gt.search_graph_symbols('zzzzqqq', ctx)['matches'] == []


def test_get_cluster(env, ctx):
    ids = {m['id'] for m in gt.get_cluster('db', ctx)['members']}
    assert ids == {'db.getUser', 'db.deleteUser', 'db.saveSession'}
    assert gt.get_cluster('nope', ctx)['members'] == []


def test_get_source_returns_exact_lines(env, ctx):
    r = gt.get_source('auth.validateSession', ctx)
    lines = r['source'].splitlines()
    assert r['first_line'] == 12 and len(lines) == 37
    assert lines[0].endswith('line 12') and lines[-1].endswith('line 48')


def test_get_source_context_lines_clamp_at_file_edges(env, ctx):
    r = gt.get_source('auth.checkOwnership', ctx, context_lines=50)     # lines 1-20 of a 20-line file
    assert r['first_line'] == 1 and len(r['source'].splitlines()) == 20


def test_get_source_missing_file_is_an_error_not_a_crash(env, ctx):
    (env.repo / 'src/auth/session.ts').unlink()
    try:
        r = gt.get_source('auth.validateSession', ctx)
    except FileNotFoundError:
        pytest.fail('get_source raised FileNotFoundError instead of returning status error')
    assert r['status'] == 'error'


def test_tests_and_coverage_match_oracle(env, ctx):
    for node in IDS:
        r = gt.find_tests_for_node(node, ctx)
        assert [t['id'] for t in r['tests']] == env.oracle.tests_for(node)
        assert r['untested'] == (node in env.oracle.untested())
    assert gt.get_coverage('api.deleteAccount', ctx)['coverage'] == 0.0
    assert gt.get_coverage('orphan.unused', ctx)['coverage'] is None


def test_verify_citations(env, ctx):
    r = gt.verify_citations(['api.login', 'made.up', 'util.log', ''], ctx)
    assert r['valid'] == ['api.login', 'util.log']
    assert r['invalid'] == ['made.up', '']
    assert gt.verify_citations([], ctx) == {'status': 'ok', 'valid': [], 'invalid': []}
