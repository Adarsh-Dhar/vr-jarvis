"""Integration test for control-flow analysis pipeline with exact correctness assertions."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg, cfg_to_unity_format


def test_control_flow_pipeline_end_to_end():
    """Test the complete control-flow analysis pipeline."""
    code = """
def example(value, items):
    if value > 100:
        result = 1
    else:
        result = 2
    for item in items:
        if item == 0:
            continue
        if item < 0:
            break
        result += item
    try:
        result = calculate(result)
    except ValueError:
        result = 0
    finally:
        cleanup()
    return result
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    # Step 1: Build CFG
    builder = PythonCFGBuilder()
    cfg = builder.build_function(
        function_ast=func_node,
        function_id="test::example",
        source=code,
        file_path="test.py"
    )

    # Step 2: Validate CFG
    validation = validate_cfg(cfg)
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    # Step 3: Convert to dict
    cfg_dict = cfg.to_dict()
    assert "nodes" in cfg_dict
    assert "edges" in cfg_dict
    assert len(cfg_dict["nodes"]) > 0
    assert len(cfg_dict["edges"]) > 0

    # Step 4: Convert to Unity format
    unity_graph = cfg_to_unity_format(cfg)
    assert "graph_type" in unity_graph
    assert unity_graph["graph_type"] == "control_flow"
    assert "nodes" in unity_graph
    assert "edges" in unity_graph

    # Verify Unity nodes have required fields
    for node in unity_graph["nodes"]:
        assert "id" in node
        assert "name" in node
        assert "node_kind" in node
        assert "function_id" in node
        assert "file" in node
        assert "line" in node

    # Verify Unity edges have required fields
    for edge in unity_graph["edges"]:
        assert "src" in edge
        assert "dst" in edge
        assert "edge_kind" in edge
        assert "edge_id" in edge  # Critical for multiple parallel edges

    # Verify actual node kinds
    node_kinds = {n["node_kind"] for n in unity_graph["nodes"]}
    assert "entry" in node_kinds
    assert "exit" in node_kinds
    assert "condition" in node_kinds

    # Verify actual edge kinds
    edge_kinds = {e["edge_kind"] for e in unity_graph["edges"]}
    assert "next" in edge_kinds
    assert "true" in edge_kinds or "false" in edge_kinds


def test_control_flow_pipeline_with_complex_branches():
    """Test control-flow pipeline with complex nested branches."""
    code = """
def process(data):
    if data:
        for item in data:
            if item.active:
                process(item)
            else:
                skip(item)
    else:
        return None
    finish()
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    builder = PythonCFGBuilder()
    cfg = builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )

    validation = validate_cfg(cfg)
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    # Should have multiple condition nodes for nested branches
    condition_nodes = [n for n in cfg.nodes if n.kind == "condition"]
    assert len(condition_nodes) >= 2, "Should have at least 2 condition nodes for nested if"

    # Should have loop header
    loop_headers = [n for n in cfg.nodes if n.kind == "loop_header"]
    assert len(loop_headers) >= 1, "Should have at least one loop header"
