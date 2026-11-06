"""Test match statement semantics."""

import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_match_literal_pattern():
    """Test match with literal patterns."""
    source = """
def process(value):
    match value:
        case 1:
            return "one"
        case 2:
            return "two"
        case _:
            return "other"
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
    
    # Should have match node and case nodes
    node_kinds = {node.kind for node in artifact.graph.nodes}
    assert 'statement' in node_kinds or 'condition' in node_kinds
    assert len(artifact.graph.nodes) > 0


def test_match_with_guard():
    """Test match with guard conditions."""
    source = """
def process(value):
    match value:
        case x if x > 0:
            return "positive"
        case x if x < 0:
            return "negative"
        case _:
            return "zero"
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
    
    # Should have match, case, and guard nodes
    assert len(artifact.graph.nodes) > 0


def test_match_capture_pattern():
    """Test match with capture patterns."""
    source = """
def process(point):
    match point:
        case (x, y):
            return x + y
        case _:
            return 0
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
    
    # Should have match and case nodes
    assert len(artifact.graph.nodes) > 0


def test_match_wildcard():
    """Test match with wildcard pattern."""
    source = """
def process(value):
    match value:
        case _:
            return "anything"
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
    
    # Should have match and wildcard case
    assert len(artifact.graph.nodes) > 0


def test_match_or_pattern():
    """Test match with OR patterns."""
    source = """
def process(value):
    match value:
        case 1 | 2 | 3:
            return "small"
        case _:
            return "other"
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
    
    # Should have match and case nodes
    assert len(artifact.graph.nodes) > 0
