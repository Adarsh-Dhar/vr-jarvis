"""Tests for cross-file and cross-module propagation."""
import pytest
from ai_agents.intelligence.dataflow.cross_module import (
    CrossModuleAnalyzer,
    ModuleSummary
)
from ai_agents.intelligence.dataflow.models import DefUseFacts


def test_analyze_module():
    """Test that a module can be analyzed."""
    analyzer = CrossModuleAnalyzer()

    facts = DefUseFacts(
        function_id='test::module',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    summary = analyzer.analyze_module(facts, 'test.py')

    assert summary.module_id == 'test.py'
    assert summary.file_path == 'test.py'


def test_module_summary_storage():
    """Test that module summaries are stored."""
    analyzer = CrossModuleAnalyzer()

    facts = DefUseFacts(
        function_id='test::module',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    analyzer.analyze_module(facts, 'test.py')

    retrieved = analyzer.get_module_summary('test.py')
    assert retrieved is not None
    assert retrieved.file_path == 'test.py'


def test_propagate_globals():
    """Test that globals can be propagated across modules."""
    analyzer = CrossModuleAnalyzer()

    # Create mock summaries
    summary1 = ModuleSummary(
        module_id='module1',
        file_path='module1.py',
        top_level_definitions=['def1', 'def2'],
        global_writes=[],
        imports=['import module2'],
        exports=[],
        metadata={'import_details': [
            {'module': 'module2', 'name': None, 'level': 0, 'kind': 'import'}]}
    )

    summary2 = ModuleSummary(
        module_id='module2',
        file_path='module2.py',
        top_level_definitions=['def3'],
        global_writes=[],
        imports=[],
        exports=[]
    )

    all_summaries = {'module1': summary1, 'module2': summary2}
    result = analyzer.propagate_globals(all_summaries)

    assert 'global_usage' in result
    assert 'unresolved_imports' in result
    global_usage = result['global_usage']
    assert 'module1' in global_usage
    # module1 imports module2, so it uses module2's globals


class _FakeResolver:
    """Minimal stand-in for PythonResolver._resolve_import_target."""

    def __init__(self, mapping):
        # mapping: (module, name, level, kind) -> (sid, kind, file)
        self.mapping = mapping

    def _resolve_import_target(self, imp, file_path, graph_ctx, depth=0):
        key = (imp.get('module'), imp.get('name'), imp.get('level', 0),
               imp.get('kind'))
        return self.mapping.get(key, (None, 'unresolved', ''))


def _analyzer_with(mapping):
    return CrossModuleAnalyzer(graph_ctx={'module_files': {}},
                               resolver=_FakeResolver(mapping))


def test_resolve_import_relative_and_alias():
    analyzer = _analyzer_with({
        ('a.b', 'c', 0, 'import'): (None, 'module', 'a/b.py'),
        ('ext', 'ext', 0, 'import'): (None, 'external', ''),
    })
    # parsed imp dict delegates to the resolver
    assert analyzer.resolve_import(
        {'module': 'mod', 'name': 'thing', 'level': 1, 'kind': 'from'},
        'pkg/other.py') is None  # not in fake mapping -> unresolved
    # 'import a.b as c' style
    assert analyzer.resolve_import('import a.b as c', 'x.py') == 'a/b.py'
    # third-party -> external marker
    assert analyzer.resolve_import('import ext', 'x.py') == 'external'
    # unresolvable -> None
    assert analyzer.resolve_import('import missing_mod', 'x.py') is None


def test_analyze_module_top_level_and_exports(tmp_path):
    src = tmp_path / 'mod.py'
    src.write_text(
        'import os\n'
        'CONST = 1\n'
        '__all__ = ["CONST", "helper"]\n'
        'def helper():\n'
        '    GLOBAL_X = 2\n'
        '    global G\n'
        '    G = 3\n'
        'def _private():\n'
        '    pass\n')
    analyzer = CrossModuleAnalyzer()
    facts = DefUseFacts(function_id='mod', file=str(src),
                        definitions=[], uses=[], operations=[])
    summary = analyzer.analyze_module(facts, str(src))
    assert summary.exports == ['CONST', 'helper']


def test_propagate_globals_worklist_and_unresolved():
    mapping = {
        ('b', 'b', 0, 'import'): (None, 'module', 'b.py'),
        ('missing', 'missing', 0, 'import'): (None, 'unresolved', ''),
        ('c', 'c', 0, 'import'): (None, 'module', 'c.py'),
    }
    analyzer = _analyzer_with(mapping)
    s_a = ModuleSummary(module_id='a.py', file_path='a.py',
                        top_level_definitions=['a::X'], global_writes=[],
                        imports=['import b', 'import missing'], exports=[],
                        metadata={'import_details': [
                            {'module': 'b', 'name': None, 'level': 0,
                             'kind': 'import'},
                            {'module': 'missing', 'name': None, 'level': 0,
                             'kind': 'import'}]})
    s_b = ModuleSummary(module_id='b.py', file_path='b.py',
                        top_level_definitions=['b::Y'], global_writes=[],
                        imports=['import c'], exports=[],
                        metadata={'import_details': [
                            {'module': 'c', 'name': None, 'level': 0,
                             'kind': 'import'}]})
    s_c = ModuleSummary(module_id='c.py', file_path='c.py',
                        top_level_definitions=['c::Z'], global_writes=[],
                        imports=[], exports=[])
    result = analyzer.propagate_globals(
        {'a.py': s_a, 'b.py': s_b, 'c.py': s_c})
    usage = result['global_usage']
    # transitive: a -> b -> c
    assert 'b::Y' in usage['a.py']
    assert 'c::Z' in usage['a.py']
    assert any(u['reason'] == 'unresolved' for u in result['unresolved_imports'])


def test_propagate_globals_circular_import():
    mapping = {
        ('b', 'b', 0, 'import'): (None, 'module', 'b.py'),
    }
    analyzer = _analyzer_with(mapping)
    s_a = ModuleSummary(module_id='a.py', file_path='a.py',
                        top_level_definitions=['a::X'], global_writes=[],
                        imports=['import b'], exports=[],
                        metadata={'import_details': [
                            {'module': 'b', 'name': None, 'level': 0,
                             'kind': 'import'}]})
    s_b = ModuleSummary(module_id='b.py', file_path='b.py',
                        top_level_definitions=['b::Y'], global_writes=[],
                        imports=['import a'], exports=[],
                        metadata={'import_details': [
                            {'module': 'a', 'name': None, 'level': 0,
                             'kind': 'import'}]})
    # 'a' module isn't in module_files mapping -> unresolved, no cycle hang
    result = analyzer.propagate_globals({'a.py': s_a, 'b.py': s_b})
    assert 'b::Y' in result['global_usage']['a.py']
