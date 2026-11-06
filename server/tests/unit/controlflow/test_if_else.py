"""Test CFG construction for if-else statements."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_simple_if_else():
    """Test CFG for simple if-else."""
    code = """
def process(amount):
    if amount > 100:
        discount = 20
    else:
        discount = 0
    total = amount - discount
    return total
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

    # Validate CFG
    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check for entry node
    entry_nodes = [n for n in cfg.nodes if n.kind == 'entry']
    assert len(entry_nodes) == 1, "Should have exactly one entry node"

    # Check for condition node
    condition_nodes = [n for n in cfg.nodes if n.kind == 'condition']
    assert len(condition_nodes) >= 1, "Should have at least one condition node"

    # Check for join node
    join_nodes = [n for n in cfg.nodes if n.kind == 'join']
    assert len(join_nodes) >= 1, "Should have at least one join node"

    # Check for return node
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) >= 1, "Should have at least one return node"

    # Check for true and false edges
    true_edges = [e for e in cfg.edges if e.kind == 'true']
    false_edges = [e for e in cfg.edges if e.kind == 'false']
    assert len(true_edges) >= 1, "Should have at least one true edge"
    assert len(false_edges) >= 1, "Should have at least one false edge"


def test_nested_if():
    """Test CFG for nested if statements."""
    code = """
def process(value):
    if value:
        if value > 100:
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
    cfg = builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Should have multiple condition nodes for nested ifs
    condition_nodes = [n for n in cfg.nodes if n.kind == 'condition']
    assert len(condition_nodes) >= 2, "Should have at least 2 condition nodes for nested if"


def test_if_without_else():
    """Test CFG for if without else."""
    code = """
def process(value):
    if value:
        result = 1
    return result
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
