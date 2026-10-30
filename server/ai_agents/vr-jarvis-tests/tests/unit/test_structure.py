'''Static checks on the agent tree. These catch wiring mistakes before any model is called.'''
import inspect
import re

import pytest
from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent

from tests.harness.pkg import mod

agent_mod = mod('agent')
DEFAULT_STATE = mod('state').DEFAULT_STATE
guard = mod('callbacks').permission_guard
ROOT = agent_mod.root_agent


def walk(a):
    yield a
    for s in a.sub_agents or []:
        yield from walk(s)


ALL = list(walk(ROOT))
LLM = [a for a in ALL if isinstance(a, LlmAgent)]


def reads(a):
    if isinstance(a, LlmAgent) and isinstance(a.instruction, str):
        return set(re.findall(r'\{(\w+)\}', a.instruction))
    return set()


def writes(a):
    return {x.output_key for x in walk(a) if isinstance(x, LlmAgent) and x.output_key}


def tool_fns(a):
    return [t for t in (a.tools or []) if callable(t)]


def tool_names(a):
    return {t.__name__ for t in tool_fns(a)}


def test_agent_names_are_unique():
    names = [a.name for a in ALL]
    assert len(names) == len(set(names)), sorted(n for n in names if names.count(n) > 1)


def test_parent_links_are_consistent():
    for a in ALL:
        for s in a.sub_agents or []:
            assert s.parent_agent is a, '%s has the wrong parent' % s.name


@pytest.mark.parametrize('a', LLM, ids=lambda a: a.name)
def test_instruction_placeholders_exist_in_default_state(a):
    missing = reads(a) - set(DEFAULT_STATE)
    assert not missing, '%s reads state keys that are never initialised: %s' % (a.name, missing)


@pytest.mark.parametrize('a', [x for x in LLM if x.output_key], ids=lambda a: a.name)
def test_output_keys_are_declared_state_keys(a):
    assert a.output_key in DEFAULT_STATE


@pytest.mark.parametrize('a', [x for x in ALL if isinstance(x, ParallelAgent)], ids=lambda a: a.name)
def test_parallel_branches_do_not_depend_on_each_other(a):
    for i, branch in enumerate(a.sub_agents):
        others_out = set()
        for j, other in enumerate(a.sub_agents):
            if j != i:
                others_out |= writes(other)
        r = set()
        for x in walk(branch):
            r |= reads(x)
        assert not (r & others_out), '%s reads %s written by a sibling that runs at the same time' % (
            branch.name, r & others_out)


@pytest.mark.parametrize('a', [x for x in ALL if isinstance(x, SequentialAgent)], ids=lambda a: a.name)
def test_sequential_agents_never_read_a_key_before_it_is_written(a):
    for i, step in enumerate(a.sub_agents):
        later, earlier = set(), set()
        for s in a.sub_agents[i + 1:]:
            later |= writes(s)
        for s in a.sub_agents[:i]:
            earlier |= writes(s)
        r = set()
        for x in walk(step):
            r |= reads(x)
        bad = (r & later) - earlier - writes(step)
        assert not bad, '%s reads %s, which is only written by a later step' % (step.name, bad)


@pytest.mark.parametrize('a', [x for x in LLM if x.tools], ids=lambda a: a.name)
def test_every_tool_is_documented_and_typed(a):
    seen = set()
    for fn in tool_fns(a):
        assert fn.__name__ not in seen, 'duplicate tool %s on %s' % (fn.__name__, a.name)
        seen.add(fn.__name__)
        assert inspect.getdoc(fn), '%s has no docstring, so the model cannot know when to use it' % fn.__name__
        sig = inspect.signature(fn)
        for p in sig.parameters.values():
            assert p.annotation is not inspect.Parameter.empty, '%s.%s has no type hint' % (fn.__name__, p.name)
        assert sig.return_annotation in (dict, 'dict'), '%s should be annotated -> dict' % fn.__name__


def test_root_has_no_code_tools_and_only_root_can_request_approval():
    assert [t.__name__ for t in ROOT.tools] == ['request_approval']
    for a in LLM:
        if a is not ROOT:
            assert 'request_approval' not in tool_names(a)


WRITE_TOOLS = {'create_worktree', 'apply_patch_to_worktree', 'run_tests', 'run_typecheck'}


@pytest.mark.parametrize('a', [x for x in LLM if x.tools], ids=lambda a: a.name)
def test_agents_with_sandbox_tools_use_the_permission_guard(a):
    if WRITE_TOOLS & tool_names(a):
        assert a.before_tool_callback is guard, '%s can change the sandbox but has no permission guard' % a.name


def test_loop_is_bounded_and_only_the_verifier_can_end_it():
    loops = [a for a in ALL if isinstance(a, LoopAgent)]
    assert loops
    for loop in loops:
        assert loop.max_iterations and loop.max_iterations <= 5
        can_exit = [s.name for s in loop.sub_agents if 'exit_loop' in tool_names(s)]
        assert can_exit == ['verifier_agent']


def test_scene_directors_cannot_ask_for_approval_or_touch_code():
    forbidden = {'request_approval', 'show_approval_prompt', 'apply_patch_to_worktree', 'create_worktree', 'run_tests'}
    for a in LLM:
        if a.name.endswith('_scene'):
            assert not (forbidden & tool_names(a))


def test_routing_descriptions_are_distinct_and_informative():
    descs = [s.description for s in ROOT.sub_agents]
    assert len(set(descs)) == len(descs)
    assert all(len(d) >= 40 for d in descs)


def test_every_pipeline_ends_in_a_scene_director_so_the_user_always_gets_a_reply():
    for p in ROOT.sub_agents:
        assert p.sub_agents[-1].name.endswith('_scene'), p.name


def test_every_non_briefing_pipeline_has_a_critic_before_the_scene():
    for p in ROOT.sub_agents:
        if p.name != 'briefing_pipeline':
            assert any(s.name.endswith('_critic') for s in p.sub_agents), p.name
