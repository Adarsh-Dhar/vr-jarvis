import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
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
    # ---- type check (TypeScript and Python projects) -----------------------------------------
    tc = state.get('last_typecheck') or {}
    if tc.get('typecheck') == 'failed':
        why.append('Type check failed. Fix it before committing.')
    needs_tc = bool(worktree) and _typecheck_kind(worktree) is not None
    if needs_tc:
        if not tc:
            why.append('Type check has not been run for this patch. Run it before committing.')
        else:
            if tc.get('typecheck') not in ('passed', 'failed'):
                why.append('Type check has not passed for this patch (status: %s).' % tc.get('typecheck'))
            if not allow_cached:
                if tc.get('source') != 'live':
                    why.append('Type check results are cached, not live. Re-run it before committing.')
                if not tc.get('diff_hash'):
                    why.append('The type check has no patch fingerprint. Re-run it.')
                if not tc.get('head'):
                    why.append('The type check has no worktree HEAD record. Re-run it.')
            if tc.get('diff_hash') and tc['diff_hash'] != fp['diff_hash']:
                why.append('The patch changed after the type check ran. Re-run it.')
            if tc.get('head') and fp.get('head') and tc['head'] != fp['head']:
                why.append('The worktree HEAD moved after the type check ran. Re-run it.')
    return why


def _clear_verification(state):
    """A patch that changed invalidates every recorded test/typecheck result."""
    if state is not None:
        state['last_test_run'] = {}
        state['last_typecheck'] = {}


# Directories never worth walking when probing a worktree for tests, Python
# sources or type-check targets (vendored trees can be enormous).
_SKIP_WALK_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env',
    '.tox', '.nox', 'build', 'dist', '.pytest_cache', '.mypy_cache',
    '.ruff_cache', '.next', '.nuxt', 'target', 'vendor',
}


