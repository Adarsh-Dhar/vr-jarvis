"""
Quality tests for the architecture -> plan -> evidence pipeline.

Covers the audit P0 items that test_design_lifecycle.py does not:
provenance (model vs heuristic fallback), repository-grounded comparison
(unique node assignment + relationship type semantics), repository-grounded
implementation tasks, and independent task-evidence verification.
"""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_agents.tools import architecture_tools as at  # noqa: E402
from ai_agents import config  # noqa: E402


# ---------------------------------------------------------------------------
# helpers


def _write_graph(tmp_path, nodes, edges):
    p = tmp_path / 'graph.json'
    p.write_text(json.dumps({'nodes': nodes, 'edges': edges}))
    return str(p)


def _module(nid, name):
    return {'id': 'module::' + nid, 'name': name, 'kind': 'module',
            'level': 'module', 'file': nid, 'parent': None}


def _file(nid, rel, parent):
    return {'id': 'file::' + rel, 'name': rel.rsplit('/', 1)[-1], 'kind': 'file',
            'level': 'file', 'file': rel, 'parent': parent}


def _func(nid, name, rel, parent):
    return {'id': nid, 'name': name, 'qualname': name, 'kind': 'function',
            'level': 'function', 'file': rel, 'parent': parent}


# ---------------------------------------------------------------------------
# provenance: model vs heuristic


class _FakeModels:
    def __init__(self, payload):
        self.payload = payload

    def generate_content(self, *a, **k):
        return SimpleNamespace(text=json.dumps(self.payload))


class _FakeClient:
    payload = {}

    def __init__(self, *a, **k):
        self.models = _FakeModels(_FakeClient.payload)


@pytest.fixture
def fake_genai(monkeypatch):
    import google.genai
    monkeypatch.setattr(google.genai, 'Client', _FakeClient)
    return _FakeClient


class TestProvenance:
    def test_model_source_reported(self, fake_genai):
        _FakeClient.payload = {
            'components': [{'id': 'c1', 'name': 'A', 'responsibility': 'r',
                            'kind': 'service'}],
            'relationships': []}
        res = at.propose_architecture({'goals': ['g'], 'functional': ['f']})
        assert res['source'] == 'model'
        assert res['components'][0]['name'] == 'A'

    def test_llm_failure_reports_heuristic(self, monkeypatch):
        import google.genai

        def boom(*a, **k):
            raise RuntimeError('no api key')
        monkeypatch.setattr(google.genai, 'Client', boom)
        res = at.propose_architecture({'goals': ['g'], 'functional': ['f1', 'f2']})
        assert res['source'] == 'heuristic'
        # heuristic fallback still produces a usable chained proposal
        assert len(res['components']) == 2
        assert res['relationships']

    def test_empty_model_output_reports_heuristic(self, fake_genai):
        _FakeClient.payload = {'components': 'not-a-list', 'relationships': []}
        res = at.propose_architecture({'goals': ['g'], 'functional': ['f']})
        assert res['source'] == 'heuristic'

    def test_requirements_source_reported(self, fake_genai):
        _FakeClient.payload = {'goals': ['ship it'], 'functional': ['f']}
        res = at.extract_requirements('an idea')
        assert res['source'] == 'model'
        assert res['requirements']['goals'] == ['ship it']


# ---------------------------------------------------------------------------
# repository comparison


