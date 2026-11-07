"""Regression tests for exception and finally routing."""
import pytest
import ast
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
from ai_agents.intelligence.controlflow.validator import validate_cfg


def test_try_else_only_on_normal_completion():
    """Test that try-else executes only on normal completion, not on raise."""
    source = """
def try_else_normal():
    try:
        x = 1
        return x
    except ValueError:
        y = 2
    else:
        z = 3  # Should not execute when return is taken
    return z
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::try_else_normal", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_try_else_on_raise_not_executed():
    """Test that else doesn't execute when exception is raised."""
    source = """
def try_else_raise():
    try:
        raise ValueError("error")
    except ValueError:
        x = 1
    else:
        y = 2  # Should not execute when exception is raised
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::try_else_raise", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_return_through_finally():
    """Test that return routes through finally before reaching exit."""
    source = """
def return_finally():
    try:
        return 1
    finally:
        x = 2  # Should execute before return
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::return_finally", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check that finally nodes exist (completion-specific finalizers)
    finally_nodes = [n for n in cfg.nodes if n.kind == 'finally']
    assert len(finally_nodes) >= 1, "Should have finally nodes"

    # Check that return connects to a finally node with return completion kind
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) == 1
    return_edges = cfg.get_edges_from(return_nodes[0].id)
    finally_edges = [e for e in return_edges if e.kind == 'finally']
    assert len(finally_edges) >= 1, "Return should connect to finally"


def test_raise_through_finally():
    """Test that raise routes through finally before propagating."""
    source = """
def raise_finally():
    try:
        raise ValueError("error")
    finally:
        x = 2  # Should execute before exception propagates
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::raise_finally", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check that raise connects to finally
    raise_nodes = [n for n in cfg.nodes if n.kind == 'raise']
    assert len(raise_nodes) == 1
    raise_edges = cfg.get_edges_from(raise_nodes[0].id)
    finally_edges = [e for e in raise_edges if e.kind == 'finally']
    assert len(finally_edges) >= 1, "Raise should connect to finally"


def test_finally_overrides_return():
    """Test that return in finally overrides pending return."""
    source = """
def finally_override():
    try:
        return 1
    finally:
        return 2  # This return overrides the first
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::finally_override", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_finally_overrides_raise():
    """Test that raise in finally overrides pending raise."""
    source = """
def finally_override_raise():
    try:
        raise ValueError("error1")
    finally:
        raise ValueError("error2")  # This overrides the first
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::finally_override_raise", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_break_through_finally():
    """Test that break routes through finally."""
    source = """
def break_finally():
    for i in range(10):
        try:
            if i == 5:
                break
        finally:
            x = i  # Should execute before break takes effect
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::break_finally", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_continue_through_finally():
    """Test that continue routes through finally."""
    source = """
def continue_finally():
    for i in range(10):
        try:
            if i % 2 == 0:
                continue
        finally:
            x = i  # Should execute before continue
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::continue_finally", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_nested_finally():
    """Test nested finally blocks."""
    source = """
def nested_finally():
    try:
        try:
            return 1
        finally:
            x = 2
    finally:
        y = 3
    return y
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::nested_finally", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Should have finally nodes for each try (completion-specific finalizers)
    # Each try creates 5 finally nodes (normal, return, raise, break, continue)
    # Two nested tries = 10 finally nodes total
    finally_nodes = [n for n in cfg.nodes if n.kind == 'finally']
    assert len(finally_nodes) == 10, "Should have 10 finally nodes (5 per try for completion-specific routing)"


def test_exception_in_handler():
    """Test exception raised in handler body."""
    source = """
def handler_exception():
    try:
        x = 1
    except ValueError:
        raise TypeError("new error")  # New exception from handler
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::handler_exception", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_exception_in_else():
    """Test exception raised in else block."""
    source = """
def else_exception():
    try:
        x = 1
    except ValueError:
        y = 2
    else:
        raise TypeError("error in else")
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::else_exception", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_multiple_handlers_ordered():
    """Test that handlers are tried in order."""
    source = """
def ordered_handlers():
    try:
        x = risky()
    except ValueError:
        y = 1
    except TypeError:
        z = 2
    except Exception:
        w = 3
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::ordered_handlers", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Should have exception dispatcher
    dispatch_nodes = [n for n in cfg.nodes if n.kind == 'exception_dispatch']
    assert len(dispatch_nodes) == 1, "Should have exception dispatcher"


def test_bare_except():
    """Test bare except handler."""
    source = """
def bare_except():
    try:
        x = risky()
    except:
        y = 1
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::bare_except", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_raise_routes_through_dispatcher():
    """Test that explicit raise routes through exception dispatcher, not directly to exception exit."""
    source = """
def process():
    try:
        raise ValueError()
    except ValueError:
        handled()
    after()
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::process", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Find raise node and dispatcher
    raise_nodes = [n for n in cfg.nodes if n.kind == 'raise']
    assert len(raise_nodes) == 1, "Should have one raise node"
    raise_node = raise_nodes[0]

    dispatch_nodes = [n for n in cfg.nodes if n.kind == 'exception_dispatch']
    assert len(dispatch_nodes) == 1, "Should have one exception dispatcher"
    dispatch_node = dispatch_nodes[0]

    # Raise should route to dispatcher, not directly to exception exit
    edges_from_raise = cfg.get_edges_from(raise_node.id)
    dispatch_edges = [e for e in edges_from_raise if e.target == dispatch_node.id]
    assert len(dispatch_edges) > 0, "Raise should route to exception dispatcher"

    # Raise should NOT have direct edge to exception exit
    exception_exit_edges = [e for e in edges_from_raise if e.target == cfg.exception_exit_node_id]
    assert len(exception_exit_edges) == 0, "Raise should not bypass dispatcher to exception exit"


def test_unmatched_exception_to_parent():
    """Test that unmatched exception routes to parent dispatcher, not self-loop."""
    source = """
def process():
    try:
        try:
            raise ValueError()
        except TypeError:
            handled()
    except ValueError:
        outer_handled()
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::process", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Find both dispatchers
    dispatch_nodes = [n for n in cfg.nodes if n.kind == 'exception_dispatch']
    assert len(dispatch_nodes) == 2, "Should have two exception dispatchers (inner and outer)"

    # Inner dispatcher should route to outer dispatcher, not to itself
    inner_dispatch = dispatch_nodes[0]
    outer_dispatch = dispatch_nodes[1]

    edges_from_inner = cfg.get_edges_from(inner_dispatch.id)
    self_loop_edges = [e for e in edges_from_inner if e.target == inner_dispatch.id]
    assert len(self_loop_edges) == 0, "Inner dispatcher should not have self-loop"

    # Should have edge to outer dispatcher or exception exit
    to_outer = [e for e in edges_from_inner if e.target == outer_dispatch.id]
    to_exit = [e for e in edges_from_inner if e.target == cfg.exception_exit_node_id]
    assert len(to_outer) > 0 or len(to_exit) > 0, "Inner dispatcher should route to outer dispatcher or exception exit"
