"""Regression tests for CFG lifecycle and completion architecture."""
import pytest
import ast
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
from ai_agents.intelligence.controlflow.validator import validate_cfg


def test_empty_function():
    """Test that empty functions connect entry directly to exit."""
    source = """
def empty():
    pass
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::empty", source, "test.py")
    cfg = artifact.graph

    # Should have entry and exit nodes
    assert cfg.entry_node_id is not None
    assert cfg.exit_node_id is not None

    # Entry should connect to something (pass statement creates a node)
    entry_edges = cfg.get_edges_from(cfg.entry_node_id)
    assert len(entry_edges) >= 1

    # The pass statement node should connect to exit
    pass_nodes = [n for n in cfg.nodes if n.kind == 'statement']
    if pass_nodes:
        pass_edges = cfg.get_edges_from(pass_nodes[0].id)
        assert any(e.target == cfg.exit_node_id for e in pass_edges)


def test_straight_line_function():
    """Test straight-line code connects sequentially."""
    source = """
def straight():
    x = 1
    y = 2
    z = 3
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::straight", source, "test.py")
    cfg = artifact.graph

    # Should have a valid path from entry to exit
    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_return():
    """Test return statement connects to exit."""
    source = """
def returns():
    return 42
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::returns", source, "test.py")
    cfg = artifact.graph

    # Find return node
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) == 1

    # Return should connect to exit
    return_edges = cfg.get_edges_from(return_nodes[0].id)
    assert len(return_edges) >= 1
    assert any(e.target == cfg.exit_node_id and e.kind == 'return' for e in return_edges)


def test_raise():
    """Test raise statement connects to exception exit."""
    source = """
def raises():
    raise ValueError("error")
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::raises", source, "test.py")
    cfg = artifact.graph

    # Should have exception exit
    assert cfg.exception_exit_node_id is not None

    # Find raise node
    raise_nodes = [n for n in cfg.nodes if n.kind == 'raise']
    assert len(raise_nodes) == 1

    # Raise should connect to exception exit
    raise_edges = cfg.get_edges_from(raise_nodes[0].id)
    assert len(raise_edges) >= 1
    assert any(e.target == cfg.exception_exit_node_id and e.kind == 'raise' for e in raise_edges)


def test_if_no_else():
    """Test if without else has false edge as normal continuation."""
    source = """
def if_no_else(x):
    if x:
        y = 1
    z = 2
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::if_no_else", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_both_branches_return():
    """Test if where both branches return has no normal continuation."""
    source = """
def both_return(x):
    if x:
        return 1
    else:
        return 2
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::both_return", source, "test.py")
    cfg = artifact.graph

    # Find condition node
    condition_nodes = [n for n in cfg.nodes if n.kind == 'condition']
    assert len(condition_nodes) == 1

    # Condition should have two outgoing edges (true and false)
    condition_edges = cfg.get_edges_from(condition_nodes[0].id)
    assert len(condition_edges) == 2

    # Both branches should end in return nodes
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) == 2


def test_one_branch_returns():
    """Test if where one branch returns and other continues normally."""
    source = """
def one_returns(x):
    if x:
        return 1
    y = 2
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::one_returns", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_unreachable_after_return():
    """Test unreachable code after return is diagnosed."""
    source = """
def unreachable():
    return 1
    x = 2  # unreachable
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::unreachable", source, "test.py")
    cfg = artifact.graph

    # Should have a diagnostic about unreachable code
    diagnostics = cfg.metadata.get('diagnostics', [])
    unreachable_diags = [d for d in diagnostics if d.get('code') == 'unreachable_statement']
    assert len(unreachable_diags) > 0


def test_nested_branches():
    """Test nested if statements with multiple completions."""
    source = """
def nested(x, y):
    if x:
        if y:
            return 1
        else:
            return 2
    else:
        z = 3
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::nested", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_exit_nodes_exist_before_body():
    """Test that exit nodes are created before body is built."""
    source = """
def early_exit():
    return 1
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::early_exit", source, "test.py")
    cfg = artifact.graph

    # Both exit nodes should exist
    assert cfg.exit_node_id is not None
    assert cfg.exception_exit_node_id is not None

    # Completion objects should have valid targets
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) == 1
    return_edges = cfg.get_edges_from(return_nodes[0].id)
    assert any(e.target == cfg.exit_node_id for e in return_edges)


def test_for_loop_break_else():
    """Test that break bypasses else in for loops."""
    source = """
def for_break_else():
    for i in range(10):
        if i == 5:
            break
    else:
        # This should execute only on natural exhaustion
        x = 1
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::for_break_else", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check that break target bypasses else
    break_nodes = [n for n in cfg.nodes if n.label == 'break']
    if break_nodes:
        break_edges = cfg.get_edges_from(break_nodes[0].id)
        # Break should go to post_loop, not through else
        assert all(e.kind == 'break' for e in break_edges)


def test_sequential_suite_unreachable():
    """Test that _build_suite marks unreachable statements correctly."""
    source = """
def seq_unreachable():
    return 1
    x = 2  # unreachable
    y = 3  # also unreachable
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::seq_unreachable", source, "test.py")
    cfg = artifact.graph

    # Should have unreachable diagnostics
    diagnostics = cfg.metadata.get('diagnostics', [])
    unreachable_diags = [d for d in diagnostics if d.get('code') == 'unreachable_statement']
    assert len(unreachable_diags) >= 2  # Both x and y are unreachable


def test_completion_targets_valid():
    """Test that all completions have valid intended targets."""
    source = """
def all_completions(x):
    if x:
        return 1
    raise ValueError("error")
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::all_completions", source, "test.py")
    cfg = artifact.graph

    # Find all nodes
    node_ids = {n.id for n in cfg.nodes}

    # Check return edge
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    if return_nodes:
        return_edges = cfg.get_edges_from(return_nodes[0].id)
        for edge in return_edges:
            assert edge.target in node_ids, f"Return edge target {edge.target} not in nodes"

    # Check raise edge
    raise_nodes = [n for n in cfg.nodes if n.kind == 'raise']
    if raise_nodes:
        raise_edges = cfg.get_edges_from(raise_nodes[0].id)
        for edge in raise_edges:
            assert edge.target in node_ids, f"Raise edge target {edge.target} not in nodes"