class TestCompareToRepository:
    def _graph(self, tmp_path):
        nodes = [
            _module('auth', 'auth'),
            _file('file::auth/x.ts', 'auth/x.ts', 'module::auth'),
            _module('services', 'services'),
            _file('file::services/y.ts', 'services/y.ts', 'module::services'),
            _func('services/y.ts::handle', 'handle', 'services/y.ts',
                  'file::services/y.ts'),
        ]
        edges = [
            {'src': 'file::services/y.ts', 'dst': 'file::auth/x.ts',
             'type': 'calls', 'kind': 'confirmed'},
            {'src': 'module::services', 'dst': 'module::auth',
             'type': 'imports', 'kind': 'confirmed'},
        ]
        return _write_graph(tmp_path, nodes, edges)

    def test_components_match_modules_uniquely(self, tmp_path):
        gp = self._graph(tmp_path)
        arch = {'components': [
            {'id': 'c1', 'name': 'Auth', 'responsibility': '', 'kind': 'service'},
            {'id': 'c2', 'name': 'Services', 'responsibility': '', 'kind': 'service'},
            {'id': 'c3', 'name': 'Auth', 'responsibility': '', 'kind': 'service'},
        ], 'relationships': []}
        res = at.compare_to_repository(arch, graph_path=gp)
        by_id = {m['id']: m for m in res['matched']}
        missing = {m['id'] for m in res['missing']}
        # c1 takes module::auth (exact); c3 cannot reuse it and falls back to
        # the file inside auth/ via fuzzy containment.
        assert by_id['c1']['node'] == 'module::auth'
        assert by_id['c1']['confidence'] == 'high'
        assert by_id['c3']['node'] == 'file::auth/x.ts'
        assert by_id['c3']['confidence'] == 'low'
        assert by_id['c2']['node'] == 'module::services'
        assert not missing
        # no two components share a node
        nodes = [m['node'] for m in res['matched']]
        assert len(nodes) == len(set(nodes))

    def test_relationship_type_semantics(self, tmp_path):
        gp = self._graph(tmp_path)
        arch = {'components': [
            {'id': 'c1', 'name': 'Auth', 'responsibility': '', 'kind': 'service'},
            {'id': 'c2', 'name': 'Services', 'responsibility': '', 'kind': 'service'},
        ], 'relationships': [
            {'id': 'e1', 'src': 'c2', 'dst': 'c1', 'kind': 'calls', 'label': ''},
            {'id': 'e2', 'src': 'c2', 'dst': 'c1', 'kind': 'reads', 'label': ''},
            {'id': 'e3', 'src': 'c1', 'dst': 'c2', 'kind': 'calls', 'label': ''},
        ]}
        res = at.compare_to_repository(arch, graph_path=gp)
        rels = {r['id']: r for r in res['relationships']}
        # services -> auth has a confirmed calls edge: confirmed.
        assert rels['e1']['status'] == 'confirmed'
        # reads maps to imports: the module-level imports edge confirms it.
        assert rels['e2']['status'] == 'confirmed'
        # auth -> services only exists in the reverse direction: wrong_direction.
        assert rels['e3']['status'] == 'wrong_direction'

    def test_type_mismatch_reported_not_confirmed(self, tmp_path):
        gp = _write_graph(tmp_path,
                          [_module('a', 'a'), _module('b', 'b')],
                          [{'src': 'module::a', 'dst': 'module::b',
                            'type': 'imports', 'kind': 'confirmed'}])
        arch = {'components': [
            {'id': 'c1', 'name': 'A', 'responsibility': '', 'kind': 'service'},
            {'id': 'c2', 'name': 'B', 'responsibility': '', 'kind': 'service'},
        ], 'relationships': [
            {'id': 'e1', 'src': 'c1', 'dst': 'c2', 'kind': 'calls', 'label': ''}]}
        res = at.compare_to_repository(arch, graph_path=gp)
        rel = res['relationships'][0]
        # connectivity exists but an imports edge cannot confirm 'calls'.
        assert rel['status'] == 'wrong_type'
        assert 'does not match' in rel['evidence']

    def test_unmatched_endpoint(self, tmp_path):
        gp = self._graph(tmp_path)
        arch = {'components': [
            {'id': 'c1', 'name': 'Auth', 'responsibility': '', 'kind': 'service'},
            {'id': 'c2', 'name': 'Nonexistent', 'responsibility': '', 'kind': 'service'},
        ], 'relationships': [
            {'id': 'e1', 'src': 'c1', 'dst': 'c2', 'kind': 'calls', 'label': ''}]}
        res = at.compare_to_repository(arch, graph_path=gp)
        assert res['relationships'][0]['status'] == 'unmatched'


# ---------------------------------------------------------------------------
# implementation plan grounding


