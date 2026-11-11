import hashlib
import json
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from google.adk.tools import ToolContext

from ..config import CACHED_TESTS_PATH, USE_CACHED_TESTS
from ._safe import safe
from .graph_tools import _graph


def _test_id(full_name):
    '''Jest reports names like "deleteAccount deletes own account". The scene needs graph node ids.'''
    for tid, node in _graph()['nodes'].items():
        if node.get('kind') == 'test' and node.get('name') and full_name.endswith(node['name']):
            return tid
    return full_name


def _run(cmd, cwd, timeout=180):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, '', 'timeout'


def _worktree_fingerprint(cwd):
    """Identify the exact patch a test/typecheck run saw: hash of the worktree
    diff plus HEAD. /approve recomputes this and refuses stale results."""
    import hashlib as _hl
    head = _run(['git', 'rev-parse', 'HEAD'], cwd)[1].strip()
    subprocess.run(['git', 'add', '-N', '.'], cwd=cwd, capture_output=True, text=True)
    diff = _run(['git', 'diff', 'HEAD'], cwd)[1]
    return {'diff_hash': _hl.sha256(diff.encode()).hexdigest()[:16], 'head': head}


def verification_blockers(state, worktree, allow_cached=False):
    """Every reason the recorded test/typecheck evidence cannot approve the CURRENT patch.
    Empty list means the evidence is acceptable. Used by /approve and by the auto approval prompt."""
    why = []
    last = state.get('last_test_run') or {}
    if not isinstance(last, dict) or not last:
        return ['No test run is recorded for this patch.']
    if last.get('status') != 'passed':
        why.append('Tests must pass before committing (status: %s).' % last.get('status'))
    if last.get('source') != 'live' and not allow_cached:
        why.append('Test results are not from a live run of this patch. Re-run the tests before committing.')
    if not allow_cached:
        if last.get('exit_code') != 0:
            why.append('The test runner did not exit 0 (exit code: %s).' % last.get('exit_code'))
        if not (last.get('passed') or []):
            why.append('No test passed in the recorded run.')
        if last.get('failed'):
            why.append('The recorded run contains failures.')
        if last.get('checks_not_run'):
            why.append('Requested tests did not run: ' + ', '.join(map(str, last['checks_not_run'])))
        if not last.get('diff_hash'):
            why.append('The test run has no patch fingerprint; re-run the tests.')
    fp = _worktree_fingerprint(worktree) if worktree else {'diff_hash': '', 'head': ''}
    if last.get('diff_hash') and last['diff_hash'] != fp['diff_hash']:
        why.append('The patch changed after the tests ran. Re-run the tests.')
    if last.get('head') and fp.get('head') and last['head'] != fp['head']:
        why.append('The worktree HEAD moved after the tests ran. Re-run the tests.')
    return why


def _clear_verification(state):
    """A patch that changed invalidates every recorded test/typecheck result."""
    if state is not None:
        state['last_test_run'] = {}
        state['last_typecheck'] = {}


def _detect_runner(cwd):
    p = Path(cwd)
    if (p / 'package.json').is_file():
        return 'jest'
    if any((p / f).is_file() for f in ('pytest.ini', 'pyproject.toml', 'setup.cfg', 'conftest.py')):
        return 'pytest'
    return None


def _jest(test_files, cwd):
    cmd = ['npx', 'jest', '--json', *test_files]
    code, out, err = _run(cmd, cwd)
    try:
        report = json.loads(out)
    except json.JSONDecodeError:
        # (cmd, code, passed, failed, skipped, stderr, not_run): always seven values.
        return cmd, code, None, None, None, (out + err)[-2000:], []
    passed, failed, skipped = [], [], []
    seen_suites = []
    for suite in report.get('testResults', []):
        seen_suites.append(str(suite.get('name') or ''))
        asserts = suite.get('assertionResults', [])
        if suite.get('status') == 'failed' and not asserts:
            # Suite could not even run (syntax error, missing import): that is a failure, not "nothing ran".
            failed.append({'id': str(suite.get('name') or 'suite'),
                           'message': str(suite.get('message') or 'test suite failed to run')[:500]})
        for a in asserts:
            if a['status'] == 'passed':
                passed.append(_test_id(a['fullName']))
            elif a['status'] in ('skipped', 'pending', 'todo', 'disabled'):
                skipped.append(_test_id(a['fullName']))
            else:
                failed.append({'id': _test_id(a['fullName']),
                               'message': ' '.join(a.get('failureMessages', []))[:500]})
    not_run = [f for f in (test_files or [])
               if not any(n.replace('\\', '/').endswith(str(f).replace('\\', '/').lstrip('./'))
                          for n in seen_suites)]
    return cmd, code, passed, failed, skipped, err[-500:], not_run


def _pytest(test_files, cwd):
    xml_path = Path(cwd) / '.jarvis_junit.xml'
    cmd = ['python', '-m', 'pytest', '-q', f'--junitxml={xml_path}', *test_files]
    code, out, err = _run(cmd, cwd)
    if not xml_path.is_file():
        return cmd, code, None, None, None, (out + err)[-2000:], []
    passed, failed, skipped = [], [], []
    classnames = set()
    for case in ET.parse(xml_path).getroot().iter('testcase'):
        classname = case.get('classname', '')
        classnames.add(classname)
        name = classname + '::' + case.get('name', '')
        bad = case.find('failure')
        if bad is None:
            bad = case.find('error')      # collection errors and fixture errors land here
        if bad is not None:
            failed.append({'id': name, 'message': (bad.get('message') or '')[:500]})
        elif case.find('skipped') is not None:
            skipped.append(name)
        else:
            passed.append(name)
    xml_path.unlink(missing_ok=True)   # must not end up in the commit (commit_worktree runs git add -A)
    return cmd, code, passed, failed, skipped, err[-2000:], _pytest_not_run(test_files, classnames)


