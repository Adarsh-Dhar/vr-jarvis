'''Layer 2: red-team the grounding critic. It must catch every seeded error, and not cry wolf on clean drafts.'''
import pytest

from tests.agents.helpers import TRIALS, gather_limited, json_state, one_turn
from tests.data.critic_cases import CASES
from tests.harness.metrics import assert_rate
from tests.harness.pkg import mod
from tests.harness.runner import fresh_tree
from tests.agents.helpers import model_or_none

pytestmark = pytest.mark.llm
make_critic = mod('agents.critic').make_critic


async def run_case(review_key, state, check):
    critic = make_critic('test_critic', review_key)
    llm = model_or_none()
    if llm is not None:
        critic.model = llm
    tr = await one_turn(critic, 'Review the draft.', state=state)
    verified = json_state(tr, 'verified_answer')
    if not isinstance(verified, dict):
        return False
    return bool(check(verified))


@pytest.mark.parametrize('name,key,state,bad,check', CASES, ids=[c[0] for c in CASES])
async def test_critic_case(env, name, key, state, bad, check):
    results = await gather_limited([run_case(key, state, check) for _ in range(TRIALS)])
    # Seeded errors must be caught every time. Clean drafts may be flagged occasionally.
    assert_rate(results, 1.0 if bad else 0.9, name)


async def test_critic_verdict_is_never_pass_for_a_draft_with_an_invented_node(env):
    state = CASES[0][2]

    async def verdict():
        critic = make_critic('test_critic', 'answer_draft')
        llm = model_or_none()
        if llm is not None:
            critic.model = llm
        tr = await one_turn(critic, 'Review the draft.', state=state)
        v = json_state(tr, 'verified_answer') or {}
        return v.get('verdict') != 'pass'
    assert_rate(await gather_limited([verdict() for _ in range(TRIALS)]), 1.0, 'verdict on invented node')
