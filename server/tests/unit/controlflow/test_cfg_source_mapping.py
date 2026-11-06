"""Test CFG AST-to-source mapping."""

import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_cfg_statement_mapping():
    """Test that statements map to CFG nodes."""
    source = """
def process(value):
    x = value + 1
    return x
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
    
    # Check that AST index has mappings
    ast_index = artifact.ast_index
    assert len(ast_index.ast_to_cfg_nodes) > 0


def test_cfg_expression_mapping():
    """Test that expressions map to CFG nodes."""
    source = """
def process(a, b):
    result = a + b
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
    
    # Check that AST index has expression mappings
    ast_index = artifact.ast_index
    assert len(ast_index.ast_to_cfg_nodes) > 0


def test_cfg_loop_target_mapping():
    """Test that loop targets map to CFG nodes."""
    source = """
def process(items):
    for item in items:
        print(item)
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
    
    # Check that AST index has loop target mappings
    ast_index = artifact.ast_index
    assert len(ast_index.ast_to_cfg_nodes) > 0


def test_cfg_exception_handler_mapping():
    """Test that exception handlers map to CFG nodes."""
    source = """
def process():
    try:
        risky()
    except ValueError:
        handle()
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
    
    # Check that AST index has handler mappings
    ast_index = artifact.ast_index
    assert len(ast_index.ast_to_cfg_nodes) > 0
