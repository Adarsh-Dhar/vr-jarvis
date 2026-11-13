"""MVP gap tests: independent code review, validation-tool correctness,
planner workflow completion, and multi-framework test discovery/mapping."""
import json
import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_agents.tools import exec_tools  # noqa: E402
from ai_agents.tools import testing_verification_tools as tvt  # noqa: E402
from ai_agents.tools.exec_tools import verification_blockers  # noqa: E402


def _ctx(state):
    return SimpleNamespace(state=dict(state), agent_name='test')


# ---------------------------------------------------------------- code review gate
def _good(worktree):
    fp = exec_tools._worktree_fingerprint(str(worktree))
    return {'status': 'passed', 'source': 'live', 'exit_code': 0,
            'passed': ['t::a'], 'failed': [], 'skipped': [], 'checks_not_run': [], **fp}


@pytest.fixture
def worktree(tmp_path):
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q',
                    '--allow-empty', '-m', 'init'], cwd=tmp_path, check=True)
    return tmp_path


class TestCodeReviewGate:
    def test_rejection_blocks_commit(self, worktree):
        state = {'last_test_run': _good(worktree),
                 'code_review': {'verdict': 'changes_requested',
                                 'findings': [{'severity': 'blocker', 'file': 'a.py',
                                               'line': 1, 'issue': 'missing error handling'}],
                                 'acceptance': []}}
        why = ' '.join(verification_blockers(state, str(worktree)))
        assert 'Code review' in why and 'missing error handling' in why

    def test_rejection_as_json_string_blocks(self, worktree):
        state = {'last_test_run': _good(worktree),
                 'code_review': json.dumps({'verdict': 'rejected',
                                            'findings': [], 'acceptance': []})}
        assert 'Code review' in ' '.join(verification_blockers(state, str(worktree)))

    def test_approval_verdict_does_not_block(self, worktree):
        state = {'last_test_run': _good(worktree),
                 'code_review': {'verdict': 'approve', 'findings': [],
                                 'acceptance': []}}
        assert verification_blockers(state, str(worktree),
                                     require_security=False) == []

    def test_missing_acceptance_key_blocks_approval(self, worktree):
        state = {'last_test_run': _good(worktree),
                 'code_review': {'verdict': 'approve', 'findings': []}}
        why = ' '.join(verification_blockers(state, str(worktree)))
        assert 'code review' in why

    def test_unknown_acceptance_status_blocks(self, worktree):
        state = {'last_test_run': _good(worktree),
                 'active_task': {'acceptance_criteria': ['handles errors']},
                 'code_review': {'verdict': 'approve', 'findings': [],
                                 'acceptance': [{'criterion_index': 0,
                                                 'criterion': 'handles errors',
                                                 'status': 'unknown'}]}}
        why = ' '.join(verification_blockers(state, str(worktree)))
        assert 'acceptance' in why

    def test_not_met_acceptance_status_blocks(self, worktree):
        state = {'last_test_run': _good(worktree),
                 'active_task': {'acceptance_criteria': ['handles errors']},
                 'code_review': {'verdict': 'approve', 'findings': [],
                                 'acceptance': [{'criterion_index': 0,
                                                 'criterion': 'handles errors',
                                                 'status': 'not_met'}]}}
        why = ' '.join(verification_blockers(state, str(worktree)))
        assert 'acceptance' in why

    def test_all_criteria_met_allows_gate(self, worktree):
        state = {'last_test_run': _good(worktree),
                 'active_task': {'acceptance_criteria': ['handles errors',
                                                         'adds tests']},
                 'code_review': {'verdict': 'approve',
                                 'findings': [{'severity': 'info', 'file': 'a.py',
                                               'line': 1, 'issue': 'note'}],
                                 'acceptance': [
                                     {'criterion_index': 0,
                                      'criterion': 'handles errors',
                                      'status': 'met'},
                                     {'criterion_index': 1,
                                      'criterion': 'adds tests',
                                      'status': 'met'}]}}
        assert verification_blockers(state, str(worktree),
                                     require_security=False) == []

    def test_missing_review_blocks_commit(self, worktree):
        assert verification_blockers({'last_test_run': _good(worktree)}, str(worktree))

    def test_patch_change_clears_review(self, worktree):
        state = {'last_test_run': {}, 'last_typecheck': {}, 'code_review': {'verdict': 'approve'}}
        exec_tools._clear_verification(state)
        assert state['code_review'] == {}

    def test_reviewer_is_in_fix_pipeline(self):
        import ai_agents.agent as ag
        fix = next(s for s in ag.root_agent.sub_agents if s.name == 'fix_pipeline')
        names = [getattr(s, 'name', '') for s in fix.sub_agents]
        assert 'review_loop' in names
        review = next(s for s in fix.sub_agents if s.name == 'review_loop')
        assert 'code_reviewer' in [getattr(s, 'name', '') for s in review.sub_agents]
        assert names.index('review_loop') > names.index('verify_loop')

    def test_reviewer_output_key_and_tools(self):
        from ai_agents.agents.fix import code_reviewer
        assert code_reviewer.output_key == 'code_review'
        names = {getattr(t, '__name__', '') for t in code_reviewer.tools}
        assert {'get_worktree_diff', 'read_worktree_file', 'read_file'} <= names


