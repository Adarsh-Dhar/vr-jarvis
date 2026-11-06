"""Regression tests for loop semantics - while loops, edge kinds, and exhaustion paths."""
import pytest
import ast
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
from ai_agents.intelligence.controlflow.validator import validate_cfg


def test_while_loop_else_executes_on_natural_exhaustion():
    """Test that while-else executes only when loop condition becomes false."""
    source = """
def while_else():
    i = 0
    while i < 5:
        i += 1
    else:
        x = 1  # Should execute when i becomes 5
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::while_else", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check that there's a loop_exhausted edge from header
    header_nodes = [n for n in cfg.nodes if n.kind == 'loop_header']
    assert len(header_nodes) == 1
    header_edges = cfg.get_edges_from(header_nodes[0].id)
    exhausted_edges = [e for e in header_edges if e.kind == 'loop_exhausted']
    assert len(exhausted_edges) == 1, "Should have loop_exhausted edge"


def test_while_break_bypasses_else():
    """Test that break in while loop bypasses the else clause."""
    source = """
def while_break_else():
    i = 0
    while i < 10:
        if i == 5:
            break
        i += 1
    else:
        x = 1  # Should not execute when break is taken
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::while_break_else", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Find break node
    break_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'break']
    assert len(break_nodes) == 1

    # Break should not route to else body
    break_node = break_nodes[0]
    edges_from_break = cfg.get_edges_from(break_node.id)
    for edge in edges_from_break:
        target_node = cfg.get_node(edge.target)
        if target_node:
            assert 'else' not in target_node.label.lower(), "Break should not route to else body"


def test_while_else_ending_abruptly():
    """Test that else suite ending abruptly doesn't create false normal exits."""
    source = """
def while_else_return():
    i = 0
    while i < 5:
        i += 1
    else:
        return 1  # Else ends abruptly
    return 2
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::while_else_return", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_while_return_in_loop():
    """Test that return in while loop remains abrupt."""
    source = """
def while_return():
    i = 0
    while i < 10:
        if i == 5:
            return 1
        i += 1
    return 2
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::while_return", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_for_else_executes_on_natural_exhaustion():
    """Test that for-else executes only when iterator is exhausted."""
    source = """
def for_else():
    for i in range(5):
        x = i
    else:
        y = 1  # Should execute when range is exhausted
    return y
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::for_else", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check for loop_exhausted edge
    header_nodes = [n for n in cfg.nodes if n.kind == 'loop_header']
    assert len(header_nodes) == 1
    header_edges = cfg.get_edges_from(header_nodes[0].id)
    exhausted_edges = [e for e in header_edges if e.kind == 'loop_exhausted']
    assert len(exhausted_edges) == 1, "Should have loop_exhausted edge"


def test_for_break_bypasses_else():
    """Test that break in for loop bypasses the else clause."""
    source = """
def for_break():
    for i in range(10):
        if i == 5:
            break
    else:
        x = 1  # Should not execute when break is taken
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::for_break", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Find break node
    break_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'break']
    assert len(break_nodes) == 1

    # Break should route to post_loop, not through else
    break_node = break_nodes[0]
    edges_from_break = cfg.get_edges_from(break_node.id)
    break_edges = [e for e in edges_from_break if e.kind == 'break']
    assert len(break_edges) >= 1, "Should have break edge"


def test_edge_kinds_standardized():
    """Test that edge kinds follow standardized naming convention."""
    source = """
def test_edges():
    for i in range(10):
        if i > 5:
            break
    while x:
        y = 1
    return y
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::test_edges", source, "test.py")
    cfg = artifact.graph

    # Standard edge kinds
    standard_kinds = {
        'next', 'true', 'false', 'loop_back', 'loop_exhausted',
        'break', 'continue', 'return', 'raise', 'exception',
        'finally', 'resume', 'exception_group'
    }

    # Check all edges use standard kinds
    for edge in cfg.edges:
        assert edge.kind in standard_kinds, f"Edge kind '{edge.kind}' is not standard"


def test_loop_back_edge_kind():
    """Test that loop back edges use 'loop_back' kind."""
    source = """
def loop_back():
    for i in range(10):
        x = i
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::loop_back", source, "test.py")
    cfg = artifact.graph

    # Find loop back edges
    loop_back_edges = [e for e in cfg.edges if e.kind == 'loop_back']
    assert len(loop_back_edges) >= 1, "Should have at least one loop_back edge"


def test_nested_loops_break_targets():
    """Test that nested loops have correct break targets."""
    source = """
def nested_loops():
    for i in range(10):
        for j in range(10):
            if j == 5:
                break  # Should break inner loop only
        x = i
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::nested_loops", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Should have two loop headers
    header_nodes = [n for n in cfg.nodes if n.kind == 'loop_header']
    assert len(header_nodes) == 2


def test_continue_targets_loop_header():
    """Test that continue targets the loop header, not exit."""
    source = """
def continue_test():
    for i in range(10):
        if i % 2 == 0:
            continue
        x = i
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::continue_test", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Find continue node
    continue_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'continue']
    assert len(continue_nodes) == 1

    # Continue should use 'continue' edge kind
    continue_node = continue_nodes[0]
    edges_from_continue = cfg.get_edges_from(continue_node.id)
    continue_edges = [e for e in edges_from_continue if e.kind == 'continue']
    assert len(continue_edges) >= 1, "Should have continue edge"


def test_zero_iteration_loop():
    """Test that zero-iteration loops work correctly."""
    source = """
def zero_iteration():
    for i in []:  # Empty iterable
        x = 1  # Unreachable
    else:
        y = 2  # Should execute
    return y
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::zero_iteration", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"
