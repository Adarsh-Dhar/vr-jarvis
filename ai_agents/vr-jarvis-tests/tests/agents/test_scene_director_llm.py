'''Layer 2: the scene director must emit valid commands about real nodes and speak briefly.'''
import json
import re

import pytest

from tests.agents.helpers import TRIALS, gather_limited, model_or_none, one_turn
from tests.harness.jsonutil import ID_RE
from tests.harness.metrics import assert_rate
from tests.harness.pkg import mod
from tests.harness.schemas import node_ids_in, validate_command

pytestmark = pytest.mark.llm
make_scene_director = mod('agents.scene_director').make_scene_director

VERIFIED = json.dumps({'verdict': 'pass', 'answer': 'Two functions call validateSession.',
                       'claims': [{'text': 'callers', 'node_ids': ['auth.validateSession', 'api.deleteAccount', 'api.getProfile'],
                                   'confidence': 'confirmed'}], 'changes_made': []})
REPORT = json.dumps({'summary': 'Medium risk.', 'risk_level': 'medium',
                     'affected': [{'id': 'api.deleteAccount', 'risk': 'high', 'edge_kind': 'inferred', 'reason': 'x', 'untested': True}],
                     'inferred_links': [{'src': 'api.deleteAccount', 'dst': 'auth.checkOwnership', 'reason': 'name match'}],
                     'recommended_tests': [], 'claims': []})
PATCH = json.dumps({'summary': 'Adds a test.', 'files': ['tests/x.test.ts'], 'diff': '+ test', 'tests_added': ['tests/x.test.ts'],
                    'assumptions': [], 'claims': []})
FAILED = json.dumps({'status': 'failed', 'passed': [], 'failed': [{'id': 't', 'message': 'boom'}], 'not_run': [], 'typecheck': 'passed'})


def sentences(t):
    return [s for s in re.split(r'(?<=[.!?])\s+', t.strip()) if s]


async def run(state):
    director = make_scene_director('test_scene')
    llm = model_or_none()
    if llm is not None:
        director.model = llm
    return await one_turn(director, 'Show the result.', state=state)


def check(tr, env, state, expect_dashed=False, forbid_fixed=False):
    real = set(env.oracle.ids)
    if not tr.scene:
        return False, 'no scene commands'
    for c in tr.scene:
        if validate_command(c):
            return False, 'invalid command %s' % validate_command(c)
        if set(node_ids_in(c)) - real:
            return False, 'unknown node in command'
    types = [c['type'] for c in tr.scene]
    if 'highlight_path' not in types or 'dim_unrelated' not in types:
        return False, 'missing highlight or dim'
    if expect_dashed and not any(c['type'] == 'set_edge_style' and c['style'] == 'dashed' for c in tr.scene):
        return False, 'inferred link was not dashed'
    text = tr.final_text
    if len(sentences(text)) > 2:
        return False, 'spoken reply longer than two sentences'
    if re.search(r'[*#`]|^\s*[-\d]+[.)]\s', text, re.M) or ID_RE.search(text):
        return False, 'reply has markdown or node ids'
    if forbid_fixed and 'fixed' in text.lower():
        return False, 'claimed a fix with failing tests'
    return True, ''


async def test_scene_for_an_investigation(env):
    state = {'verified_answer': VERIFIED}

    async def one():
        return check(await run(state), env, state)
    out = await gather_limited([one() for _ in range(TRIALS)])
    assert_rate([ok for ok, _ in out], 0.9, '; '.join(sorted({w for ok, w in out if not ok})))


async def test_inferred_links_are_drawn_dashed(env):
    state = {'verified_answer': VERIFIED, 'impact_report': REPORT}

    async def one():
        return check(await run(state), env, state, expect_dashed=True)
    out = await gather_limited([one() for _ in range(TRIALS)])
    assert_rate([ok for ok, _ in out], 0.9, '; '.join(sorted({w for ok, w in out if not ok})))


async def test_a_patch_with_failing_tests_is_never_called_fixed(env):
    state = {'verified_answer': VERIFIED, 'proposed_patch': PATCH, 'test_results': FAILED}

    async def one():
        tr = await run(state)
        ok, why = check(tr, env, state, forbid_fixed=True)
        types = [c['type'] for c in tr.scene]
        return ok and 'show_ghost_diff' in types and 'show_test_badges' in types, why
    out = await gather_limited([one() for _ in range(TRIALS)])
    assert_rate([ok for ok, _ in out], 1.0, '; '.join(sorted({w for ok, w in out if not ok})))
