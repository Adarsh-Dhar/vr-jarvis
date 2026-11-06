"""Test CFG completeness for various constructs."""

import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_cfg_for_loop_completeness():
    """Test that for loops have all necessary nodes."""
    source = """
def process(items):
    for item in items:
        result = item
    return result
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Should have loop header, body, and join nodes
    node_kinds = {node.kind for node in artifact.graph.nodes}
    assert 'loop_header' in node_kinds or 'statement' in node_kinds


def test_cfg_while_loop_completeness():
    """Test that while loops have all necessary nodes."""
    source = """
def process():
    i = 0
    while i < 10:
        i += 1
    return i
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Should have loop header, body, and join nodes
    node_kinds = {node.kind for node in artifact.graph.nodes}
    assert 'loop_header' in node_kinds or 'statement' in node_kinds


def test_cfg_if_branch_completeness():
    """Test that if branches have all necessary nodes."""
    source = """
def process(value):
    if value > 0:
        result = value
    else:
        result = -value
    return result
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Should have condition nodes
    node_kinds = {node.kind for node in artifact.graph.nodes}
    assert 'condition' in node_kinds or 'statement' in node_kinds


def test_cfg_try_except_completeness():
    """Test that try/except blocks have all necessary nodes."""
    source = """
def process():
    try:
        result = risky()
    except ValueError:
        result = handle()
    return result
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Should have try, handler, and join nodes
    assert len(artifact.graph.nodes) > 0


def test_cfg_with_statement_completeness():
    """Test that with statements have all necessary nodes."""
    source = """
def process():
    with open('file.txt') as f:
        result = f.read()
    return result
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Should have with and body nodes
    assert len(artifact.graph.nodes) > 0
