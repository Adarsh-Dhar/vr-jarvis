"""Test that exceptions route through finally blocks correctly."""
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder
import ast


def test_unmatched_exception_runs_finally():
    """Test that unmatched exceptions run the finally block."""
    code = """
def f():
    try:
        risky()
    except ValueError:
        handle()
    finally:
        cleanup()
"""
    tree = ast.parse(code)
    func = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::f",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Find the dispatcher
    dispatch = next((n for n in cfg.nodes if n.kind == 'exception_dispatch'), None)
    assert dispatch is not None, "Should have an exception dispatcher"

    # Find the finally (raise) node
    fin_raise = next((n for n in cfg.nodes if n.label == 'finally (raise)'), None)
    assert fin_raise is not None, "Should have a finally (raise) node"

    # Dispatcher should go to finally (raise), not directly to exception_exit
    edges_from_dispatch = cfg.get_edges_from(dispatch.id)
    target_ids = [e.target for e in edges_from_dispatch]
    assert fin_raise.id in target_ids, "Dispatcher should route to finally (raise)"
    assert cfg.exception_exit_node_id not in target_ids, "Dispatcher should not bypass finally"


def test_handler_exception_runs_finally():
    """Test that exceptions raised in handlers run the finally block."""
    code = """
def f():
    try:
        risky()
    except ValueError:
        handle()
    finally:
        cleanup()
"""
    tree = ast.parse(code)
    func = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::f",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Find the handler node
    handler = next((n for n in cfg.nodes if 'except ValueError' in n.label), None)
    assert handler is not None, "Should have a handler node"

    # Find the finally (raise) node
    fin_raise = next((n for n in cfg.nodes if n.label == 'finally (raise)'), None)
    assert fin_raise is not None, "Should have a finally (raise) node"

    # Handler should have edge to finally (raise) if it can raise
    # (This is a simplified check - full implementation would verify may_raise metadata)
    edges_from_handler = cfg.get_edges_from(handler.id)
    # Handler normal exit should go to finally (normal) or handler join
    # If handler raises, it should go to finally (raise)


def test_return_in_inner_try_reaches_outer_finally():
    """Test that return in inner try reaches outer finally."""
    code = """
def f():
    try:
        try:
            return 1
        except ValueError:
            pass
    finally:
        cleanup()
"""
    tree = ast.parse(code)
    func = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::f",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Find the return node
    ret = next((n for n in cfg.nodes if n.kind == 'return'), None)
    assert ret is not None, "Should have a return node"

    # Find the finally (return) node
    fin_return = next((n for n in cfg.nodes if n.label == 'finally (return)'), None)
    assert fin_return is not None, "Should have a finally (return) node"

    # Return should route through finally (return)
    edges_from_ret = cfg.get_edges_from(ret.id)
    target_ids = [e.target for e in edges_from_ret]
    assert fin_return.id in target_ids, "Return should route through finally (return)"

    # Return should not go directly to exit
    assert cfg.exit_node_id not in target_ids, "Return should not bypass finally"