def _pytest_not_run(test_files, classnames):
    """Requested test files that produced no testcase. A junit classname is the dotted module path
    (optionally followed by a class), e.g. 'tests.test_foo' or 'tests.test_foo.TestBar'."""
    not_run = []
    for f in (test_files or []):
        path = str(f).split('::')[0]
        mod = '.'.join(Path(path).with_suffix('').parts)
        ran = any(cn == mod or cn.startswith(mod + '.') or cn.endswith('.' + mod)
                  or ('.' + mod + '.') in cn for cn in classnames)
        if not ran:
            not_run.append(f)
    return not_run


def classify_run(code, passed, failed, skipped, not_run):
    """Decide the status of a test run. Pure function so every edge case is unit-testable.

    passed       only when the runner exited 0, at least one test really passed, nothing failed,
                 and every requested test file produced results.
    failed       any failing test/collection error, OR a non-zero exit code (even if no individual
                 failure was parsed, e.g. interrupted run or crashed worker).
    unverified   nothing passed (empty or skipped-only), or requested tests never ran.
    """
    passed, failed, skipped, not_run = passed or [], list(failed or []), skipped or [], not_run or []
    if failed:
        return 'failed', failed
    if code not in (0, None):
        if not passed and not skipped:
            return 'unverified', failed          # runner produced nothing usable (e.g. exit 5: none collected)
        failed.append({'id': 'runner_exit', 'message':
                       'Test runner exited with code %s although no individual failure was parsed; '
                       'treating the run as failed.' % code})
        return 'failed', failed
    if not passed:
        return 'unverified', failed                # skipped-only or empty: never a pass
    if not_run:
        return 'unverified', failed                # requested tests that never ran
    return 'passed', failed


@safe
def run_tests(test_files: list[str], tool_context: ToolContext) -> dict:
    '''Run the given test files in the sandbox worktree. status is passed, failed, unverified or error.
    unverified means no test actually ran. Never guess a result; report exactly what ran.'''
    if USE_CACHED_TESTS:
        data = json.loads(CACHED_TESTS_PATH.read_text())
        # Cached results are labelled so /approve can refuse to treat them as
        # verification of the current patch.
        data = dict(data)
        data['source'] = 'cached'
        tool_context.state['last_test_run'] = data
        return {'source': 'cached', **data}
    cwd = tool_context.state.get('worktree')
    if not cwd:
        return {'status': 'error', 'error': 'No sandbox worktree. Call create_worktree and apply the patch first.'}
    runner = _detect_runner(cwd)
    if runner is None:
        result = {'status': 'unverified', 'source': 'live',
                  'error': 'No supported test runner found (jest or pytest). Nothing was executed.'}
        tool_context.state['last_test_run'] = result
        return result
    started = time.time()
    cmd, code, passed, failed, skipped, err, not_run = (_jest if runner == 'jest' else _pytest)(test_files, cwd)
    meta = {'source': 'live', 'runner': runner, 'command': ' '.join(cmd),
            'exit_code': code, 'duration_s': round(time.time() - started, 1)}
    meta.update(_worktree_fingerprint(cwd))
    if passed is None:
        result = {'status': 'unverified', **meta, 'passed': [], 'failed': [], 'skipped': [],
                  'checks_not_run': list(not_run or []),
                  'error': 'The test runner produced no parsable results, so nothing can be reported as passed.',
                  'stderr': err}
    else:
        status, failed = classify_run(code, passed, failed, skipped, not_run)
        result = {'status': status, **meta, 'passed': passed, 'failed': failed,
                  'skipped': skipped or [], 'checks_not_run': not_run or []}
        if status == 'unverified':
            result['error'] = ('No test passed.' if not passed else 'Requested tests did not run.') + \
                              ' Skipped or missing tests are not verification.'
    tool_context.state['last_test_run'] = result
    return result


@safe
def run_typecheck(tool_context: ToolContext) -> dict:
    '''Run the TypeScript type check in the sandbox worktree. Returns the first 40 lines of errors.'''
    if USE_CACHED_TESTS:
        res = {'status': 'ok', 'typecheck': 'passed', 'source': 'cached'}
        tool_context.state['last_typecheck'] = res
        return res
    cwd = tool_context.state.get('worktree')
    if not cwd:
        return {'status': 'error', 'error': 'No sandbox worktree. Call create_worktree first.'}
    if not (Path(cwd) / 'tsconfig.json').is_file():
        res = {'status': 'ok', 'typecheck': 'not_applicable', 'source': 'live'}
    else:
        code, out, err = _run(['npx', 'tsc', '--noEmit'], cwd)
        res = {'status': 'ok', 'typecheck': 'passed' if code == 0 else 'failed',
               'command': 'npx tsc --noEmit', 'exit_code': code,
               'errors': (out + err).splitlines()[:40], 'source': 'live'}
        res.update(_worktree_fingerprint(cwd))
    tool_context.state['last_typecheck'] = res
    return res


@safe
def read_test_results(tool_context: ToolContext) -> dict:
    '''Return the most recent test run from this session, or none if no tests have run.'''
    last = tool_context.state.get('last_test_run')
    if not last:
        return {'status': 'none'}
    return dict(last)
