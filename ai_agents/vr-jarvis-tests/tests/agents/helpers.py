'''Shared helpers for tests that need a real model.

Set JARVIS_RUN_LLM=1 and model credentials to run them. JARVIS_DRY=1 swaps in the scripted model so the
test code itself can be exercised offline. Dry runs check the test mechanics, not agent quality.'''
import asyncio
import os

from tests.harness.jsonutil import extract_json
from tests.harness.metrics import TRIALS
from tests.harness.runner import Session, fresh_tree
from tests.harness.scripted_llm import ScriptedLlm

DRY = os.getenv('JARVIS_DRY') == '1'
CONCURRENCY = int(os.getenv('JARVIS_LLM_CONCURRENCY', '6'))


def model_or_none():
    return ScriptedLlm() if DRY else None


def tree(root):
    return fresh_tree(root, model_or_none())


def standalone(agent):
    '''Detached copy of one agent from the tree so it can be run and judged on its own.'''
    a = agent.clone()
    a.parent_agent = None
    llm = model_or_none()
    if llm is not None:
        a.model = llm
    return a


async def gather_limited(coros, limit=CONCURRENCY):
    sem = asyncio.Semaphore(limit)

    async def run(c):
        async with sem:
            return await c
    return await asyncio.gather(*[run(c) for c in coros])


def json_state(tr, key):
    return extract_json(tr.state.get(key))


def ids_of(items):
    '''Accept a list of ids or a list of objects with an id field.'''
    out = []
    for x in items or []:
        out.append(x['id'] if isinstance(x, dict) and 'id' in x else x)
    return [i for i in out if isinstance(i, str)]


async def one_turn(root, text, state=None, run_config=None, timeout=180):
    s = await Session(root, state=state, run_config=run_config).start()
    return await asyncio.wait_for(s.say(text), timeout=timeout)


__all__ = ['TRIALS']
