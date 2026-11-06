"""Test CFG construction for return statements with exact correctness assertions."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_return_has_return_edge():
    """Test that return statements have return edges to exit."""
    code = """
def process(value):
    return value * 2
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

    return_edges = [e for e in cfg.edges if e.kind == "return"]
    assert len(return_edges) >= 1, "Should have at least one return edge"

    # Return edge should target exit
    for edge in return_edges:
        assert edge.target == cfg.exit_node_id, "Return edge should target exit"


def test_conditional_return():
    """Test that conditional returns create multiple return nodes."""
    code = """
def process(value):
    if value < 0:
        return 0
    return value * 2
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

    return_nodes = [n for n in cfg.nodes if n.kind == "return"]
    assert len(return_nodes) >= 2, "Should have at least 2 return nodes for conditional return"
