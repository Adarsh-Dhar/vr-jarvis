"""v13 blocker tests: strict test classification, approval evidence, repo switching, fix-pipeline permissions."""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_agents.tools import exec_tools  # noqa: E402
from ai_agents.tools.exec_tools import classify_run, verification_blockers  # noqa: E402


# --------------------------------------------------------------------------- classify_run (pure)
class TestClassifyRun:
    def test_all_skipped_is_never_passed(self):
        assert classify_run(0, [], [], ['t::a', 't::b'], [])[0] == 'unverified'

    def test_empty_run_is_unverified(self):
        assert classify_run(0, [], [], [], [])[0] == 'unverified'

    def test_nonzero_exit_with_passes_and_no_parsed_failure_is_failed(self):
        status, failed = classify_run(2, ['t::a'], [], [], [])
        assert status == 'failed'
        assert failed and failed[0]['id'] == 'runner_exit'

    def test_exit_5_nothing_collected_is_unverified(self):
        assert classify_run(5, [], [], [], [])[0] == 'unverified'

    def test_requested_test_missing_is_unverified(self):
        assert classify_run(0, ['t::a'], [], [], ['tests/test_missing.py'])[0] == 'unverified'

    def test_real_failure_is_failed(self):
        assert classify_run(1, ['t::a'], [{'id': 't::b', 'message': 'x'}], [], [])[0] == 'failed'

    def test_clean_run_passes(self):
        assert classify_run(0, ['t::a'], [], ['t::s'], [])[0] == 'passed'


# --------------------------------------------------------------------------- real pytest runs
@pytest.fixture
def project(tmp_path):
    (tmp_path / 'pytest.ini').write_text('[pytest]\n')
    (tmp_path / 'tests').mkdir()
    return tmp_path


def _write(project, name, body):
    (project / 'tests' / name).write_text(textwrap.dedent(body))


def _run(project, files):
    cmd, code, passed, failed, skipped, err, not_run = exec_tools._pytest(files, str(project))
    return code, passed, failed, skipped, not_run


class TestPytestParsing:
    def test_nested_test_file_is_not_reported_as_not_run(self, project):
        _write(project, 'test_ok.py', 'def test_a():\n    assert True\n')
        code, passed, failed, skipped, not_run = _run(project, ['tests/test_ok.py'])
        assert code == 0 and passed and not not_run      # used to report tests/test_ok.py as not run

    def test_all_skipped(self, project):
        _write(project, 'test_s.py', 'import pytest\n@pytest.mark.skip\ndef test_a():\n    pass\n')
        code, passed, failed, skipped, not_run = _run(project, ['tests/test_s.py'])
        assert classify_run(code, passed, failed, skipped, not_run)[0] == 'unverified'

    def test_collection_error_is_failed(self, project):
        _write(project, 'test_bad.py', 'import module_that_does_not_exist\n')
        code, passed, failed, skipped, not_run = _run(project, ['tests/test_bad.py'])
        assert classify_run(code, passed, failed, skipped, not_run)[0] == 'failed'

    def test_partial_execution_is_unverified(self, project):
        _write(project, 'test_ok.py', 'def test_a():\n    assert True\n')
        code, passed, failed, skipped, not_run = _run(project, ['tests/test_ok.py', 'tests/test_never.py'])
        assert 'tests/test_never.py' in not_run
        assert classify_run(code, passed, failed, skipped, not_run)[0] != 'passed'


# --------------------------------------------------------------------------- approval evidence
@pytest.fixture
def worktree(tmp_path):
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q',
                    '--allow-empty', '-m', 'init'], cwd=tmp_path, check=True)
    return tmp_path


def _good(worktree):
    fp = exec_tools._worktree_fingerprint(str(worktree))
    return {'status': 'passed', 'source': 'live', 'exit_code': 0, 'passed': ['t::a'], 'failed': [],
            'skipped': [], 'checks_not_run': [], **fp}


class TestVerificationBlockers:
    def test_good_run_has_no_blockers(self, worktree):
        assert verification_blockers({'last_test_run': _good(worktree)}, str(worktree)) == []

    @pytest.mark.parametrize('field,value,needle', [
        ('exit_code', 1, 'exit 0'),
        ('passed', [], 'No test passed'),
        ('checks_not_run', ['tests/x.py'], 'did not run'),
        ('diff_hash', '', 'fingerprint'),
        ('diff_hash', 'deadbeefdeadbeef', 'patch changed'),
        ('source', 'cached', 'not from a live run'),
    ])
    def test_each_defect_blocks(self, worktree, field, value, needle):
        run = _good(worktree)
        run[field] = value
        why = ' '.join(verification_blockers({'last_test_run': run}, str(worktree)))
        assert needle in why

    def test_no_run_at_all_blocks(self, worktree):
        assert verification_blockers({}, str(worktree))


