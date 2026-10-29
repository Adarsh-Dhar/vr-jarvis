'''Layer 1: git sandbox and test-execution tools, using a real throwaway git repo.'''
import json
import subprocess
from unittest import mock

import pytest

from tests.harness.context import DEFAULT_DIFF, FakeToolContext
from tests.harness.pkg import mod

gitt = mod('tools.git_tools')
ex = mod('tools.exec_tools')


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def test_create_worktree_is_isolated(git_env, ctx):
    r = gitt.create_worktree(ctx)
    assert r['status'] == 'ok'
    wt = r['worktree']
    assert wt.startswith(str(git_env.worktree_dir)) and ctx.state['worktree'] == wt
    assert (git_env.repo / 'README.md').exists()
    assert run(['git', 'status', '--porcelain'], git_env.repo).stdout.strip() == ''


def test_each_worktree_is_unique(git_env):
    paths = set()
    for _ in range(5):
        c = FakeToolContext()
        assert gitt.create_worktree(c)['status'] == 'ok'
        paths.add(c.state['worktree'])
    assert len(paths) == 5


def test_create_worktree_outside_a_git_repo_returns_error(env, ctx):
    r = gitt.create_worktree(ctx)          # env has no git init
    assert r['status'] == 'error' and 'worktree' not in ctx.state


def test_apply_valid_diff_only_touches_the_worktree(git_env, ctx):
    gitt.create_worktree(ctx)
    assert gitt.apply_patch_to_worktree(DEFAULT_DIFF, ctx)['status'] == 'ok'
    wt = ctx.state['worktree']
    assert 'ratelimit.test.ts' in gitt.get_worktree_diff(ctx)['diff']
    assert (git_env.repo / 'tests/ratelimit.test.ts').exists() is False
    assert run(['git', 'log', '--oneline'], wt).stdout.count('\n') == 1      # nothing committed


def test_apply_garbage_diff_errors_and_leaves_worktree_clean(git_env, ctx):
    gitt.create_worktree(ctx)
    r = gitt.apply_patch_to_worktree('this is not a diff', ctx)
    assert r['status'] == 'error'
    assert gitt.get_worktree_diff(ctx)['diff'] == ''


def test_apply_without_worktree_errors(git_env, ctx):
    assert gitt.apply_patch_to_worktree(DEFAULT_DIFF, ctx)['status'] == 'error'
    assert gitt.get_worktree_diff(ctx)['status'] == 'error'


def test_applying_the_same_diff_twice_errors_cleanly(git_env, ctx):
    gitt.create_worktree(ctx)
    assert gitt.apply_patch_to_worktree(DEFAULT_DIFF, ctx)['status'] == 'ok'
    assert gitt.apply_patch_to_worktree(DEFAULT_DIFF, ctx)['status'] == 'error'


def test_change_readers(env, ctx):
    assert gitt.list_changed_nodes(ctx)['changed_nodes'] == ['auth.validateSession']
    assert 'auth.validateSession' in ctx.state['evidence']
    assert gitt.get_branch_info(ctx)['branch'] == 'feature/session-timeout'
    assert gitt.get_diff(ctx)['diff'].startswith('diff --git')


# ---- test execution tools -------------------------------------------------

def test_cached_run_tests_and_read_back(env, ctx):
    assert ex.read_test_results(ctx)['status'] == 'none'
    r = ex.run_tests(['tests/x.test.ts'], ctx)
    assert r['status'] == 'passed' and r['source'] == 'cached' and r['passed']      # status is passed, failed or error
    assert ex.read_test_results(ctx)['status'] == 'passed'


def test_missing_cache_file_is_an_error_not_a_crash(env, ctx):
    env.tests_path.unlink()
    try:
        r = ex.run_tests(['t'], ctx)
    except FileNotFoundError:
        pytest.fail('run_tests raised FileNotFoundError instead of returning status error')
    assert r['status'] == 'error'


def test_corrupt_cache_file_is_an_error_not_a_crash(env, ctx):
    env.tests_path.write_text('{not json')
    try:
        r = ex.run_tests(['t'], ctx)
    except json.JSONDecodeError:
        pytest.fail('run_tests raised JSONDecodeError instead of returning status error')
    assert r['status'] == 'error'


def jest(*suites):
    return json.dumps({'testResults': [{'assertionResults': list(s)} for s in suites]})


@pytest.fixture
def live(env, ctx):
    ctx.state['worktree'] = '/tmp/jarvis-test-worktree'   # run_tests/run_typecheck now refuse to run without one
    with mock.patch.object(ex, 'USE_CACHED_TESTS', False):
        yield


def test_live_passing_run(live, ctx):
    out = jest([{'status': 'passed', 'fullName': 'a'}, {'status': 'passed', 'fullName': 'b'}])
    with mock.patch.object(ex, '_run', return_value=(0, out, '')):
        r = ex.run_tests(['t'], ctx)
    assert r['status'] == 'passed' and r['passed'] == ['a', 'b'] and r['failed'] == []


def test_live_failing_run_reports_each_failure(live, ctx):
    out = jest([{'status': 'passed', 'fullName': 'a'},
                {'status': 'failed', 'fullName': 'b', 'failureMessages': ['boom']}])
    with mock.patch.object(ex, '_run', return_value=(1, out, '')):
        r = ex.run_tests(['t'], ctx)
    assert r['status'] == 'failed' and r['failed'][0] == {'id': 'b', 'message': 'boom'}


@pytest.mark.parametrize('rc,out,err', [(1, 'not json at all', 'SyntaxError'), (124, '', 'timeout'), (0, '', '')])
def test_live_garbage_or_timeout_is_an_error_never_a_pass(live, ctx, rc, out, err):
    with mock.patch.object(ex, '_run', return_value=(rc, out, err)):
        r = ex.run_tests(['t'], ctx)
    assert r['status'] == 'error'
    assert 'passed' not in r or r.get('passed') in (None, [])


def test_live_run_with_zero_tests_is_not_reported_as_passed(live, ctx):
    with mock.patch.object(ex, '_run', return_value=(0, jest(), '')):
        r = ex.run_tests(['t'], ctx)
    assert r['status'] != 'passed', 'a run that executed no tests must not count as passed'


def test_typecheck_modes(live, ctx):
    with mock.patch.object(ex, '_run', return_value=(0, '', '')):
        assert ex.run_typecheck(ctx)['typecheck'] == 'passed'
    with mock.patch.object(ex, '_run', return_value=(2, 'src/a.ts(1,1): error TS1', '')):
        r = ex.run_typecheck(ctx)
    assert r['typecheck'] == 'failed' and r['errors']
