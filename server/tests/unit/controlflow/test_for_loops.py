"""Test CFG construction for for loops with exact correctness assertions."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_for_loop_has_loop_back_edge():
    """Test that for loop has loop-back edge from body to header."""
    code = """
def process(items):
    for item in items:
        result = item * 2
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    loop_back_edges = [e for e in cfg.edges if e.kind == "loop_back"]
    assert len(loop_back_edges) >= 1, "Should have at least one loop-back edge"

    # Loop-back edge should target a loop_header
    for edge in loop_back_edges:
        target = cfg.get_node(edge.target)
        assert target is not None, f"Loop-back edge {edge.id} targets non-existent node"
        assert target.kind == "loop_header", f"Loop-back edge should target loop_header, got {target.kind}"


def test_for_loop_has_loop_exit_edge():
    """Test that for loop has loop-exit edge."""
    code = """
def process(items):
    for item in items:
        result = item * 2
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    loop_exit_edges = [e for e in cfg.edges if e.kind == "loop_exit"]
    assert len(loop_exit_edges) >= 1, "Should have at least one loop-exit edge"


def test_for_loop_with_break():
    """Test that break edges target loop exit."""
    code = """
def process(items):
    for item in items:
        if item == 0:
            break
        result = item * 2
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    break_edges = [e for e in cfg.edges if e.kind == "break"]
    assert len(break_edges) >= 1, "Should have at least one break edge"

    # Break should target a join node or loop exit
    for edge in break_edges:
        target = cfg.get_node(edge.target)
        assert target is not None, f"Break edge {edge.id} targets non-existent node"
        assert target.kind in ("join", "exit"), f"Break should target join or exit, got {target.kind}"


def test_for_loop_with_continue():
    """Test that continue edges target loop header."""
    code = """
def process(items):
    for item in items:
        if item == 0:
            continue
        result = item * 2
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    continue_edges = [e for e in cfg.edges if e.kind == "continue"]
    assert len(continue_edges) >= 1, "Should have at least one continue edge"

    # Continue should target loop header
    for edge in continue_edges:
        target = cfg.get_node(edge.target)
        assert target is not None, f"Continue edge {edge.id} targets non-existent node"
        assert target.kind == "loop_header", f"Continue should target loop_header, got {target.kind}"
