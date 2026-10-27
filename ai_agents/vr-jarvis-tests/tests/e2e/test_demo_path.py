'''Layer 4: the three-minute demo, end to end. The scripted run always executes; the real-model run repeats the
path many times and measures the success rate and latency budgets. Run it against the cached demo data.'''
import os

import pytest

from tests.agents.helpers import tree
from tests.harness.context import installed_graph
from tests.harness.metrics import assert_rate, summarize
from tests.harness.pkg import mod
from tests.harness.runner import Session, fresh_tree
from tests.harness.schemas import node_ids_in, validate_command
from tests.harness.scripted_llm import ScriptedLlm

ROOT = mod('agent').root_agent
DEMO_TRIALS = int(os.getenv('DEMO_TRIALS', '10'))
BUDGET = {'brief': 8.0, 'investigate': 10.0, 'impact': 15.0, 'fix': 40.0}     # seconds, real model

STEPS = [  # name, utterance, selection, expected first agent after the root
    ('brief', 'Brief me on this project', None, 'briefing_agent'),
    ('investigate', 'Explain this', 'auth.validateSession', 'investigator_agent'),
    ('impact', 'What breaks if I change this?', None, 'change_loader_agent'),
    ('fix', 'Add a rate limit to deleteAccount', None, 'patch_agent'),
    ('approve', 'Commit this change', None, None),
]


async def run_demo(root, env):
    ids = {n['id'] for n in env.graph['nodes']}
    s = await Session(root).start()
    problems, times = [], {}
    for name, text, sel, first in STEPS:
        tr = await s.say(text, state_delta={'selection': sel} if sel else None)
        times[name] = tr.latency_s
        if name != 'approve' and (len(tr.authors) < 2 or tr.authors[1] != first):
            problems.append('%s routed to %s' % (name, tr.authors[:2]))
        if not tr.final_text:
            problems.append('%s gave no spoken reply' % name)
        for c in tr.scene:
            if validate_command(c) or set(node_ids_in(c)) - ids:
                problems.append('%s emitted a bad scene command: %s' % (name, c))
        if name == 'approve':
            if 'request_approval' not in tr.tools() or tr.state.get('approved') is not False:
                problems.append('approval step did not ask the user')
    return problems, times


async def test_demo_path_with_the_scripted_model():
    with installed_graph(git=True) as env:
        problems, times = await run_demo(fresh_tree(ROOT, ScriptedLlm()), env)
    assert problems == []


@pytest.mark.llm
async def test_demo_path_with_a_real_model_repeatedly():
    oks, all_times = [], {k: [] for k in BUDGET}
    for _ in range(DEMO_TRIALS):
        with installed_graph(git=True) as env:
            problems, times = await run_demo(tree(ROOT), env)
        oks.append(not problems)
        for k, v in times.items():
            if k in all_times:
                all_times[k].append(v)
    assert_rate(oks, 0.9, 'demo path')
    for k, vals in all_times.items():
        assert summarize(vals)['p95'] < BUDGET[k], '%s p95 %.1fs over %.0fs budget' % (k, summarize(vals)['p95'], BUDGET[k])
