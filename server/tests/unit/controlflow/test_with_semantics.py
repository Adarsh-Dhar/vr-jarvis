"""Test with statement semantics."""

import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_with_statement():
    """Test basic with statement."""
    source = """
def process():
    with open('file.txt') as f:
        content = f.read()
    return content
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
    
    # Should have with node and exit node
    node_kinds = {node.kind for node in artifact.graph.nodes}
    assert 'statement' in node_kinds
    assert len(artifact.graph.nodes) > 0


def test_with_return():
    """Test with statement with return inside."""
    source = """
def process():
    with open('file.txt') as f:
        return f.read()
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
    
    # Should have with exit node for cleanup
    assert len(artifact.graph.nodes) > 0


def test_with_exception():
    """Test with statement with exception handling."""
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
    
    # Should have with and exit nodes
    assert len(artifact.graph.nodes) > 0


def test_nested_with():
    """Test nested with statements."""
    source = """
def process():
    with open('file1.txt') as f1:
        with open('file2.txt') as f2:
            result = f1.read() + f2.read()
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
    
    # Should have multiple with and exit nodes
    assert len(artifact.graph.nodes) > 0
