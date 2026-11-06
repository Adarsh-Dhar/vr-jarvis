"""Test CFG construction for if-else statements with exact correctness assertions."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_if_else_has_correct_branch_edges():
    """Test that if-else has true and false edges from condition."""
    code = """
def process(value):
    if value > 10:
        result = 1
    else:
        result = 2
    return result
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    builder = PythonCFGBuilder()
    artifact = builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    # Find condition node
    condition_nodes = [n for n in cfg.nodes if n.kind == "condition"]
    assert len(condition_nodes) >= 1, "Should have at least one condition node"

    condition = condition_nodes[0]
    outgoing = cfg.get_edges_from(condition.id)

    # Should have both true and false edges
    true_edges = [e for e in outgoing if e.kind == "true"]
    false_edges = [e for e in outgoing if e.kind == "false"]

    assert len(true_edges) >= 1, "Should have at least one true edge"
    assert len(false_edges) >= 1, "Should have at least one false edge"

    # All edge targets should exist
    for edge in outgoing:
        assert cfg.get_node(edge.target) is not None, f"Edge {edge.id} targets non-existent node {edge.target}"


def test_if_else_has_join_node():
    """Test that if-else creates a join node."""
    code = """
def process(value):
    if value:
        result = 1
    else:
        result = 2
    return result
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    builder = PythonCFGBuilder()
    artifact = builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    join_nodes = [n for n in cfg.nodes if n.kind == "join"]
    assert len(join_nodes) >= 1, "Should have at least one join node"


def test_nested_if_branches():
    """Test that nested if branches are correctly connected."""
    code = """
def process(value):
    if value:
        if value > 10:
            result = 1
        else:
            result = 2
    else:
        result = 0
    return result
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    builder = PythonCFGBuilder()
    artifact = builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    # Should have multiple condition nodes
    condition_nodes = [n for n in cfg.nodes if n.kind == "condition"]
    assert len(condition_nodes) >= 2, "Should have at least 2 condition nodes for nested if"
