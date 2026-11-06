"""Test data-flow graph construction."""
import ast
import pytest
from ai_agents.intelligence.dataflow import (
    PythonDefUseExtractor,
    ReachingDefinitionsAnalyzer,
    DataFlowGraphBuilder,
)
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_dfg_construction():
    """Test data-flow graph construction."""
    code = """
def process(value):
    x = value * 2
    y = x + 1
    return y
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    # Build CFG
    cfg_builder = PythonCFGBuilder()
    cfg = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )

    # Extract definition/use facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        cfg=cfg,
        file_path="test.py"
    )

    # Perform reaching definitions analysis
    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(cfg, facts)

    # Build data-flow graph
    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, analysis_result)

    # Should have nodes for definitions and uses
    assert len(dfg.nodes) > 0, "Should have at least one node"

    # Should have edges for data flow
    assert len(dfg.edges) > 0, "Should have at least one edge"

    # Check metadata
    assert dfg.metadata['language'] == 'python', "Language should be python"
    assert dfg.metadata['scope'] == 'intra_function', "Scope should be intra_function"


def test_dfg_to_dict():
    """Test data-flow graph serialization."""
    code = "def process(value): return value * 2"
    tree = ast.parse(code)
    func_node = tree.body[0]

    # Build CFG
    cfg_builder = PythonCFGBuilder()
    cfg = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )

    # Extract definition/use facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        cfg=cfg,
        file_path="test.py"
    )

    # Perform reaching definitions analysis
    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(cfg, facts)

    # Build data-flow graph
    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, analysis_result)

    # Convert to dict
    dfg_dict = dfg.to_dict()

    # Check dict structure
    assert 'function_id' in dfg_dict, "Should have function_id"
    assert 'file' in dfg_dict, "Should have file"
    assert 'nodes' in dfg_dict, "Should have nodes"
    assert 'edges' in dfg_dict, "Should have edges"
    assert 'metadata' in dfg_dict, "Should have metadata"
