"""Test CFG construction for return statements."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_simple_return():
    """Test CFG for simple return."""
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
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check for return node
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) >= 1, "Should have at least one return node"

    # Check for return edge
    return_edges = [e for e in cfg.edges if e.kind == 'return']
    assert len(return_edges) >= 1, "Should have at least one return edge"

    # Return nodes should have no outgoing edges
    for return_node in return_nodes:
        outgoing = cfg.get_edges_from(return_node.id)
        assert len(outgoing) == 0, f"Return node {return_node.id} should have no outgoing edges"


def test_conditional_return():
    """Test CFG for conditional return."""
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
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Should have multiple return nodes
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) >= 2, "Should have at least 2 return nodes"