class TestReadWorktreeFile:
    def test_reads_post_patch_content(self, worktree):
        from ai_agents.tools.git_tools import read_worktree_file
        (worktree / 'a.py').write_text('x = 1\n')
        subprocess.run(['git', 'add', '-A'], cwd=worktree, check=True)
        subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
                        'commit', '-qm', 'add'], cwd=worktree, check=True)
        (worktree / 'a.py').write_text('x = 2\n')
        res = read_worktree_file('a.py', _ctx({'worktree': str(worktree)}))
        assert res['status'] == 'ok' and 'x = 2' in res['content']

    def test_escape_rejected(self, worktree):
        from ai_agents.tools.git_tools import read_worktree_file
        res = read_worktree_file('../outside.py', _ctx({'worktree': str(worktree)}))
        assert res['status'] == 'error'

    def test_no_worktree_errors(self):
        from ai_agents.tools.git_tools import read_worktree_file
        assert read_worktree_file('a.py', _ctx({}))['status'] == 'error'


# ---------------------------------------------------------------- validation tools
class TestZeroPassRuns:
    def test_all_skipped_unit_tests_are_unverified(self, tmp_path):
        (tmp_path / 'tests').mkdir()
        (tmp_path / 'tests' / 'test_s.py').write_text(
            'import pytest\n@pytest.mark.skip\ndef test_a():\n    pass\n')
        res = tvt.run_unit_tests(_ctx({'worktree': str(tmp_path)}))
        assert res['status'] == 'unverified'

    def test_no_tests_collected_is_unverified(self, tmp_path):
        (tmp_path / 'tests').mkdir()
        (tmp_path / 'tests' / 'test_empty.py').write_text('# nothing\n')
        res = tvt.run_unit_tests(_ctx({'worktree': str(tmp_path)}))
        assert res['status'] == 'unverified'

    def test_passing_tests_are_ok(self, tmp_path):
        (tmp_path / 'tests').mkdir()
        (tmp_path / 'tests' / 'test_ok.py').write_text('def test_a():\n    assert True\n')
        res = tvt.run_unit_tests(_ctx({'worktree': str(tmp_path)}))
        assert res['status'] == 'ok' and res['passed'] == 1

    def test_failing_tests_are_failed(self, tmp_path):
        (tmp_path / 'tests').mkdir()
        (tmp_path / 'tests' / 'test_bad.py').write_text('def test_a():\n    assert False\n')
        res = tvt.run_unit_tests(_ctx({'worktree': str(tmp_path)}))
        assert res['status'] == 'failed'

    def test_integration_tests_use_worktree(self, tmp_path):
        res = tvt.run_integration_tests(_ctx({}))
        assert res['status'] == 'blocked'
        (tmp_path / 'tests').mkdir()
        (tmp_path / 'tests' / 'test_i.py').write_text(
            'import pytest\n@pytest.mark.integration\ndef test_i():\n    assert True\n')
        res = tvt.run_integration_tests(_ctx({'worktree': str(tmp_path)}))
        assert res['status'] in ('ok', 'unverified')


