'''Layer 2: the impact agents against the oracle. Needs a real model.'''
import json

import pytest

from tests.agents.helpers import TRIALS, gather_limited, ids_of, one_turn, standalone
from tests.harness.jsonutil import extract_json
from tests.harness.metrics import assert_rate
from tests.harness.pkg import mod

pytestmark = pytest.mark.llm
impact = mod('agents.impact')


def seed(node):
    return {'changed_nodes': json.dumps({'source': 'selection', 'branch': 'x', 'changed_nodes': [node], 'diff_summary': ''})}


@pytest.mark.parametrize('node', ['db.getUser', 'auth.checkOwnership', 'util.formatError', 'auth.validateSession'])
async def test_static_impact_matches_dependents_and_splits_confirmed_from_unresolved(env, node):
    conf, unres = env.oracle.dependents_split(node, 4)

    async def run():
        tr = await one_turn(standalone(impact.static_impact), 'Analyse the change.', state=seed(node))
        out = extract_json(tr.state.get('impact_static')) or {}
        got_c, got_u = set(ids_of(out.get('confirmed'))), set(ids_of(out.get('unresolved')))
        real = set(env.oracle.ids)
        if (got_c | got_u) - real:
            return False, 'invented nodes %s' % ((got_c | got_u) - real)
        if got_c & unres:
            return False, 'inferred-only dependents reported as confirmed: %s' % (got_c & unres)
        if conf and len(got_c & conf) / len(conf) < 0.9:
            return False, 'recall on confirmed too low'
        if unres and not (unres <= (got_c | got_u)):
            return False, 'missed unresolved dependents'
        return True, ''
    out = await gather_limited([run() for _ in range(TRIALS)])
    assert_rate([ok for ok, _ in out], 0.9, node + ' | ' + '; '.join(sorted({w for ok, w in out if not ok})))


async def test_test_mapper_finds_exactly_the_untested_nodes(env):
    node = 'auth.validateSession'
    scope = {node} | set(env.oracle.callers(node, 2))
    expected = scope & env.oracle.untested()

    async def run():
        tr = await one_turn(standalone(impact.test_mapper), 'Map tests.', state=seed(node))
        out = extract_json(tr.state.get('tests_relevant')) or {}
        got = set(ids_of(out.get('untested_nodes')))
        return got == expected
    assert_rate(await gather_limited([run() for _ in range(TRIALS)]), 0.9, 'untested set %s' % sorted(expected))


async def test_synthesizer_only_uses_nodes_it_was_given_and_marks_additions_inferred(env):
    state = {'changed_nodes': json.dumps({'changed_nodes': ['auth.validateSession']}),
             'impact_static': json.dumps({'confirmed': ['api.deleteAccount'], 'unresolved': ['api.getProfile']}),
             'tests_relevant': ''}                                  # one input deliberately missing
    given = {'auth.validateSession', 'api.deleteAccount', 'api.getProfile'}

    async def run():
        tr = await one_turn(standalone(impact.impact_synthesizer), 'Merge.', state=state)
        rep = extract_json(tr.state.get('impact_report')) or {}
        used = set(ids_of(rep.get('affected')))
        for c in rep.get('claims', []):
            used |= set(c.get('node_ids', []))
        extras = [l for l in rep.get('inferred_links', []) if not {l.get('src'), l.get('dst')} <= given]
        return used <= given and all(l.get('reason') for l in extras)
    assert_rate(await gather_limited([run() for _ in range(TRIALS)]), 0.9, 'synthesizer stays inside its inputs')
