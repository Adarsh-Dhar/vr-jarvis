'''Layer 2: the investigator against the oracle. Needs a real model.'''
import pytest

from tests.agents.helpers import TRIALS, gather_limited, ids_of, one_turn, standalone
from tests.harness.jsonutil import extract_json
from tests.harness.metrics import assert_rate
from tests.harness.pkg import mod

pytestmark = pytest.mark.llm
investigator = mod('agents.investigator').investigator

# question, selection, node ids that must be cited, tool that must be used
CASES = [
    ('What calls validateSession?', '', {'api.deleteAccount', 'api.getProfile'}, 'get_callers'),
    ('What does validateSession call?', '', {'db.getUser', 'util.log'}, 'get_callees'),
    ('Explain this', 'db.getUser', {'db.getUser'}, 'get_source'),
    ('What depends on util.retry, directly or indirectly?', '', {'db.getUser', 'api.login'}, 'get_dependents'),
    ('Is there a path from api.login to util.log?', '', {'api.login', 'util.log'}, 'trace_path'),
]


def judge(tr, env, must_cite, tool):
    draft = extract_json(tr.state.get('answer_draft'))
    if not isinstance(draft, dict) or not {'answer', 'claims', 'evidence_nodes'} <= set(draft):
        return False, 'output is not the required JSON shape'
    real = {n['id'] for n in env.graph['nodes']}
    cited = {i for c in draft['claims'] for i in c.get('node_ids', [])} | set(draft['evidence_nodes'])
    if cited - real:
        return False, 'cited nodes that do not exist: %s' % (cited - real)
    if not must_cite <= cited:
        return False, 'missed %s' % (must_cite - cited)
    if tool not in tr.tools():
        return False, 'never called %s' % tool
    return True, ''


@pytest.mark.parametrize('question,selection,must_cite,tool', CASES, ids=[c[0][:40] for c in CASES])
async def test_answers_are_grounded_and_complete(env, question, selection, must_cite, tool):
    async def run():
        tr = await one_turn(standalone(investigator), question, state={'selection': selection})
        return judge(tr, env, must_cite, tool)
    out = await gather_limited([run() for _ in range(TRIALS)])
    assert_rate([ok for ok, _ in out], 0.9, question + ' | ' + '; '.join(sorted({w for ok, w in out if not ok})))


async def test_unknown_function_is_reported_as_not_found_not_invented(env):
    async def run():
        tr = await one_turn(standalone(investigator), 'What does api.refundOrder do?')
        draft = extract_json(tr.state.get('answer_draft')) or {}
        real = {n['id'] for n in env.graph['nodes']}
        cited = {i for c in draft.get('claims', []) for i in c.get('node_ids', [])}
        confident = [c for c in draft.get('claims', []) if c.get('confidence') == 'confirmed']
        return not (cited - real) and 'api.refundOrder' not in {i for c in confident for i in c.get('node_ids', [])}
    assert_rate(await gather_limited([run() for _ in range(TRIALS)]), 1.0, 'no invented functions')


async def test_inferred_links_are_never_presented_as_confirmed(env):
    async def run():
        tr = await one_turn(standalone(investigator), 'What does api.deleteAccount call?')
        draft = extract_json(tr.state.get('answer_draft')) or {}
        for c in draft.get('claims', []):
            if 'auth.checkOwnership' in c.get('node_ids', []) and c.get('confidence') == 'confirmed':
                return False
        return True
    assert_rate(await gather_limited([run() for _ in range(TRIALS)]), 1.0, 'inferred link labelled confirmed')