class TestVerifyLint:
    def test_linter_crash_is_error_not_success(self, tmp_path, monkeypatch):
        bindir = tmp_path / 'bin'
        bindir.mkdir()
        script = bindir / 'crashlint'
        script.write_text('#!/bin/sh\necho "Traceback" >&2\nexit 1\n')
        script.chmod(0o755)
        monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
        repo = tmp_path / 'repo'
        repo.mkdir()
        res = tvt.verify_lint(str(repo), _ctx({}), linter='crashlint')
        # exits non-zero with no diagnostics -> the lint run itself failed
        assert res['status'] == 'error'

    def test_linter_warnings_on_stderr_are_seen(self, tmp_path, monkeypatch):
        bindir = tmp_path / 'bin'
        bindir.mkdir()
        script = bindir / 'stderrlint'
        script.write_text('#!/bin/sh\necho "x.py:1: [E] bad" >&2\nexit 2\n')
        script.chmod(0o755)
        monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
        repo = tmp_path / 'repo'
        repo.mkdir()
        res = tvt.verify_lint(str(repo), _ctx({}), linter='stderrlint')
        assert res['status'] == 'ok'
        assert res['lint_check'] == 'failed'
        assert res['warnings'] and 'bad' in res['warnings'][0]

    def test_clean_linter_is_success(self, tmp_path, monkeypatch):
        bindir = tmp_path / 'bin'
        bindir.mkdir()
        script = bindir / 'cleanlint'
        script.write_text('#!/bin/sh\nexit 0\n')
        script.chmod(0o755)
        monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
        repo = tmp_path / 'repo'
        repo.mkdir()
        res = tvt.verify_lint(str(repo), _ctx({}), linter='cleanlint')
        assert res['status'] == 'ok' and res['lint_check'] == 'success'


class TestTypecheckSemantics:
    def test_ast_check_is_marked_syntax_only(self, tmp_path):
        (tmp_path / 'm.py').write_text('x = 1\n')
        ctx = _ctx({'worktree': str(tmp_path)})
        res = exec_tools.run_typecheck(ctx)
        assert res['checker'] == 'ast'
        assert res['semantic'] is False
        assert 'NOT a semantic type check' in res['note']

    def test_typescript_is_semantic(self, tmp_path):
        (tmp_path / 'tsconfig.json').write_text('{}')
        ctx = _ctx({'worktree': str(tmp_path)})
        res = exec_tools.run_typecheck(ctx)
        assert res.get('semantic') is True or res['typecheck'] == 'failed'


# ---------------------------------------------------------------- test discovery/mapping
class TestDiscoverTests:
    def test_finds_python_and_js_tests(self, tmp_path):
        (tmp_path / 'tests').mkdir()
        (tmp_path / 'tests' / 'test_a.py').write_text('')
        (tmp_path / 'src').mkdir()
        (tmp_path / 'src' / 'foo.test.ts').write_text('')
        (tmp_path / '__tests__').mkdir()
        (tmp_path / '__tests__' / 'bar.spec.js').write_text('')
        (tmp_path / 'package.json').write_text('{"devDependencies": {"jest": "^29"}}')
        res = tvt.discover_tests(str(tmp_path), _ctx({}))
        files = {t['file'] for t in res['tests_found']}
        assert 'tests/test_a.py' in files
        assert 'src/foo.test.ts' in files
        assert any(f.endswith('bar.spec.js') for f in files)
        assert res['test_framework'] == 'jest'

    def test_python_only_repo_reports_pytest(self, tmp_path):
        (tmp_path / 'tests').mkdir()
        (tmp_path / 'tests' / 'test_b.py').write_text('')
        res = tvt.discover_tests(str(tmp_path), _ctx({}))
        assert res['test_framework'] == 'pytest'


