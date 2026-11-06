"""Test CFG construction for for loops."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_simple_for_loop():
    """Test CFG for simple for loop."""
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
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check for loop header
    loop_headers = [n for n in cfg.nodes if n.kind == 'loop_header']
    assert len(loop_headers) >= 1, "Should have at least one loop header"

    # Check for loop-back edge
    loop_back_edges = [e for e in cfg.edges if e.kind == 'loop_back']
    assert len(loop_back_edges) >= 1, "Should have at least one loop-back edge"

    # Check for loop-exit edge
    loop_exit_edges = [e for e in cfg.edges if e.kind == 'loop_exit']
    assert len(loop_exit_edges) >= 1, "Should have at least one loop-exit edge"


def test_for_loop_with_break():
    """Test CFG for for loop with break."""
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
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check for break edge
    break_edges = [e for e in cfg.edges if e.kind == 'break']
    assert len(break_edges) >= 1, "Should have at least one break edge"


def test_for_loop_with_continue():
    """Test CFG for for loop with continue."""
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
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check for continue edge
    continue_edges = [e for e in cfg.edges if e.kind == 'continue']
    assert len(continue_edges) >= 1, "Should have at least one continue edge"


def test_for_loop_with_else():
    """Test CFG for for loop with else clause."""
    code = """
def process(items):
    for item in items:
        if item == 0:
            break
        result = item * 2
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
