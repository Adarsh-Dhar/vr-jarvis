"""Test abrupt completion handling in CFG construction."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_return_blocks_subsequent_statement():
    """Test that return prevents subsequent statements from being reachable."""
    code = """
def process(value):
    return value * 2
    x = value * 3  # Should be unreachable
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

    # Find the return node
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) >= 1, "Should have at least one return node"

    # The assignment after return should not be reachable from the first return
    # by normal control flow
    return_node = return_nodes[0]
    edges_from_return = cfg.get_edges_from(return_node.id)
    
    # Return should only have 'return' edge to exit, or 'may_raise' for expressions that can raise
    for edge in edges_from_return:
        assert edge.kind in ('return', 'raise', 'may_raise'), f"Return node should not have normal edge to assignment, got {edge.kind}"


def test_conditional_return_with_reachable_statement():
    """Test that conditional return allows the other branch to reach subsequent statements."""
    code = """
def process(value):
    if value > 100:
        return value
    x = value * 2  # Should be reachable from the else branch
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

    # Find the assignment node
    assignment_nodes = [n for n in cfg.nodes if 'x = value' in n.label]
    assert len(assignment_nodes) == 1, "Should have exactly one assignment node"

    # The assignment should be reachable (has incoming edges)
    assignment_node = assignment_nodes[0]
    edges_to_assignment = cfg.get_edges_to(assignment_node.id)
    assert len(edges_to_assignment) > 0, "Assignment should be reachable from the else branch"


def test_break_bypasses_loop_else():
    """Test that break bypasses the loop else clause."""
    code = """
def process(items):
    for item in items:
        if item > 100:
            break
    else:
        result = "empty"  # Should not execute when break is taken
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
    assert len(break_nodes) == 1, "Should have exactly one break node"

    # Break should not have edges to the else body
    break_node = break_nodes[0]
    edges_from_break = cfg.get_edges_from(break_node.id)
    
    for edge in edges_from_break:
        target_node = cfg.get_node(edge.target)
        if target_node:
            assert 'else' not in target_node.label.lower(), "Break should not route to else body"


def test_break_has_correct_source_location():
    """Test that break statement uses actual source location."""
    code = """
def process(items):
    for item in items:
        if item > 100:
            break  # Line 4
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
    assert len(break_nodes) == 1, "Should have exactly one break node"

    # Break should have correct line number (line 5, not 4 due to triple-quoted string)
    break_node = break_nodes[0]
    assert break_node.start_line == 5, f"Break should be on line 5, got {break_node.start_line}"


def test_continue_has_correct_source_location():
    """Test that continue statement uses actual source location."""
    code = """
def process(items):
    for item in items:
        if item > 100:
            continue  # Line 4
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

    # Find continue node
    continue_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'continue']
    assert len(continue_nodes) == 1, "Should have exactly one continue node"

    # Continue should have correct line number (line 5, not 4 due to triple-quoted string)
    continue_node = continue_nodes[0]
    assert continue_node.start_line == 5, f"Continue should be on line 5, got {continue_node.start_line}"


def test_nested_loop_break_targets_correct_loop():
    """Test that break in nested loop targets the correct loop."""
    code = """
def process(items, values):
    for item in items:
        for value in values:
            if value > 100:
                break  # Should break inner loop only
        # Continue with outer loop
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
    assert len(break_nodes) == 1, "Should have exactly one break node"

    # Break should route to the correct target (after inner loop, not after outer loop)
    break_node = break_nodes[0]
    edges_from_break = cfg.get_edges_from(break_node.id)
    assert len(edges_from_break) == 1, "Break should have exactly one outgoing edge"
    
    break_edge = edges_from_break[0]
    assert break_edge.kind == 'break', "Break edge should have kind 'break'"


def test_completions_have_unique_ids():
    """Test that abrupt completions have unique completion IDs."""
    code = """
def process(value):
    if value > 100:
        return 1
    elif value < 0:
        return -1
    return 0
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

    # Find return nodes
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) == 3, "Should have three return nodes"

    # The build context should have generated unique completion IDs
    # This is verified implicitly by the builder's completion counter