class TestMapTestsToFunctions:
    def test_ast_mapping_uses_real_calls(self, tmp_path):
        (tmp_path / 'pkg').mkdir()
        (tmp_path / 'pkg' / '__init__.py').write_text('')
        (tmp_path / 'tests').mkdir()
        (tmp_path / 'tests' / 'test_calc.py').write_text(textwrap.dedent('''
            from pkg.calc import add, multiply
            def test_adds():
                assert add(1, 2) == 3
            def test_multiplies():
                assert multiply(2, 3) == 6
        '''))
        res = tvt.map_tests_to_functions(str(tmp_path), _ctx({}))
        mapping = {(m['test'], m['function']): m for m in res['test_mapping']}
        assert ('test_adds', 'pkg.calc.add') in mapping
        assert ('test_multiplies', 'pkg.calc.multiply') in mapping
        assert mapping[('test_adds', 'pkg.calc.add')]['confidence'] == 'high'

    def test_falls_back_to_name_guess(self, tmp_path):
        (tmp_path / 'tests').mkdir()
        (tmp_path / 'tests' / 'test_utils.py').write_text(
            'def test_helper_runs():\n    pass\n')
        res = tvt.map_tests_to_functions(str(tmp_path), _ctx({}))
        m = res['test_mapping'][0]
        assert m['function'] == 'helper_runs'
        assert m['confidence'] == 'low'


# ---------------------------------------------------------------- planner workflow
class TestPlannerWorkflow:
    def test_split_subtasks_chain_dependencies(self, tmp_path):
        from ai_agents.tools import architecture_tools as at
        arch = {'components': [
            {'id': 'c1', 'name': 'A', 'kind': 'service',
             'responsibility': 'parse input. validate it. emit result.'},
            {'id': 'c2', 'name': 'B', 'kind': 'service', 'responsibility': 'store it.'},
        ], 'relationships': [
            {'id': 'e1', 'src': 'c1', 'dst': 'c2', 'kind': 'calls', 'label': ''}]}
        res = at.generate_implementation_plan(arch, graph_path=str(tmp_path / 'none.json'))
        tasks = res['tasks']
        c1_tasks = [t for t in tasks if t['component_id'] == 'c1']
        c2_tasks = [t for t in tasks if t['component_id'] == 'c2']
        assert len(c1_tasks) >= 2 and len(c2_tasks) == 1
        # c2 is scheduled first (c1 depends on it); every c1 first subtask waits on c2's task
        first = c1_tasks[0]
        assert c2_tasks[0]['id'] in first['depends_on']
        # later subtasks chain off the previous subtask of the same component
        for prev, cur in zip(c1_tasks, c1_tasks[1:]):
            assert cur['depends_on'] == [prev['id']]
        # the task graph stays acyclic and topologically ordered
        pos = {t['id']: i for i, t in enumerate(tasks)}
        for t in tasks:
            for d in t['depends_on']:
                assert d != t['id'] and pos[d] < pos[t['id']]

    def test_approve_generates_plan(self):
        from fastapi.testclient import TestClient
        import jarvis_server
        H = {'authorization': 'Bearer test-token'}
        client = TestClient(jarvis_server.app)
        monkey = pytest.MonkeyPatch()
        monkey.setattr(jarvis_server, 'extract_requirements', lambda text, tool_context=None: {
            'status': 'ok',
            'requirements': {'goals': ['g'], 'functional': ['f1'], 'non_functional': [],
                             'constraints': [], 'assumptions': [], 'open_questions': []}})
        monkey.setattr(jarvis_server, 'propose_architecture', lambda req, tool_context=None: {
            'status': 'ok',
            'components': [{'id': 'c1', 'name': 'A', 'responsibility': 'ra',
                            'kind': 'service', 'requirement_ids': []}],
            'relationships': []})
        try:
            sid = client.post('/session', headers=H).json()['session_id']
            assert client.post('/design/propose',
                               json={'session_id': sid, 'idea_text': 'x'}, headers=H).status_code == 200
            r = client.post('/design/%s/approve' % sid,
                            json={'session_id': sid, 'approved': True}, headers=H)
            assert r.status_code == 200
            plan = r.json().get('plan')
            assert plan and plan['tasks'], 'approval did not generate an implementation plan'
            view = client.get('/design/' + sid, headers=H).json()
            assert view['plan']['tasks']
        finally:
            monkey.undo()

    def test_architecture_agent_instruction_covers_planning(self):
        from ai_agents.agents.architecture_design import INSTRUCTION
        assert 'generate_implementation_plan' in INSTRUCTION


