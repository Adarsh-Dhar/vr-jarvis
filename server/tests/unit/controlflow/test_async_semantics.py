"""Test async semantics with suspension nodes."""

import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_async_for_suspension():
    """Test async for loop has suspension node."""
    source = """
async def process(items):
    async for item in items:
        result = item
    return result
"""
    
    cfg = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source).body[0],
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Should have suspension nodes
    suspension_nodes = [n for n in cfg.graph.nodes if n.kind == 'suspension']
    assert len(suspension_nodes) >= 1
    
    # Should have metadata indicating async iteration
    async_iter_nodes = [n for n in suspension_nodes if n.metadata.get('suspension_point') == 'async_iteration']
    assert len(async_iter_nodes) >= 1


def test_async_with_suspension():
    """Test async with has suspension nodes."""
    source = """
async def process():
    async with get_context():
        result = 1
    return result
"""
    
    cfg = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source).body[0],
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Should have suspension nodes
    suspension_nodes = [n for n in cfg.graph.nodes if n.kind == 'suspension']
    assert len(suspension_nodes) >= 1
    
    # Should have metadata indicating async enter
    async_enter_nodes = [n for n in suspension_nodes if n.metadata.get('suspension_point') == 'async_enter']
    assert len(async_enter_nodes) >= 1


def test_await_suspension():
    """Test await expression has suspension node."""
    source = """
async def process():
    result = await fetch_data()
    return result
"""
    
    cfg = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source).body[0],
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    # Check if await is handled (may be in assignment)
    # Look for nodes with await in their label or ast_kind
    await_nodes = [n for n in cfg.graph.nodes if 'await' in n.label.lower() or n.ast_kind == 'Await']
    assert len(await_nodes) >= 1
