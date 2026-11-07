"""Test try/except/else/finally semantics in CFG construction."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_return_through_finally():
    """Test that return executes finally before exiting."""
    code = """
def process():
    try:
        return 1
    finally:
        cleanup()
    return 2  # Should be unreachable
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Find return and finally nodes
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    finally_nodes = [n for n in cfg.nodes if 'finally' in n.label.lower() or n.kind == 'statement' and 'cleanup' in n.label]
    
    assert len(return_nodes) >= 1, "Should have return node"
    assert len(finally_nodes) >= 1, "Should have finally body node"
    
    # Return should route to finally before exit
    return_node = return_nodes[0]
    edges_from_return = cfg.get_edges_from(return_node.id)
    
    # Return should have 'finally' edge or route through finally
    finally_edges = [e for e in edges_from_return if e.kind == 'finally']
    assert len(finally_edges) > 0, "Return should route through finally"


def test_raise_through_finally():
    """Test that raise executes finally before propagating."""
    code = """
def process():
    try:
        raise ValueError()
    finally:
        cleanup()
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Find raise and finally nodes
    raise_nodes = [n for n in cfg.nodes if n.kind == 'raise']
    finally_nodes = [n for n in cfg.nodes if 'finally' in n.label.lower() or n.kind == 'statement' and 'cleanup' in n.label]
    
    assert len(raise_nodes) >= 1, "Should have raise node"
    assert len(finally_nodes) >= 1, "Should have finally body node"
    
    # Raise should route to finally before exception exit
    raise_node = raise_nodes[0]
    edges_from_raise = cfg.get_edges_from(raise_node.id)
    
    # Raise should have 'finally' edge or route through finally
    finally_edges = [e for e in edges_from_raise if e.kind == 'finally']
    assert len(finally_edges) > 0, "Raise should route through finally"


def test_finally_overrides_return():
    """Test that return in finally overrides the original return."""
    code = """
def process():
    try:
        return 1
    finally:
        return 2  # This should be the actual return value
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Find both return nodes
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) == 2, "Should have two return nodes"
    
    # The second return (in finally) should be the one that reaches exit
    return_in_finally = [n for n in return_nodes if '2' in n.label][0]
    edges_from_finally_return = cfg.get_edges_from(return_in_finally.id)
    
    # Should have edge to exit
    assert len(edges_from_finally_return) > 0, "Return in finally should reach exit"


def test_else_only_on_normal_completion():
    """Test that else executes only when try body completes normally."""
    code = """
def process(value):
    try:
        if value > 100:
            raise ValueError()
    except ValueError:
        result = "caught"
    else:
        result = "normal"  # Should execute only when no exception
    return result
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Find else body node
    else_nodes = [n for n in cfg.nodes if 'normal' in n.label]
    assert len(else_nodes) == 1, "Should have else body node"
    
    # Find raise node
    raise_nodes = [n for n in cfg.nodes if n.kind == 'raise']
    assert len(raise_nodes) == 1, "Should have raise node"
    
    # Raise should not route to else
    raise_node = raise_nodes[0]
    else_node = else_nodes[0]
    
    edges_from_raise = cfg.get_edges_from(raise_node.id)
    raise_targets = [edge.target for edge in edges_from_raise]
    
    assert else_node.id not in raise_targets, "Raise should not route to else body"


def test_break_through_finally():
    """Test that break executes finally before exiting loop."""
    code = """
def process(items):
    while True:
        try:
            break
        finally:
            cleanup()
    return None
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Find break and finally nodes
    break_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'break']
    finally_nodes = [n for n in cfg.nodes if 'finally' in n.label.lower() or n.kind == 'statement' and 'cleanup' in n.label]
    
    assert len(break_nodes) >= 1, "Should have break node"
    assert len(finally_nodes) >= 1, "Should have finally body node"
    
    # Break should route to finally before loop exit
    break_node = break_nodes[0]
    edges_from_break = cfg.get_edges_from(break_node.id)
    
    # Break should have 'finally' edge or route through finally
    finally_edges = [e for e in edges_from_break if e.kind == 'finally']
    assert len(finally_edges) > 0, "Break should route through finally"


def test_continue_through_finally():
    """Test that continue executes finally before resuming loop."""
    code = """
def process(items):
    for item in items:
        try:
            continue
        finally:
            cleanup()
    return None
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Find continue and finally nodes
    continue_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'continue']
    finally_nodes = [n for n in cfg.nodes if 'finally' in n.label.lower() or n.kind == 'statement' and 'cleanup' in n.label]

    assert len(continue_nodes) >= 1, "Should have continue node"
    assert len(finally_nodes) >= 1, "Should have finally body node"

    # Continue should route to finally before loop header
    continue_node = continue_nodes[0]
    edges_from_continue = cfg.get_edges_from(continue_node.id)

    # Continue should have 'finally' edge or route through finally
    finally_edges = [e for e in edges_from_continue if e.kind == 'finally']
    assert len(finally_edges) > 0, "Continue should route through finally"


def test_return_finally_blocks_after():
    """Test that return in try/finally blocks execution of statements after the try."""
    code = """
def process():
    try:
        return 1
    finally:
        cleanup()
    after()  # Should be unreachable after return
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Find return, finally, and after nodes
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    finally_nodes = [n for n in cfg.nodes if n.kind == 'finally']
    after_nodes = [n for n in cfg.nodes if 'after' in n.label]

    assert len(return_nodes) == 1, "Should have one return node"
    assert len(finally_nodes) >= 1, "Should have finally nodes"
    assert len(after_nodes) == 1, "Should have after() node"

    # after() should not be reachable from return through finally
    # The return should route through finally to exit, not to after()
    return_node = return_nodes[0]
    after_node = after_nodes[0]

    # Check that there's no path from return to after
    # by checking if after has any incoming edges from finally or return
    edges_to_after = cfg.get_edges_to(after_node.id)
    assert len(edges_to_after) == 0, "after() should have no incoming edges (unreachable)"
