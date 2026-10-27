'''Layer 2: patch agent and verifier with a real model, in a real throwaway git repo.'''
import json

import pytest

from tests.agents.helpers import TRIALS, gather_limited, json_state, one_turn, standalone
from tests.harness.context import FAILING_TESTS, PASSING_TESTS, installed_graph
from tests.harness.metrics import assert_rate
from tests.harness.pkg import mod

pytestmark = pytest.mark.llm
fix = mod('agents.fix')
FORBIDDEN = {'commit_changes', 'merge_branch', 'request_approval'}


async def test_patch_agent_works_only_in_the_sandbox_and_returns_a_real_diff():
    async def run():
        with installed_graph(git=True) as env:
            tr = await one_turn(standalone(fix.patch_agent),
                                'Add a regression test proving deleteAccount checks ownership.',
                                state={'selection': 'api.deleteAccount'})
            patch = json_state(tr, 'proposed_patch') or {}
            tools = tr.tools()
            ok = (tools.index('create_worktree') < tools.index('apply_patch_to_worktree')
                  and not FORBIDDEN & set(tools)
                  and bool(patch.get('diff')) and bool(patch.get('tests_added')) and len(patch.get('files', [])) <= 3
                  and tr.state.get('worktree', '').startswith(str(env.worktree_dir))
                  and not list((env.repo / 'tests').glob('*.test.ts')))      # main checkout untouched
            return ok
    assert_rate(await gather_limited([run() for _ in range(TRIALS)], limit=2), 0.9, 'patch agent')


@pytest.mark.parametrize('cached,expect_status,expect_exit', [
    (PASSING_TESTS, 'passed', 1), (FAILING_TESTS, 'failed', 0)], ids=['passing', 'failing'])
async def test_verifier_reports_exactly_what_the_tools_returned(cached, expect_status, expect_exit):
    patch = json.dumps({'summary': 's', 'files': ['tests/ratelimit.test.ts'], 'diff': 'd',
                        'tests_added': ['tests/ratelimit.test.ts'], 'assumptions': [], 'claims': []})

    async def run():
        with installed_graph(git=True, cached_tests=cached):
            tr = await one_turn(standalone(fix.verifier), 'Verify the patch.', state={'proposed_patch': patch})
            res = json_state(tr, 'test_results') or {}
            return res.get('status') == expect_status and tr.count('exit_loop') == expect_exit
    assert_rate(await gather_limited([run() for _ in range(TRIALS)]), 1.0, 'verifier on %s tests' % expect_status)


async def test_verifier_never_reports_passed_when_tests_could_not_run():
    patch = json.dumps({'summary': 's', 'files': [], 'diff': 'd', 'tests_added': [], 'assumptions': [], 'claims': []})

    async def run():
        with installed_graph(git=True) as env:
            env.tests_path.unlink()                      # the test runner has nothing to report
            try:
                tr = await one_turn(standalone(fix.verifier), 'Verify the patch.', state={'proposed_patch': patch})
            except Exception:
                return True                              # failing loudly is acceptable
            res = json_state(tr, 'test_results') or {}
            return res.get('status') != 'passed' and tr.count('exit_loop') == 0
    assert_rate(await gather_limited([run() for _ in range(TRIALS)]), 1.0, 'no false pass')
