"""Test CFG construction for while loops with exact correctness assertions."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_while_loop_has_loop_back_edge():
    """Test that while loop has loop-back edge."""
    code = """
def process(value):
    while value > 0:
        value = value - 1
    return value
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

    loop_back_edges = [e for e in cfg.edges if e.kind == "loop_back"]
    assert len(loop_back_edges) >= 1, "Should have at least one loop-back edge"


def test_while_loop_with_break():
    """Test that while loop with break has correct break edges."""
    code = """
def process(value):
    while value > 0:
        if value == 5:
            break
        value = value - 1
    return value
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

    break_edges = [e for e in cfg.edges if e.kind == "break"]
    assert len(break_edges) >= 1, "Should have at least one break edge"
