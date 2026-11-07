"""Test with statement semantics and cleanup."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder
from ai_agents.intelligence.controlflow.validator import validate_cfg


def test_return_inside_with_blocks_exit():
    """Test that return inside with routes through cleanup and after() is unreachable."""
    code = """
def process():
    with open("file.txt") as handle:
        return handle.read()
    after()  # Should be unreachable
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

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Find return, with exit, and after nodes
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    with_exit_nodes = [n for n in cfg.nodes if n.kind == 'statement' and 'with exit' in n.label]
    after_nodes = [n for n in cfg.nodes if 'after' in n.label]

    assert len(return_nodes) == 1, "Should have one return node"
    assert len(with_exit_nodes) >= 1, "Should have with exit nodes"
    assert len(after_nodes) == 1, "Should have after() node"

    # Return should route through with exit (cleanup)
    return_node = return_nodes[0]
    edges_from_return = cfg.get_edges_from(return_node.id)

    # Return should have edge to with exit (cleanup)
    to_exit = [e for e in edges_from_return if e.target in [n.id for n in with_exit_nodes]]
    assert len(to_exit) > 0, "Return should route through with exit"

    # after() should be unreachable (no incoming edges)
    after_node = after_nodes[0]
    edges_to_after = cfg.get_edges_to(after_node.id)
    assert len(edges_to_after) == 0, "after() should be unreachable"

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