# --------------------------------------------------------------------------- permissions for fix_pipeline
class TestFixPipelinePermissions:
    @pytest.mark.parametrize('agent,tool', [
        ('patch_agent', 'create_worktree'), ('patch_agent', 'apply_patch_to_worktree'),
        ('patch_agent', 'record_task_targets'), ('patch_repair_agent', 'apply_patch_to_worktree'),
        ('verifier_agent', 'run_tests'), ('verifier_agent', 'run_typecheck')])
    def test_fix_pipeline_tools_are_not_blocked_by_ceiling(self, agent, tool):
        from types import SimpleNamespace
        from ai_agents.callbacks import permission_guard
        ctx = SimpleNamespace(state={'worktree': '/tmp'}, agent_name=agent)
        res = permission_guard(SimpleNamespace(name=tool), {}, ctx)
        assert not (res and res.get('status') == 'blocked'), res

    def test_patch_agent_is_task_aware(self):
        from ai_agents.agents.fix import patch_agent
        assert '{active_task}' in patch_agent.instruction
        assert 'record_task_targets' in [getattr(t, '__name__', '') for t in patch_agent.tools]

    def test_placeholder_tools_are_not_exposed(self):
        from ai_agents.agents.toolsets import TOOLSETS
        for name in ('generate_function', 'generate_class', 'extract_function', 'rename_symbol'):
            assert name not in TOOLSETS['software_engineering']


# --------------------------------------------------------------------------- repository switching
class TestRepoSwitching:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        import jarvis_server
        return TestClient(jarvis_server.app)

    H = {'authorization': 'Bearer test-token'}

    def _sid(self, client):
        return client.post('/session', headers=self.H).json()['session_id']

    def _set(self, sid, delta):
        import asyncio
        import jarvis_server
        asyncio.run(jarvis_server.set_state(sid, delta))

    def test_switch_refused_for_pending_approval_without_worktree(self, client):
        sid = self._sid(client)
        self._set(sid, {'pending_approval': 'x'})
        assert client.post('/repos/select', json={'name': 'anything'}, headers=self.H).status_code == 409
        self._set(sid, {'pending_approval': ''})

    def test_switch_refused_for_unpromoted_commit(self, client):
        sid = self._sid(client)
        self._set(sid, {'last_commit': {'branch': 'jarvis/fix-abc', 'commit': 'deadbeef'}})
        assert client.post('/repos/select', json={'name': 'anything'}, headers=self.H).status_code == 409
        self._set(sid, {'last_commit': {}})

    def test_switch_refused_while_agent_request_runs(self, client):
        import asyncio
        import jarvis_server
        sid = self._sid(client)

        async def probe():
            async with jarvis_server.locks[sid]:
                return await jarvis_server._sessions_blocking_switch()
        assert any(s == sid for s, _ in asyncio.run(probe()))

    def test_successful_switch_tells_client_to_reset_session(self, client):
        import jarvis_server
        from ai_agents import repository
        names = repository.list_repos()
        if not names:
            pytest.skip('no repositories configured')
        r = client.post('/repos/select', json={'name': names[0]}, headers=self.H)
        if r.status_code == 200:
            assert r.json()['session_reset_required'] is True

    def test_ask_rechecks_repo_while_holding_session_lock(self, client, monkeypatch):
        """Regression: the repo checks must run under the session lock. Before the
        fix they ran before lock acquisition, so a /repos/select could slip into
        the gap between the check and the turn."""
        import jarvis_server
        from ai_agents.tools import graph_tools
        sid = self._sid(client)

        monkeypatch.setattr(graph_tools, '_graph',
                            lambda: {'nodes': {}, 'out': {}, 'in': {}, 'tests': [], 'coverage': {}})

        lock_states = []
        orig_require = jarvis_server._require_active_repo

        def spy(name):
            lock_states.append(jarvis_server.locks[sid].locked())
            return orig_require(name)
        monkeypatch.setattr(jarvis_server, '_require_active_repo', spy)

        async def fake_turn(body):
            # Mid-turn the session lock is held, so the switch guard must report
            # this session as a blocker.
            blockers = await jarvis_server._sessions_blocking_switch()
            assert any(s == sid for s, _ in blockers)
            return 'ok'
        monkeypatch.setattr(jarvis_server, '_run_turn', fake_turn)

        r = client.post('/ask', json={'session_id': sid, 'text': 'hi'}, headers=self.H)
        assert r.status_code == 200
        # The outer check runs unlocked (fast fail); the authoritative re-check
        # inside the session lock must be the last one and must see the lock held.
        assert lock_states[-1] is True


