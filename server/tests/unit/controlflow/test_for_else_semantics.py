"""Test for-loop else semantics in CFG construction."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_for_else_executes_on_natural_exhaustion():
    """Test that else clause executes when loop exhausts naturally."""
    code = """
def process(items):
    for item in items:
        x = item
    else:
        result = "exhausted"  # Should execute
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
    else_nodes = [n for n in cfg.nodes if 'exhausted' in n.label]
    assert len(else_nodes) == 1, "Should have else body node"

    # Else should be reachable
    else_node = else_nodes[0]
    edges_to_else = cfg.get_edges_to(else_node.id)
    assert len(edges_to_else) > 0, "Else body should be reachable from loop exhaustion"


def test_break_bypasses_else():
    """Test that break bypasses the else clause."""
    code = """
def process(items):
    for item in items:
        if item > 100:
            break
    else:
        result = "exhausted"  # Should not execute when break is taken
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

    # Find break node
    break_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'break']
    assert len(break_nodes) == 1, "Should have break node"

    # Find else body node
    else_nodes = [n for n in cfg.nodes if 'exhausted' in n.label]
    assert len(else_nodes) == 1, "Should have else body node"

    # Break should not route to else
    break_node = break_nodes[0]
    else_node = else_nodes[0]
    
    # Check if there's a path from break to else
    # (This would be incorrect)
    edges_from_break = cfg.get_edges_from(break_node.id)
    for edge in edges_from_break:
        target = cfg.get_node(edge.target)
        if target and target.id == else_node.id:
            assert False, "Break should not route directly to else body"


def test_return_in_loop_remains_abrupt():
    """Test that return inside loop remains abrupt."""
    code = """
def process(items):
    for item in items:
        if item > 100:
            return item
    else:
        result = "exhausted"
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

    # Find return node inside loop
    return_nodes = [n for n in cfg.nodes if n.kind == 'return' and 'item' in n.label]
    assert len(return_nodes) == 1, "Should have return node for item"

    # Return should have only 'return' edge to exit
    return_node = return_nodes[0]
    edges_from_return = cfg.get_edges_from(return_node.id)
    
    for edge in edges_from_return:
        assert edge.kind == 'return', f"Return should only have return edges, got {edge.kind}"


def test_continue_returns_to_loop_header():
    """Test that continue returns to the loop header."""
    code = """
def process(items):
    for item in items:
        if item < 0:
            continue
        x = item
    return x
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

    # Find continue node
    continue_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'continue']
    assert len(continue_nodes) == 1, "Should have continue node"

    # Find loop header
    header_nodes = [n for n in cfg.nodes if n.kind == 'loop_header']
    assert len(header_nodes) == 1, "Should have loop header"

    # Continue should route back to loop header
    continue_node = continue_nodes[0]
    header_node = header_nodes[0]
    
    edges_from_continue = cfg.get_edges_from(continue_node.id)
    continue_targets = [edge.target for edge in edges_from_continue]
    
    assert header_node.id in continue_targets, "Continue should route back to loop header"


def test_nested_loop_break_targets_correct_loop():
    """Test that break in nested loop targets the correct loop."""
    code = """
def process(items, values):
    for item in items:
        for value in values:
            if value > 100:
                break  # Should break inner loop only
        # This line should be reachable
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

    # Find break node
    break_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'break']
    assert len(break_nodes) == 1, "Should have break node"

    # Find the two loop headers
    header_nodes = [n for n in cfg.nodes if n.kind == 'loop_header']
    assert len(header_nodes) == 2, "Should have two loop headers (inner and outer)"
    
    outer_header = header_nodes[1]  # Second is outer
    
    # Break should not route to the outer loop header
    break_node = break_nodes[0]
    edges_from_break = cfg.get_edges_from(break_node.id)
    break_targets = [edge.target for edge in edges_from_break]
    
    assert outer_header.id not in break_targets, "Break should not route to outer loop header"
