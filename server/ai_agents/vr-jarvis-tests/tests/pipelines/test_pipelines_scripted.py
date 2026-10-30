'''Layer 3: the real agent tree, real tools, real ADK routing, loops and state, with a scripted model.

Only the model is fake, so these tests prove the wiring: routing, state hand-off, the parallel step,
the verify loop, escalation, per-turn state, and scene commands. They run offline and are deterministic.
'''
import pytest

from tests.harness.context import FAILING_TESTS, PASSING_TESTS
from tests.harness.jsonutil import extract_json
from tests.harness.pkg import mod
from tests.harness.runner import Session, fresh_tree, run_turn
from tests.harness.schemas import node_ids_in, validate_command
from tests.harness.scripted_llm import ScriptedLlm

ROOT = mod('agent').root_agent
ORCH = 'jarvis_orchestrator'


def make(**kw):
    llm = ScriptedLlm(**kw)
    return llm, fresh_tree(ROOT, llm)


def valid_scene(tr, env):
    ids = {n['id'] for n in env.graph['nodes']}
    for cmd in tr.scene:
        assert validate_command(cmd) == [], cmd
        unknown = set(node_ids_in(cmd)) - ids
        assert not unknown, 'scene command references nodes that do not exist: %s' % unknown


@pytest.mark.parametrize('text,first_agent,pipeline_agents', [
    ('What calls validateSession?', 'investigator_agent', ['investigator_agent', 'investigate_critic', 'investigate_scene']),
    ('What breaks if I change validateSession?', 'change_loader_agent',
     ['change_loader_agent', 'static_impact_agent', 'test_mapper_agent', 'impact_synthesizer_agent',
      'impact_critic', 'impact_scene']),
    ('Add a rate limit to deleteAccount', 'patch_agent', ['patch_agent', 'verifier_agent', 'fix_critic', 'fix_scene']),
    ('Brief me on this project', 'briefing_agent', ['briefing_agent', 'briefing_scene']),
])
async def test_each_intent_runs_its_whole_pipeline_in_order(git_env, text, first_agent, pipeline_agents):
    llm, tree = make()
    tr = await run_turn(tree, text)
    assert tr.authors[0] == ORCH and tr.authors[1] == first_agent
    positions = [tr.authors.index(a) for a in pipeline_agents]
    assert positions == sorted(positions), 'agents ran out of order: %s' % tr.authors
    assert tr.authors[-1].endswith('_scene'), 'the last agent must be the scene director'
    assert tr.final_text and len(tr.final_text.split('.')) <= 3
    valid_scene(tr, git_env)


async def test_out_of_scope_request_never_reaches_a_pipeline(git_env):
    llm, tree = make()
    tr = await run_turn(tree, 'Who won the cricket match?')
    assert tr.authors == [ORCH] and tr.calls == [] and tr.scene == []


async def test_empty_input_gets_a_clarifying_reply_not_a_crash(git_env):
    llm, tree = make()
    tr = await run_turn(tree, '   ')
    assert tr.authors == [ORCH] and tr.final_text


async def test_investigate_fills_state_with_parseable_json_and_real_evidence(git_env):
    llm, tree = make()
    tr = await run_turn(tree, 'What calls validateSession?')
    draft = extract_json(tr.state['answer_draft'])
    verified = extract_json(tr.state['verified_answer'])
    assert draft and draft['claims'] and verified and verified['verdict'] == 'pass'
    ids = {n['id'] for n in git_env.graph['nodes']}
    assert tr.state['evidence'] and set(tr.state['evidence']) <= ids
    assert {'api.deleteAccount', 'api.getProfile'} <= set(draft['claims'][0]['node_ids'])


async def test_pinched_selection_reaches_the_investigator(git_env):
    llm, tree = make()
    tr = await run_turn(tree, 'Explain this', state={'selection': 'db.getUser'})
    claims = extract_json(tr.state['answer_draft'])['claims'][0]['node_ids']
    assert claims[0] == 'db.getUser'
    assert any('db.getUser' in s for a, s in llm.seen if a == 'investigator_agent')


async def test_impact_pipeline_runs_both_parallel_branches_and_merges(git_env):
    llm, tree = make()
    tr = await run_turn(tree, 'What breaks if I change validateSession?')
    assert 'static_impact_agent' in tr.authors and 'test_mapper_agent' in tr.authors
    for key in ('changed_nodes', 'impact_static', 'tests_relevant', 'impact_report', 'verified_answer'):
        assert extract_json(tr.state[key]) is not None, '%s is empty or not JSON' % key
    synth = [s for a, s in llm.seen if a == 'impact_synthesizer_agent'][0]
    assert 'confirmed' in synth and 'untested' in synth.lower() or 'tests' in synth     # both branches visible
    valid_scene(tr, git_env)


