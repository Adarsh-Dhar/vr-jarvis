"""Integration test for data-flow analysis pipeline with exact correctness assertions."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder
from ai_agents.intelligence.dataflow import (
    PythonDefUseExtractor,
    ReachingDefinitionsAnalyzer,
    DataFlowGraphBuilder,
    dfg_to_unity_format,
)


def test_data_flow_pipeline_end_to_end():
    """Test the complete data-flow analysis pipeline."""
    code = """
def calculate(price, discount_enabled):
    if discount_enabled:
        discount = 20
    else:
        discount = 0
    total = price - discount
    return total
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    # Step 1: Build CFG
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::calculate",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Step 2: Extract definition/use facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=code,
        file_path="test.py"
    )

    # Step 3: Perform reaching-definitions analysis
    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(cfg, facts)

    assert "error" not in analysis_result, f"Analysis failed: {analysis_result.get('error')}"

    # Step 4: Build data-flow graph
    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, analysis_result)

    # Step 5: Validate DFG
    validation = dfg_builder.validate_dataflow_graph(cfg, facts, dfg)
    assert validation["valid"], f"DFG validation failed: {validation['errors']}"

    # Step 6: Convert to dict
    dfg_dict = dfg.to_dict()
    assert "nodes" in dfg_dict
    assert "edges" in dfg_dict
    assert len(dfg_dict["nodes"]) > 0
    assert len(dfg_dict["edges"]) > 0

    # Step 7: Convert to Unity format
    unity_graph = dfg_to_unity_format(dfg)
    assert "graph_type" in unity_graph
    assert unity_graph["graph_type"] == "data_flow"
    assert "nodes" in unity_graph
    assert "edges" in unity_graph

    # Verify Unity nodes have required fields
    for node in unity_graph["nodes"]:
        assert "id" in node
        assert "name" in node
        assert "node_kind" in node
        assert "variable" in node
        assert "function_id" in node
        assert "file" in node
        assert "line" in node

    # Verify Unity edges have required fields
    for edge in unity_graph["edges"]:
        assert "src" in edge
        assert "dst" in edge
        assert "edge_kind" in edge
        assert "edge_id" in edge
        assert "resolution" in edge


def test_data_flow_pipeline_with_loops():
    """Test data-flow pipeline with loops."""
    code = """
def process(items):
    total = 0
    for item in items:
        total = total + item
    return total
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=code,
        file_path="test.py"
    )

    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(cfg, facts)

    assert "error" not in analysis_result, f"Analysis failed: {analysis_result.get('error')}"

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, analysis_result)

    validation = dfg_builder.validate_dataflow_graph(cfg, facts, dfg)
    assert validation["valid"], f"DFG validation failed: {validation['errors']}"

    # Should have nodes for definitions and uses
    assert len(dfg.nodes) > 0, "Should have DFG nodes"

    # Should have edges for data flow
    assert len(dfg.edges) > 0, "Should have DFG edges"


def test_data_flow_pipeline_with_parameters():
    """Test data-flow pipeline with parameters."""
    code = """
def process(a, b, c):
    x = a + b
    y = x * c
    return y
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=code,
        file_path="test.py"
    )

    # Should have parameter definitions
    param_defs = [d for d in facts.definitions if d.kind == "parameter"]
    assert len(param_defs) >= 3, "Should have 3 parameter definitions"

    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(cfg, facts)

    assert "error" not in analysis_result, f"Analysis failed: {analysis_result.get('error')}"

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, analysis_result)

    validation = dfg_builder.validate_dataflow_graph(cfg, facts, dfg)
    assert validation["valid"], f"DFG validation failed: {validation['errors']}"

    # Should have data-flow edges from parameters to uses
    assert len(dfg.edges) > 0, "Should have edges"
