"""Test generator semantics with suspension nodes."""

import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_yield_suspension():
    """Test yield has suspension node."""
    source = """
def process():
    for i in range(10):
        yield i
"""
    
    cfg = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source).body[0],
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Check for yield nodes
    yield_nodes = [n for n in cfg.graph.nodes if 'yield' in n.label.lower() or n.ast_kind == 'Yield']
    assert len(yield_nodes) >= 1


def test_yield_from_suspension():
    """Test yield from has suspension node."""
    source = """
def process():
    yield from generator()
"""
    
    cfg = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source).body[0],
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Check for yield from nodes
    yield_from_nodes = [n for n in cfg.graph.nodes if 'yield from' in n.label.lower() or n.ast_kind == 'YieldFrom']
    assert len(yield_from_nodes) >= 1


def test_yield_with_try_finally():
    """Test yield with try/finally."""
    source = """
def process():
    try:
        yield 1
    finally:
        cleanup()
"""
    
    cfg = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source).body[0],
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Check for yield nodes
    yield_nodes = [n for n in cfg.graph.nodes if 'yield' in n.label.lower() or n.ast_kind == 'Yield']
    assert len(yield_nodes) >= 1
