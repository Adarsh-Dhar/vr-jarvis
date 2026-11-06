"""Test CFG construction for exception handling."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_try_except():
    """Test CFG for try-except."""
    code = """
def process():
    try:
        result = calculate()
    except ValueError:
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

    # Check for exception_dispatch node
    dispatch_nodes = [n for n in cfg.nodes if n.kind == 'exception_dispatch']
    assert len(dispatch_nodes) >= 1, "Should have at least one exception_dispatch node"

    # Check for exception edges
    exception_edges = [e for e in cfg.edges if e.kind == 'exception']
    assert len(exception_edges) >= 1, "Should have at least one exception edge"


def test_try_except_finally():
    """Test CFG for try-except-finally."""
    code = """
def process():
    try:
        result = calculate()
    except ValueError:
        result = 0
    finally:
        cleanup()
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

    # Check for finally node
    finally_nodes = [n for n in cfg.nodes if n.kind == 'finally']
    assert len(finally_nodes) >= 1, "Should have at least one finally node"

    # Check for finally edges
    finally_edges = [e for e in cfg.edges if e.kind == 'finally']
    assert len(finally_edges) >= 1, "Should have at least one finally edge"


def test_try_except_else():
    """Test CFG for try-except-else."""
    code = """
def process():
    try:
        result = calculate()
    except ValueError:
        result = 0
    else:
        commit(result)
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