async def test_fix_passes_first_time_loop_exits_and_the_rest_still_runs(git_env):
    llm, tree = make()
    tr = await run_turn(tree, 'Add a rate limit to deleteAccount')
    assert tr.count('run_tests') == 1 and tr.count('exit_loop') == 1
    assert 'patch_repair_agent' not in tr.authors
    assert tr.authors[-2:] == ['fix_critic', 'fix_scene'], 'escalating out of the loop must not end the pipeline'
    assert extract_json(tr.state['test_results'])['status'] == 'passed'
    types = [c['type'] for c in tr.scene]
    assert 'show_ghost_diff' in types and 'show_test_badges' in types
    assert 'ratelimit.test.ts' in extract_json(tr.state['proposed_patch'])['diff']
    valid_scene(tr, git_env)


async def test_fix_creates_one_worktree_and_never_touches_the_main_checkout(git_env):
    llm, tree = make()
    tr = await run_turn(tree, 'Add a rate limit to deleteAccount')
    assert tr.count('create_worktree') == 1
    assert tr.state['worktree'].startswith(str(git_env.worktree_dir))
    assert not (git_env.repo / 'tests/ratelimit.test.ts').exists()


async def test_fix_that_never_passes_stops_after_three_rounds_and_does_not_claim_success(git_env):
    git_env.set_cached_tests(FAILING_TESTS)
    llm, tree = make()
    tr = await run_turn(tree, 'Add a rate limit to deleteAccount')
    assert tr.count('run_tests') == 3 and tr.authors.count('patch_repair_agent') == 1      # unique authors list
    assert [a for a, t, _ in tr.calls].count('patch_repair_agent') >= 3
    assert tr.count('exit_loop') == 0
    assert extract_json(tr.state['test_results'])['status'] == 'failed'
    assert tr.authors[-2:] == ['fix_critic', 'fix_scene']
    assert 'fixed' not in tr.final_text.lower()
    assert 'show_test_badges' in [c['type'] for c in tr.scene]


async def test_fix_that_fails_once_then_passes_after_repair(git_env):
    git_env.set_cached_tests(FAILING_TESTS)
    llm, tree = make(hooks=[lambda agent, step: git_env.set_cached_tests(PASSING_TESTS)
                            if agent == 'patch_repair_agent' else None])
    tr = await run_turn(tree, 'Add a rate limit to deleteAccount')
    assert tr.count('run_tests') == 2 and tr.count('exit_loop') == 1
    assert extract_json(tr.state['test_results'])['status'] == 'passed'
    patch = extract_json(tr.state['proposed_patch'])
    assert 'repair1.test.ts' in patch['diff'] and 'ratelimit.test.ts' in patch['diff']      # cumulative diff


async def test_briefing_state_and_scene(git_env):
    llm, tree = make()
    tr = await run_turn(tree, 'Brief me on this project')
    assert extract_json(tr.state['briefing'])['risky_nodes'] == ['auth.validateSession']
    assert tr.count('load_project_memory') == 1
    valid_scene(tr, git_env)


async def test_commit_request_goes_through_approval_and_nothing_is_committed(git_env):
    llm, tree = make()
    tr = await run_turn(tree, 'Commit this change', state={'approved': True})
    assert tr.tools() == ['request_approval']
    assert tr.state['approved'] is False and tr.state['pending_approval']
    assert [c['type'] for c in tr.scene] == ['show_approval_prompt']


async def test_conversation_returns_to_the_root_each_turn_and_clears_scene_commands(git_env):
    llm, tree = make()
    s = await Session(tree).start()
    turns = [('Brief me on this project', None), ('Explain this', {'selection': 'auth.validateSession'}),
             ('What breaks if I change this?', None), ('Add a rate limit to deleteAccount', None),
             ('Commit this change', None)]
    seen_types = []
    for text, delta in turns:
        tr = await s.say(text, state_delta=delta)
        assert tr.authors[0] == ORCH, 'turn %r did not start at the root: %s' % (text, tr.authors)
        seen_types.append([c['type'] for c in tr.scene])
    assert seen_types[-1] == ['show_approval_prompt'], 'scene commands from earlier turns leaked into the last turn'
    assert all(len(t) < 12 for t in seen_types)


async def test_turn_does_not_see_the_previous_turns_results(git_env):
    '''A scene director must only see results from its own turn. Stale impact or patch data
    in its prompt makes it highlight things the user did not ask about.'''
    llm, tree = make()
    s = await Session(tree).start()
    await s.say('What breaks if I change validateSession?')
    marker = llm.policy.marker
    llm.seen.clear()
    await s.say('What calls getUser?', state_delta={'selection': 'db.getUser'})
    prompts = [text for agent, text in llm.seen if agent == 'investigate_scene']
    assert prompts and all(marker not in p for p in prompts), (
        'investigate_scene received the previous turn\'s impact_report in its instruction')


async def test_model_call_budget_per_pipeline(git_env):
    budgets = {'What calls validateSession?': 12, 'What breaks if I change validateSession?': 18,
               'Add a rate limit to deleteAccount': 20, 'Brief me on this project': 10}
    for text, limit in budgets.items():
        llm, tree = make()
        tr = await run_turn(tree, text)
        assert len(llm.calls) <= limit, '%r used %d model calls (budget %d)' % (text, len(llm.calls), limit)