def _iter_files(root, suffix, limit=4000):
    """Yield paths ending in `suffix` under `root`, pruning vendored and
    hidden directories. Bounded by `limit` matches."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in _SKIP_WALK_DIRS and not d.startswith('.')]
        for fn in filenames:
            if fn.endswith(suffix):
                yield os.path.join(dirpath, fn)
                count += 1
                if count >= limit:
                    return


def _python_layout(root):
    """(has_tests, has_sources, pytest_declared) for a Python-ish tree.

    pytest_declared covers the classic markers plus requirements/setup files
    that mention pytest; has_tests covers test_*.py / *_test.py modules even
    when the project ships no pytest configuration at all (the rp fixture is
    exactly this shape: tests/test_pipeline.py + requirements.txt)."""
    p = Path(root)
    pytest_declared = any((p / f).is_file()
                          for f in ('pytest.ini', 'pyproject.toml', 'setup.cfg',
                                    'tox.ini', 'conftest.py'))
    if not pytest_declared:
        for name in ('requirements.txt', 'requirements-dev.txt', 'setup.py', 'Pipfile'):
            f = p / name
            if f.is_file():
                try:
                    if 'pytest' in f.read_text(errors='ignore').lower():
                        pytest_declared = True
                        break
                except OSError:
                    pass
    has_tests = has_sources = False
    for fp in _iter_files(root, '.py', limit=20000):
        has_sources = True
        base = os.path.basename(fp)
        if base.startswith('test_') or base.endswith('_test.py'):
            has_tests = True
            break          # a test module is itself a source: both flags set
    return has_tests, has_sources, pytest_declared


def _detect_runner(cwd):
    p = Path(cwd)
    has_pkg = (p / 'package.json').is_file()
    uses_jest = False
    if has_pkg:
        try:
            pkg = json.loads((p / 'package.json').read_text())
        except Exception:
            pkg = {}
        deps = {}
        for k in ('dependencies', 'devDependencies', 'peerDependencies'):
            deps.update(pkg.get(k) or {})
        # Serialise values only — a literal 'jest' key name must not count.
        blob = json.dumps([deps, pkg.get('scripts') or {}, pkg.get('jest')])
        uses_jest = 'jest' in blob
        if uses_jest:
            return 'jest'
    has_tests, _src, pytest_declared = _python_layout(cwd)
    if pytest_declared or has_tests:
        return 'pytest'
    if has_pkg:
        # Preserve the previous behaviour for JS projects: attempt jest and let
        # the run report 'unverified' if the project cannot actually execute it.
        return 'jest'
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
    cmd = [sys.executable, '-m', 'pytest', '-q', f'--junitxml={xml_path}', *test_files]
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


def _typecheck_kind(worktree):
    """Which verification gate applies to this worktree: 'typescript'
    (tsconfig.json), 'python' (any .py source outside vendored dirs), or None."""
    p = Path(worktree)
    if (p / 'tsconfig.json').is_file():
        return 'typescript'
    for _ in _iter_files(worktree, '.py', limit=1):
        return 'python'
    return None


_PY_AST_CHECK = (
    "import ast, os, sys\n"
    "skip = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env',\n"
    "        '.tox', '.nox', 'build', 'dist', '.pytest_cache', '.mypy_cache',\n"
    "        '.ruff_cache', 'target', 'vendor'}\n"
    "bad = []\n"
    "for dp, dn, fn in os.walk(sys.argv[1]):\n"
    "    dn[:] = [d for d in dn if d not in skip and not d.startswith('.')]\n"
    "    for f in fn:\n"
    "        if not f.endswith('.py'):\n"
    "            continue\n"
    "        path = os.path.join(dp, f)\n"
    "        try:\n"
    "            with open(path, encoding='utf-8', errors='replace') as fh:\n"
    "                ast.parse(fh.read(), filename=path)\n"
    "        except SyntaxError as exc:\n"
    "            bad.append('%s:%s: %s' % (path, exc.lineno, exc.msg))\n"
    "        except Exception as exc:\n"
    "            bad.append('%s: %s' % (path, exc))\n"
    "for line in bad[:40]:\n"
    "    print(line)\n"
    "sys.exit(1 if bad else 0)\n"
)


def _mypy_configured(p):
    """True when the project opts into mypy via a config file."""
    if any((p / f).is_file() for f in ('mypy.ini', '.mypy.ini')):
        return True
    for name, marker in (('setup.cfg', '[mypy'), ('pyproject.toml', '[tool.mypy')):
        f = p / name
        if f.is_file():
            try:
                if marker in f.read_text(errors='ignore'):
                    return True
            except OSError:
                pass
    return False


def _mypy_argv():
    """argv for a real mypy run, or None when no mypy is installed."""
    try:
        if importlib.util.find_spec('mypy'):
            return [sys.executable, '-m', 'mypy', '.']
    except Exception:
        pass
    exe = shutil.which('mypy')
    return [exe, '.'] if exe else None


def _pyright_argv():
    for name in ('pyright', 'basedpyright'):
        exe = shutil.which(name)
        if exe:
            return [exe]
    return None


def _python_typecheck(cwd):
    """Strongest available Python check for the worktree.

    A real mypy/pyright run only happens when the project configures one —
    running mypy on an unconfigured legacy tree would fail on missing imports
    and block valid patches. Otherwise every .py file is AST-parsed so syntax
    errors still gate the patch. The chosen checker is reported in 'checker'
    so the result is never mistaken for a full type check."""
    p = Path(cwd)
    if _mypy_configured(p):
        argv = _mypy_argv()
        if argv:
            code, out, err = _run(argv, cwd)
            return {'typecheck': 'passed' if code == 0 else 'failed',
                    'command': ' '.join(argv), 'exit_code': code,
                    'checker': 'mypy', 'language': 'python',
                    'errors': (out + err).splitlines()[:40]}
    if (p / 'pyrightconfig.json').is_file():
        argv = _pyright_argv()
        if argv:
            code, out, err = _run(argv, cwd)
            return {'typecheck': 'passed' if code == 0 else 'failed',
                    'command': ' '.join(argv), 'exit_code': code,
                    'checker': 'pyright', 'language': 'python',
                    'errors': (out + err).splitlines()[:40]}
    code, out, err = _run([sys.executable, '-c', _PY_AST_CHECK, '.'], cwd)
    return {'typecheck': 'passed' if code == 0 else 'failed',
            'command': 'python -c <ast parse check>', 'exit_code': code,
            'checker': 'ast', 'language': 'python',
            'errors': (out + err).splitlines()[:40]}


@safe
def run_typecheck(tool_context: ToolContext) -> dict:
    '''Run the type/syntax check for the sandbox worktree: tsc --noEmit for
    TypeScript (tsconfig.json), mypy/pyright when a Python project configures
    them, an AST parse check for other Python projects. not_applicable when
    the worktree has neither.'''
    if USE_CACHED_TESTS:
        res = {'status': 'ok', 'typecheck': 'passed', 'source': 'cached'}
        tool_context.state['last_typecheck'] = res
        return res
    cwd = tool_context.state.get('worktree')
    if not cwd:
        return {'status': 'error', 'error': 'No sandbox worktree. Call create_worktree first.'}
    kind = _typecheck_kind(cwd)
    if kind == 'typescript':
        code, out, err = _run(['npx', 'tsc', '--noEmit'], cwd)
        res = {'status': 'ok', 'typecheck': 'passed' if code == 0 else 'failed',
               'command': 'npx tsc --noEmit', 'exit_code': code,
               'language': 'typescript', 'source': 'live',
               'errors': (out + err).splitlines()[:40]}
    elif kind == 'python':
        res = {'status': 'ok', 'source': 'live'}
        res.update(_python_typecheck(cwd))
    else:
        res = {'status': 'ok', 'typecheck': 'not_applicable', 'source': 'live'}
    if res.get('typecheck') != 'not_applicable':
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
