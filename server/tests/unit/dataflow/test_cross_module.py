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
        imports=['module2'],
        exports=[]
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
    global_usage = analyzer.propagate_globals(all_summaries)

    assert 'module1' in global_usage
    # module1 imports module2, so it uses module2's globals
