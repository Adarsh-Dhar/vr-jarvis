"""Test DFG validation with exact correctness assertions."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder
from ai_agents.intelligence.dataflow import (
    PythonDefUseExtractor,
    ReachingDefinitionsAnalyzer,
    DataFlowGraphBuilder,
)


def test_dfg_has_unique_node_ids():
    """Test that DFG has unique node IDs."""
    code = "def process(value): return value * 2"
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

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, analysis_result)

    validation = dfg_builder.validate_dataflow_graph(cfg, facts, dfg)
    assert validation["valid"], f"DFG validation failed: {validation['errors']}"

    node_ids = [n.id for n in dfg.nodes]
    assert len(node_ids) == len(set(node_ids)), "DFG node IDs should be unique"


def test_dfg_has_unique_edge_ids():
    """Test that DFG has unique edge IDs."""
    code = "def process(value): return value * 2"
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

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, analysis_result)

    validation = dfg_builder.validate_dataflow_graph(cfg, facts, dfg)
    assert validation["valid"], f"DFG validation failed: {validation['errors']}"

    edge_ids = [e.id for e in dfg.edges]
    assert len(edge_ids) == len(set(edge_ids)), "DFG edge IDs should be unique"


def test_dfg_edges_have_valid_endpoints():
    """Test that all DFG edges reference existing nodes."""
    code = """
def calculate(price, discount):
    total = price - discount
    return total
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::calculate",
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

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, analysis_result)

    validation = dfg_builder.validate_dataflow_graph(cfg, facts, dfg)
    assert validation["valid"], f"DFG validation failed: {validation['errors']}"

    node_ids = {n.id for n in dfg.nodes}
    for edge in dfg.edges:
        assert edge.source in node_ids, f"DFG edge {edge.id} source {edge.source} does not exist"
        assert edge.target in node_ids, f"DFG edge {edge.id} target {edge.target} does not exist"


def test_dfg_cfg_node_ids_exist():
    """Test that all DFG nodes reference valid CFG node IDs."""
    code = "def process(value): return value * 2"
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

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, analysis_result)

    validation = dfg_builder.validate_dataflow_graph(cfg, facts, dfg)
    assert validation["valid"], f"DFG validation failed: {validation['errors']}"

    cfg_node_ids = {n.id for n in cfg.nodes}
    for node in dfg.nodes:
        if node.cfg_node_ids:
            assert node.cfg_node_ids[0] in cfg_node_ids, f"DFG node {node.id} references non-existent CFG node {node.cfg_node_ids[0]}"
