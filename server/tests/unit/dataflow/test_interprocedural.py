"""Tests for interprocedural function summaries."""
import pytest
from ai_agents.intelligence.dataflow.interprocedural import (
    InterproceduralSummaryBuilder,
    FunctionSummary,
    CallGraph
)
from ai_agents.intelligence.dataflow.python_extractor import PythonDefUseExtractor
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
import ast


def test_build_call_graph():
    """Test that a call graph can be built from function facts."""
    builder = InterproceduralSummaryBuilder()

    # Create mock function facts
    from ai_agents.intelligence.dataflow.models import DefUseFacts

    facts1 = DefUseFacts(
        function_id='test::caller',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    facts2 = DefUseFacts(
        function_id='test::callee',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    call_graph = builder.build_call_graph([facts1, facts2])

    assert len(call_graph.nodes) == 2
    assert 'test::caller' in call_graph.nodes
    assert 'test::callee' in call_graph.nodes


def test_compute_function_summary():
    """Test that a function summary can be computed."""
    builder = InterproceduralSummaryBuilder()

    code = '''
def f(x):
    return x + 1
'''

    tree = ast.parse(code)
    func_def = tree.body[0]
    function_id = 'test::f'

    cfg_builder = PythonCFGBuilder()
    cfg_artifact = cfg_builder.build_function(
        function_ast=func_def,
        function_id=function_id,
        source=code,
        file_path='test.py'
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    summary = builder._compute_function_summary(facts, {}, {})

    assert summary.function_id == 'test::f'
    assert summary.params == ['x']
    assert summary.content_hash is not None


def test_compute_summaries_with_callees():
    """Test that summaries are computed with callee information."""
    builder = InterproceduralSummaryBuilder()

    code1 = '''
def f(x):
    return x + 1
'''

    code2 = '''
def g(y):
    return f(y) + 2
'''

    # Parse both functions
    tree1 = ast.parse(code1)
    tree2 = ast.parse(code2)

    func1 = tree1.body[0]
    func2 = tree2.body[0]

    # Build CFGs and extract facts
    cfg_builder = PythonCFGBuilder()
    extractor = PythonDefUseExtractor()

    cfg_artifact1 = cfg_builder.build_function(
        function_ast=func1,
        function_id='test::f',
        source=code1,
        file_path='test.py'
    )
    facts1 = extractor.extract_function(
        artifact=cfg_artifact1,
        source=code1,
        file_path='test.py'
    )

    cfg_artifact2 = cfg_builder.build_function(
        function_ast=func2,
        function_id='test::g',
        source=code2,
        file_path='test.py'
    )
    facts2 = extractor.extract_function(
        artifact=cfg_artifact2,
        source=code2,
        file_path='test.py'
    )

    summaries = builder.compute_summaries([facts1, facts2])

    assert 'test::f' in summaries
    assert 'test::g' in summaries


def test_invalidate_function():
    """Test that function invalidation works."""
    builder = InterproceduralSummaryBuilder()

    from ai_agents.intelligence.dataflow.models import DefUseFacts

    facts = DefUseFacts(
        function_id='test::f',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    # Compute summary
    summary = builder._compute_function_summary(facts, {}, {})
    builder._summaries['test::f'] = summary

    # Invalidate
    builder.invalidate_function('test::f')

    assert 'test::f' not in builder._summaries


def test_get_summary():
    """Test that computed summaries can be retrieved."""
    builder = InterproceduralSummaryBuilder()

    from ai_agents.intelligence.dataflow.models import DefUseFacts

    facts = DefUseFacts(
        function_id='test::f',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    summary = builder._compute_function_summary(facts, {}, {})
    builder._summaries['test::f'] = summary

    retrieved = builder.get_summary('test::f')
    assert retrieved is not None
    assert retrieved.function_id == 'test::f'