class TestMvpPatchAdditions:
    def test_variable_id_accepts_hash_and_colon(self):
        from ai_agents.tools.data_flow_intelligence_tools import _split_variable_id
        assert _split_variable_id('process:value') == ('process', 'value')
        assert _split_variable_id('process#value') == ('process', 'value')

    def test_vitest_detection(self, tmp_path):
        import json
        from ai_agents.tools import exec_tools
        from ai_agents.tools import testing_verification_tools as tvt
        (tmp_path / 'package.json').write_text(json.dumps({'devDependencies': {'vitest': '^1'}}))
        assert exec_tools._detect_runner(str(tmp_path)) == 'vitest'
        class Ctx:
            state = {}
        res = tvt.discover_tests(str(tmp_path), Ctx())
        assert res['test_framework'] == 'vitest'

    def test_python_mapping_fallback_is_per_test(self, tmp_path):
        from ai_agents.tools import testing_verification_tools as tvt
        (tmp_path / 'test_x.py').write_text('''def foo():
    pass

def test_a():
    foo()

def test_b():
    assert True
''')
        class Ctx:
            state = {}
        res = tvt.map_tests_to_functions(str(tmp_path), Ctx())
        by_test = {m['test']: m for m in res['test_mapping']}
        assert by_test['test_a']['confidence'] == 'high'
        assert by_test['test_b']['confidence'] == 'low'

    def test_planner_suggests_new_file_for_unmatched_component(self, tmp_path, monkeypatch):
        from ai_agents import config
        from ai_agents.tools import architecture_tools as at
        monkeypatch.setattr(config, 'REPO_ROOT', tmp_path)
        (tmp_path / 'pkg').mkdir()
        (tmp_path / 'pkg' / 'mod.py').write_text('x = 1\n')
        arch = {'components': [{'id': 'c1', 'name': 'Novel Service', 'kind': 'service',
                                'responsibility': 'do novel work', 'requirement_ids': []}],
                'relationships': []}
        res = at.generate_implementation_plan(arch, graph_path=str(tmp_path / 'missing.json'))
        assert res['tasks'][0]['new_files']
        assert not (tmp_path / res['tasks'][0]['new_files'][0]).exists()

    def test_architecture_edit_tools_round_trip(self):
        from types import SimpleNamespace
        from ai_agents.tools import architecture_edit_tools as aet
        arch = {'version': 3, 'revision': 1, 'status': 'approved', 'components': [],
                'relationships': [], 'approved_by': 'u', 'approved_version': 3,
                'approved_revision': 1, 'open_questions': []}
        ctx = SimpleNamespace(state={'design': arch, 'session_id': ''})
        res = aet.add_component('Payments', 'Handle payments', 'service', ctx)
        assert res['status'] == 'ok'
        got = aet.get_proposed_architecture(ctx)
        assert got['architecture']['components'][0]['name'] == 'Payments'
        assert got['architecture']['revision'] == 2
        assert got['architecture']['status'] == 'draft'
        assert ctx.state['implementation_plan'] == {}

    def test_recent_commits(self, tmp_path):
        import subprocess
        from types import SimpleNamespace
        from ai_agents.tools import git_tools
        subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
        (tmp_path / 'a.py').write_text('x=1\n')
        subprocess.run(['git', 'add', 'a.py'], cwd=tmp_path, check=True)
        subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', 'JARVIS: first'], cwd=tmp_path, check=True)
        res = git_tools.get_recent_commits(SimpleNamespace(state={'worktree': str(tmp_path)}), limit=1)
        assert res['status'] == 'ok' and res['commits'][0]['source'] == 'jarvis'