class TestPlanGrounding:
    def test_tasks_have_files_symbols_criteria(self, tmp_path):
        nodes = [
            _module('auth', 'auth'),
            _file('file::auth/x.ts', 'auth/x.ts', 'module::auth'),
            _func('auth/x.ts::verify', 'verify', 'auth/x.ts', 'file::auth/x.ts'),
            _func('auth/x.ts::issue', 'issue', 'auth/x.ts', 'file::auth/x.ts'),
        ]
        edges = [
            {'src': 'auth/x.ts::verify', 'dst': 'auth/x.ts::issue',
             'type': 'calls', 'kind': 'confirmed'},
        ]
        gp = _write_graph(tmp_path, nodes, edges)
        arch = {'components': [
            {'id': 'c1', 'name': 'Auth', 'responsibility': 'handle auth',
             'kind': 'service'}],
            'relationships': []}
        res = at.generate_implementation_plan(arch, graph_path=gp)
        task = res['tasks'][0]
        assert task['repo_match'] == 'repository'
        assert task['files'] == ['auth/x.ts']
        names = [s['name'] for s in task['symbols']]
        # issue has an incoming confirmed call -> ranked first
        assert names[0] == 'issue'
        assert any('auth/x.ts' in c for c in task['acceptance_criteria'])
        assert any('handle auth' in c for c in task['acceptance_criteria'])

    def test_unmatched_component_marked(self, tmp_path):
        gp = _write_graph(tmp_path, [_module('a', 'a')], [])
        arch = {'components': [
            {'id': 'c1', 'name': 'Zebra', 'responsibility': 'r', 'kind': 'service'}],
            'relationships': []}
        res = at.generate_implementation_plan(arch, graph_path=gp)
        task = res['tasks'][0]
        assert task['repo_match'] == 'unmatched'
        assert task['files'] == []
        assert any('No repository component matched' in c
                   for c in task['acceptance_criteria'])


# ---------------------------------------------------------------------------
# evidence verification


class TestVerifyTaskEvidence:
    def _git_repo(self, tmp_path):
        repo = tmp_path / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
        subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t',
                        'commit', '-q', '--allow-empty', '-m', 'init'],
                       cwd=repo, check=True)
        sha = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                             cwd=repo, capture_output=True, text=True).stdout.strip()
        (repo / 'tests').mkdir()
        (repo / 'tests' / 'test_thing.py').write_text(
            'def test_thing():\n    assert True\n')
        return repo, sha

    def test_real_commit_and_pytest_id_verified(self, tmp_path):
        repo, sha = self._git_repo(tmp_path)
        res = at.verify_task_evidence(
            'commit %s; tests/test_thing.py::test_thing passed' % sha,
            repo_root=repo)
        assert res['verdict'] == 'verified'
        kinds = {c['kind']: c['status'] for c in res['checks']}
        assert kinds['commit'] == 'verified'
        assert kinds['pytest'] == 'verified'

    def test_fabricated_commit_fails(self, tmp_path):
        repo, _sha = self._git_repo(tmp_path)
        res = at.verify_task_evidence('fixed in commit deadbeef',
                                      repo_root=repo)
        assert res['verdict'] == 'failed'
        assert any(c['status'] == 'failed' and c['kind'] == 'commit'
                   for c in res['checks'])

    def test_missing_test_file_fails(self, tmp_path):
        repo, _sha = self._git_repo(tmp_path)
        res = at.verify_task_evidence(
            'tests/test_thing.py::test_nonexistent passed', repo_root=repo)
        assert res['verdict'] == 'failed'

    def test_uncheckable_claims_are_unverified_not_failed(self, tmp_path):
        repo, _sha = self._git_repo(tmp_path)
        res = at.verify_task_evidence('manual review by the developer',
                                      repo_root=repo)
        assert res['verdict'] == 'unverified'
        assert res['checks'] == []

    def test_graph_node_id_verified(self, tmp_path):
        gp = _write_graph(tmp_path, [_module('a', 'a')], [])
        res = at.verify_task_evidence('touched module::a', graph_path=gp,
                                      repo_root=tmp_path / 'nonexistent')
        assert res['verdict'] == 'verified'
