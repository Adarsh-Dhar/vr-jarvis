'''Layer 5: concurrency. Shared files, git, and many sessions at once must not corrupt or leak state.'''
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.harness.context import FakeToolContext, installed_graph
from tests.harness.graphs import synthetic_graph, tiny_ids
from tests.harness.jsonutil import extract_json
from tests.harness.metrics import SCALE
from tests.harness.pkg import mod
from tests.harness.runner import Session, fresh_tree
from tests.harness.schemas import validate_command
from tests.harness.scripted_llm import ScriptedLlm

gt = mod('tools.graph_tools')
gitt = mod('tools.git_tools')
memt = mod('tools.memory_tools')
ROOT = mod('agent').root_agent
pytestmark = pytest.mark.stress
N = max(int(24 * SCALE), 6)


def test_threads_get_the_same_answers_as_a_single_thread():
    g = synthetic_graph(5000, hub_callers=100, chain_depth=20)
    with installed_graph(g, write_sources=False) as env:
        ids = [n['id'] for n in g['nodes']][::37]
        expected = {i: [c['id'] for c in gt.get_callers(i, FakeToolContext(), 2)['callers']] for i in ids}

        def work(i):
            return i, [c['id'] for c in gt.get_callers(i, FakeToolContext(), 2)['callers']]

        with ThreadPoolExecutor(16) as pool:
            for _ in range(5):
                for i, got in pool.map(work, ids):
                    assert got == expected[i]


def test_concurrent_memory_writes_do_not_lose_or_corrupt_data(env):
    def save(i):
        memt.save_finding('finding %d' % i, ['api.login'], FakeToolContext())

    with ThreadPoolExecutor(16) as pool:
        list(pool.map(save, range(N)))
    data = json.loads(env.memory_path.read_text())
    assert len(data['findings']) == N, 'lost %d writes' % (N - len(data['findings']))


def test_concurrent_worktrees_all_succeed_and_are_unique(git_env):
    def make(_):
        c = FakeToolContext()
        return gitt.create_worktree(c), c.state.get('worktree')

    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(make, range(12)))
    failed = [r for r, _ in results if r['status'] != 'ok']
    assert not failed, 'git worktree creation failed under concurrency: %s' % failed[0]
    assert len({p for _, p in results}) == 12


async def test_concurrent_sessions_do_not_bleed_state(git_env):
    ids = tiny_ids()

    async def one(i):
        sel = ids[i % len(ids)]
        s = await Session(fresh_tree(ROOT, ScriptedLlm()), user='user%d' % i, state={'selection': sel}).start()
        tr = await s.say('Explain this')
        claims = extract_json(tr.state['answer_draft'])['claims'][0]['node_ids']
        return sel, claims, tr

    results = await asyncio.wait_for(asyncio.gather(*[one(i) for i in range(N)]), timeout=180)
    for sel, claims, tr in results:
        assert claims[0] == sel, 'session for %s got an answer about %s' % (sel, claims[0])
        assert tr.state['selection'] == sel
        assert all(validate_command(c) == [] for c in tr.scene)


async def test_mixed_pipelines_in_parallel_all_complete_correctly(git_env):
    prompts = [('What calls validateSession?', 'investigator_agent'),
               ('What breaks if I change validateSession?', 'change_loader_agent'),
               ('Brief me on this project', 'briefing_agent'),
               ('Add a rate limit to deleteAccount', 'patch_agent')]

    async def one(i):
        text, first = prompts[i % 4]
        s = await Session(fresh_tree(ROOT, ScriptedLlm()), user='mix%d' % i).start()
        return first, await s.say(text)

    results = await asyncio.wait_for(asyncio.gather(*[one(i) for i in range(N)]), timeout=240)
    for first, tr in results:
        assert tr.authors[1] == first and tr.authors[-1].endswith('_scene') and tr.final_text
    patches = [extract_json(tr.state['proposed_patch']) for first, tr in results if first == 'patch_agent']
    assert all(p and 'ratelimit.test.ts' in p['diff'] for p in patches), 'a concurrent fix produced an empty patch'
