import json
import subprocess

from google.adk.tools import ToolContext

from ..config import CACHED_TESTS_PATH, USE_CACHED_TESTS


def _run(cmd, cwd, timeout=180):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, '', 'timeout'


def run_tests(test_files: list[str], tool_context: ToolContext) -> dict:
    '''Run only the given test files in the sandbox worktree and return per-test results.
    status is passed, failed or error. Never guess a result; report exactly what ran.'''
    if USE_CACHED_TESTS:
        data = json.loads(CACHED_TESTS_PATH.read_text())
        tool_context.state['last_test_run'] = data
        return {'status': 'ok', 'source': 'cached', **data}
    cwd = tool_context.state.get('worktree')
    code, out, err = _run(['npx', 'jest', '--json', *test_files], cwd)
    try:
        report = json.loads(out)
    except json.JSONDecodeError:
        return {'status': 'error', 'stderr': err[-2000:]}
    passed, failed = [], []
    for suite in report.get('testResults', []):
        for a in suite.get('assertionResults', []):
            if a['status'] == 'passed':
                passed.append(a['fullName'])
            else:
                failed.append({'id': a['fullName'], 'message': ' '.join(a.get('failureMessages', []))[:500]})
    result = {'status': 'failed' if failed else 'passed', 'source': 'live',
              'passed': passed, 'failed': failed}
    tool_context.state['last_test_run'] = result
    return {'status': 'ok', **result}


def run_typecheck(tool_context: ToolContext) -> dict:
    '''Run the TypeScript type check in the sandbox worktree. Returns the first 40 lines of errors.'''
    if USE_CACHED_TESTS:
        return {'status': 'ok', 'typecheck': 'passed', 'source': 'cached'}
    code, out, err = _run(['npx', 'tsc', '--noEmit'], tool_context.state.get('worktree'))
    lines = (out + err).splitlines()[:40]
    return {'status': 'ok', 'typecheck': 'passed' if code == 0 else 'failed', 'errors': lines}


def read_test_results(tool_context: ToolContext) -> dict:
    '''Return the most recent test run from this session, or none if no tests have run.'''
    last = tool_context.state.get('last_test_run')
    if not last:
        return {'status': 'none'}
    return {'status': 'ok', **last}