# --------------------------------------------------------------------------- navigator repository switching
class TestNavigatorRepoSwitch:
    @pytest.fixture
    def scene_tools(self, monkeypatch):
        from types import SimpleNamespace
        from ai_agents.tools import scene_tools as st
        fake_store = SimpleNamespace(
            list_repos=lambda: ['repoA', 'repoB'],
            activate=lambda name: pytest.fail('open_vr_repository must not activate a repository'),
            info=lambda n: {'name': n})
        fake_config = SimpleNamespace(REPO_ROOT=SimpleNamespace(name='repoA'))
        monkeypatch.setattr(st, '_repo_api', lambda: (fake_config, fake_store))
        return st

    @staticmethod
    def _ctx(state=None):
        from types import SimpleNamespace
        return SimpleNamespace(state=dict(state or {}))

    def test_requests_switch_without_activating(self, scene_tools):
        ctx = self._ctx()
        res = scene_tools.open_vr_repository('repoB', ctx)
        assert res['status'] == 'ok' and res['switch_requested'] == 'repoB'
        assert res['active'] == 'repoA'                      # still the old repo until Unity confirms
        assert ctx.state['scene_commands'] == [{'type': 'open_repo', 'repo': 'repoB'}]

    def test_unknown_repo_is_an_error(self, scene_tools):
        res = scene_tools.open_vr_repository('nope', self._ctx())
        assert res['status'] == 'error'

    @pytest.mark.parametrize('state', [
        {'pending_approval': 'commit it'},
        {'worktree': '/tmp/wt'},
        {'last_commit': {'branch': 'jarvis/x', 'commit': 'abc'}},
    ])
    def test_unfinished_session_is_blocked(self, scene_tools, state):
        ctx = self._ctx(state)
        res = scene_tools.open_vr_repository('repoB', ctx)
        assert res['status'] == 'blocked'
        assert 'scene_commands' not in ctx.state


# --------------------------------------------------------------------------- type check gate
def _ts_typecheck(worktree, **over):
    tc = {'typecheck': 'passed', 'source': 'live', **exec_tools._worktree_fingerprint(str(worktree))}
    tc.update(over)
    return tc


class TestTypecheckGate:
    @pytest.fixture
    def ts_worktree(self, worktree):
        (worktree / 'tsconfig.json').write_text('{}')
        return worktree

    @staticmethod
    def _why(worktree, tc):
        state = {'last_test_run': _good(worktree)}
        if tc is not None:
            state['last_typecheck'] = tc
        return ' '.join(verification_blockers(state, str(worktree)))

    def test_good_typecheck_has_no_blockers(self, ts_worktree):
        assert verification_blockers(
            {'last_test_run': _good(ts_worktree), 'last_typecheck': _ts_typecheck(ts_worktree)},
            str(ts_worktree)) == []

    def test_no_tsconfig_means_no_typecheck_required(self, worktree):
        assert verification_blockers(
            {'last_test_run': _good(worktree)}, str(worktree)) == []

    def test_missing_typecheck_blocks(self, ts_worktree):
        assert 'Type check has not been run' in self._why(ts_worktree, None)

    @pytest.mark.parametrize('over,needle', [
        ({'typecheck': 'failed'}, 'Type check failed'),
        ({'typecheck': 'not_applicable'}, 'has not passed'),
        ({'source': 'cached'}, 'cached, not live'),
        ({'diff_hash': ''}, 'no patch fingerprint'),
        ({'head': ''}, 'no worktree HEAD'),
        ({'diff_hash': 'deadbeefdeadbeef'}, 'patch changed'),
        ({'head': '0' * 40}, 'HEAD moved'),
    ])
    def test_each_defect_blocks(self, ts_worktree, over, needle):
        assert needle in self._why(ts_worktree, _ts_typecheck(ts_worktree, **over))

    def test_prompt_matches_approval(self, ts_worktree):
        import asyncio
        import jarvis_server
        cases = [None,
                 _ts_typecheck(ts_worktree, diff_hash=''),
                 _ts_typecheck(ts_worktree, head=''),
                 _ts_typecheck(ts_worktree, diff_hash='deadbeefdeadbeef'),
                 _ts_typecheck(ts_worktree, head='0' * 40),
                 _ts_typecheck(ts_worktree, source='cached')]
        for tc in cases:
            state = {'last_test_run': _good(ts_worktree), 'worktree': str(ts_worktree),
                     'proposed_patch': 'diff --git a/x b/x', 'pending_approval': ''}
            if tc is not None:
                state['last_typecheck'] = tc
            assert asyncio.run(jarvis_server._maybe_prompt_commit('sid-tc', state, '')) == ''
