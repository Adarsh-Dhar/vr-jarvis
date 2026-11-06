"""Test CFG construction for exception handling with exact correctness assertions."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_try_except_has_exception_dispatch():
    """Test that try-except has exception dispatch node."""
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    dispatch_nodes = [n for n in cfg.nodes if n.kind == "exception_dispatch"]
    assert len(dispatch_nodes) >= 1, "Should have at least one exception_dispatch node"

    exception_edges = [e for e in cfg.edges if e.kind == "exception"]
    assert len(exception_edges) >= 1, "Should have at least one exception edge"


def test_try_except_finally_has_finally_node():
    """Test that try-except-finally has finally node."""
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    finally_nodes = [n for n in cfg.nodes if n.kind == "finally"]
    assert len(finally_nodes) >= 1, "Should have at least one finally node"

    finally_edges = [e for e in cfg.edges if e.kind == "finally"]
    assert len(finally_edges) >= 1, "Should have at least one finally edge"
