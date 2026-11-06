"""Test CFG construction for while loops."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_simple_while_loop():
    """Test CFG for simple while loop."""
    code = """
def process(value):
    while value > 0:
        value = value - 1
    return value
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

    # Check for loop header
    loop_headers = [n for n in cfg.nodes if n.kind == 'loop_header']
    assert len(loop_headers) >= 1, "Should have at least one loop header"

    # Check for loop-back edge
    loop_back_edges = [e for e in cfg.edges if e.kind == 'loop_back']
    assert len(loop_back_edges) >= 1, "Should have at least one loop-back edge"


def test_while_loop_with_break():
    """Test CFG for while loop with break."""
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
    cfg = builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check for break edge
    break_edges = [e for e in cfg.edges if e.kind == 'break']
    assert len(break_edges) >= 1, "Should have at least one break edge"
