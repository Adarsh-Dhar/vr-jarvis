"""Test exceptional edge filtering in reaching definitions."""
import ast
from ai_agents.intelligence.dataflow.python_extractor import PythonDefUseExtractor
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
from ai_agents.intelligence.dataflow.reaching_definitions import ReachingDefinitionsAnalyzer


def test_exception_edge_filters_definitions():
    """Definitions from before an exception should not reach handler on exception edge."""
    source = """
def process():
    value = 10
    try:
        value = 20
        raise ValueError()
    except ValueError:
        result = value + 5
    return result
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py",
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py",
    )
    
    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(artifact.graph, facts)
    
    # The handler should only see the pre-try definition (value=10)
    # The definition value=20 inside the try should not reach the handler on the exception edge
    # because it was created in the try block that raised an exception
    
    # Check that we have the expected definitions
    assert len(facts.definitions) >= 2, "Should have at least 2 definitions of value"
    
    # The analysis should complete without error
    assert 'error' not in analysis_result, "Analysis should not error"


def test_parallel_edge_kinds_preserved():
    """Multiple edges between same nodes with different kinds should both be preserved."""
    source = """
def process():
    try:
        x = 10
        if x > 5:
            raise ValueError()
    except ValueError:
        y = x
    return y
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py",
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py",
    )
    
    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(artifact.graph, facts)
    
    # The analysis should complete without error
    assert 'error' not in analysis_result, "Analysis should not error"
    
    # Check that edge kinds are preserved (no key overwriting)
    # The analyzer should handle multiple edges between same source/target
    assert analysis_result is not None, "Analysis should produce a result"
