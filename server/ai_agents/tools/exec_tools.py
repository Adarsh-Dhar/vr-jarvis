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
        return cmd, code, None, None, err[-2000:]
    passed, failed = [], []
    for suite in report.get('testResults', []):
        for a in suite.get('assertionResults', []):
            if a['status'] == 'passed':
                passed.append(_test_id(a['fullName']))
            else:
                failed.append({'id': _test_id(a['fullName']),
                               'message': ' '.join(a.get('failureMessages', []))[:500]})
    return cmd, code, passed, failed, err[-500:]


def _pytest(test_files, cwd):
    xml_path = Path(cwd) / '.jarvis_junit.xml'
    cmd = ['python', '-m', 'pytest', '-q', f'--junitxml={xml_path}', *test_files]
    code, out, err = _run(cmd, cwd)
    if not xml_path.is_file():
        return cmd, code, None, None, (out + err)[-2000:]
    passed, failed = [], []
    for case in ET.parse(xml_path).getroot().iter('testcase'):
        name = case.get('classname', '') + '::' + case.get('name', '')
        bad = case.find('failure')
        if bad is None:
            bad = case.find('error')
        if bad is not None:
            failed.append({'id': name, 'message': (bad.get('message') or '')[:500]})
        elif case.find('skipped') is None:
            passed.append(name)
    xml_path.unlink(missing_ok=True)   # must not end up in the commit (commit_worktree runs git add -A)
    return cmd, code, passed, failed, ''


@safe
def run_tests(test_files: list[str], tool_context: ToolContext) -> dict:
    '''Run the given test files in the sandbox worktree. status is passed, failed, unverified or error.
    unverified means no test actually ran. Never guess a result; report exactly what ran.'''
    if USE_CACHED_TESTS:
        data = json.loads(CACHED_TESTS_PATH.read_text())
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
    cmd, code, passed, failed, err = (_jest if runner == 'jest' else _pytest)(test_files, cwd)
    meta = {'source': 'live', 'runner': runner, 'command': ' '.join(cmd),
            'exit_code': code, 'duration_s': round(time.time() - started, 1)}
    if passed is None or (not passed and not failed):
        result = {'status': 'unverified', **meta,
                  'error': 'No tests were executed, so nothing can be reported as passed.', 'stderr': err}
    else:
        result = {'status': 'failed' if failed else 'passed', **meta, 'passed': passed, 'failed': failed}
    tool_context.state['last_test_run'] = result
    return result


@safe
def run_typecheck(tool_context: ToolContext) -> dict:
    '''Run the TypeScript type check in the sandbox worktree. Returns the first 40 lines of errors.'''
    if USE_CACHED_TESTS:
        return {'status': 'ok', 'typecheck': 'passed', 'source': 'cached'}
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
    tool_context.state['last_typecheck'] = res
    return res


@safe
def read_test_results(tool_context: ToolContext) -> dict:
    '''Return the most recent test run from this session, or none if no tests have run.'''
    last = tool_context.state.get('last_test_run')
    if not last:
        return {'status': 'none'}
    return dict(last)
