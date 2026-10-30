'''Test doubles and the installed_graph context manager that points every tool at a fixture project.'''
import json
import shutil
import subprocess
import tempfile
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from .graphs import tiny_graph
from .pkg import mod
from .oracle import Oracle


class FakeToolContext:
    def __init__(self, state=None):
        self.state = dict(state or {})
        self.actions = SimpleNamespace(escalate=False)


class FakeCallbackContext:
    def __init__(self, state=None):
        self.state = dict(state or {})


class FakeTool:
    def __init__(self, name):
        self.name = name


DEFAULT_DIFF = '''diff --git a/tests/ratelimit.test.ts b/tests/ratelimit.test.ts
new file mode 100644
--- /dev/null
+++ b/tests/ratelimit.test.ts
@@ -0,0 +1,2 @@
+// rate limit regression test
+test('rate limit', () => {});
'''

DEFAULT_CHANGE = {'branch': 'feature/session-timeout', 'base': 'main', 'message': 'Shorten session timeout',
                  'changed_nodes': ['auth.validateSession'], 'diff': DEFAULT_DIFF}
PASSING_TESTS = {'status': 'passed', 'passed': ['session expires after timeout'], 'failed': [], 'not_run': []}
FAILING_TESTS = {'status': 'failed', 'passed': [],
                 'failed': [{'id': 'session expires after timeout', 'message': 'expected 401 got 200'}],
                 'not_run': []}


@dataclass
class Env:
    tmp: Path
    repo: Path
    graph: dict
    oracle: Oracle
    graph_path: Path
    change_path: Path
    tests_path: Path
    memory_path: Path
    worktree_dir: Path

    def set_cached_tests(self, data):
        self.tests_path.write_text(json.dumps(data))


def _git(args, cwd):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=True)


def write_repo(graph, repo):
    need = {}
    for n in graph['nodes']:
        need[n['file']] = max(need.get(n['file'], 0), n['end'])
    for rel, lines in need.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('\n'.join('// %s line %d' % (rel, i) for i in range(1, lines + 1)) + '\n')


@contextmanager
def installed_graph(graph=None, *, write_sources=True, git=False, change=None, cached_tests=None,
                    use_cached_tests=True):
    '''Point graph, git, exec and memory tools at a throwaway project built from `graph`.'''
    callbacks = mod('callbacks')
    exec_tools, git_tools = mod('tools.exec_tools'), mod('tools.git_tools')
    graph_tools, memory_tools = mod('tools.graph_tools'), mod('tools.memory_tools')

    graph = graph or tiny_graph()
    tmp = Path(tempfile.mkdtemp(prefix='jarvis_test_'))
    repo = tmp / 'repo'
    repo.mkdir()
    if write_sources:
        write_repo(graph, repo)
    (repo / 'tests').mkdir(exist_ok=True)
    (repo / 'README.md').write_text('fixture\n')
    env = Env(tmp=tmp, repo=repo, graph=graph, oracle=Oracle(graph),
              graph_path=tmp / 'graph.json', change_path=tmp / 'demo_change.json',
              tests_path=tmp / 'cached_tests.json', memory_path=tmp / 'memory.json',
              worktree_dir=tmp / 'work')
    env.graph_path.write_text(json.dumps(graph))
    env.change_path.write_text(json.dumps(change or DEFAULT_CHANGE))
    env.set_cached_tests(cached_tests or PASSING_TESTS)
    if git:
        _git(['init', '-q', '-b', 'main'], repo)
        _git(['config', 'user.email', 't@example.com'], repo)
        _git(['config', 'user.name', 'tester'], repo)
        _git(['add', '-A'], repo)
        _git(['commit', '-q', '-m', 'init'], repo)
    with ExitStack() as stack:
        for target, attr, val in [
            (graph_tools, 'GRAPH_PATH', env.graph_path), (graph_tools, 'REPO_ROOT', repo),
            (git_tools, 'CHANGE_PATH', env.change_path), (git_tools, 'REPO_ROOT', repo),
            (git_tools, 'WORKTREE_DIR', env.worktree_dir),
            (exec_tools, 'CACHED_TESTS_PATH', env.tests_path),
            (exec_tools, 'USE_CACHED_TESTS', use_cached_tests),
            (callbacks, 'USE_CACHED_TESTS', use_cached_tests),
            (memory_tools, 'MEMORY_PATH', env.memory_path),
        ]:
            stack.enter_context(mock.patch.object(target, attr, val))
        graph_tools._graph.cache_clear()
        try:
            yield env
        finally:
            graph_tools._graph.cache_clear()
            if git and env.worktree_dir.exists():
                for wt in env.worktree_dir.glob('wt-*'):
                    subprocess.run(['git', 'worktree', 'remove', '--force', str(wt)],
                                   cwd=repo, capture_output=True)
            shutil.rmtree(tmp, ignore_errors=True)
