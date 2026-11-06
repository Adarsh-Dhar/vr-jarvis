"""Test async control flow constructs in CFG construction."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_async_for_generates_cfg():
    """Test that async for generates CFG nodes."""
    code = """
async def process(items):
    async for item in items:
        result = item
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

    # Should have CFG nodes
    assert len(cfg.nodes) > 0, "Should generate CFG nodes"
    # Should have loop header
    loop_headers = [n for n in cfg.nodes if n.kind == 'loop_header']
    assert len(loop_headers) >= 1, "Should have loop header"


def test_yield_generates_cfg():
    """Test that yield generates CFG nodes."""
    code = """
def generator():
    yield 1
    yield 2
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::generator",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Should have CFG nodes
    assert len(cfg.nodes) > 0, "Should generate CFG nodes"
    # Should have yield nodes
    yield_nodes = [n for n in cfg.nodes if n.kind == 'statement' and 'yield' in n.label]
    assert len(yield_nodes) >= 1, "Should have yield nodes"


def test_yield_from_generates_cfg():
    """Test that yield from generates CFG nodes."""
    code = """
def generator():
    yield from other_generator()
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::generator",
        source=code,
        file_path="test.py"
    )
    cfg = artifact.graph

    # Should have CFG nodes
    assert len(cfg.nodes) > 0, "Should generate CFG nodes"
    # Should have yield from node
    yield_from_nodes = [n for n in cfg.nodes if n.kind == 'statement' and 'yield from' in n.label]
    assert len(yield_from_nodes) >= 1, "Should have yield from node"
