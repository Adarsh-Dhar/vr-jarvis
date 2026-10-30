'''Layer 5: long runs. Set JARVIS_SOAK=1. Looks for leaks, runaway growth, and leftover files.'''
import os
import tracemalloc

import pytest

from tests.harness.pkg import mod
from tests.harness.runner import Session, fresh_tree, run_turn
from tests.harness.scripted_llm import ScriptedLlm

ROOT = mod('agent').root_agent
gitt = mod('tools.git_tools')
ITER = int(os.getenv('JARVIS_SOAK_ITERATIONS', '120'))
pytestmark = [pytest.mark.stress, pytest.mark.soak]
PROMPTS = ['What calls validateSession?', 'What breaks if I change validateSession?',
           'Brief me on this project', 'Add a rate limit to deleteAccount']


async def test_many_fresh_sessions_do_not_leak_memory(git_env):
    for i in range(10):                                          # warm up
        await run_turn(fresh_tree(ROOT, ScriptedLlm()), PROMPTS[i % 3])
    tracemalloc.start()
    base, _ = tracemalloc.get_traced_memory()
    for i in range(ITER):
        await run_turn(fresh_tree(ROOT, ScriptedLlm()), PROMPTS[i % 3])
    grown, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert (grown - base) / ITER < 150_000, 'about %.0f KB retained per turn' % ((grown - base) / ITER / 1000)


async def test_worktrees_do_not_pile_up_on_disk(git_env):
    assert hasattr(gitt, 'MAX_WORKTREES'), 'git_tools needs a MAX_WORKTREES limit that prunes old sandboxes'
    for _ in range(max(ITER // 6, gitt.MAX_WORKTREES + 4)):
        await run_turn(fresh_tree(ROOT, ScriptedLlm()), 'Add a rate limit to deleteAccount')
    left = list(git_env.worktree_dir.glob('wt-*'))
    assert len(left) <= gitt.MAX_WORKTREES, '%d sandboxes left on disk' % len(left)


async def test_prompt_size_stays_flat_over_a_long_conversation(git_env):
    llm = ScriptedLlm()
    s = await Session(fresh_tree(ROOT, llm)).start()
    marks = {}
    for turn in range(1, 41):
        before = len(llm.sizes)
        await s.say(PROMPTS[turn % 3])
        marks[turn] = max(llm.sizes[before:])
    assert marks[40] < marks[5] * 3, 'prompt grew from %d to %d characters over 40 turns' % (marks[5], marks[40])
