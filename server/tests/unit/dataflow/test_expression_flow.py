"""Tests for expression-level control flow analysis."""
import pytest
import ast
from ai_agents.intelligence.dataflow.expression_flow import ExpressionFlowBuilder
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder


def test_boolop_flow():
    """Test that BoolOp expressions are expanded into flow nodes."""
    code = '''
def f():
    result = a and b
'''

    tree = ast.parse(code)
    func_def = tree.body[0]
    function_id = 'test::f'

    cfg_builder = PythonCFGBuilder()
    cfg_artifact = cfg_builder.build_function(
        function_ast=func_def,
        function_id=function_id,
        source=code,
        file_path='test.py'
    )
    cfg = cfg_artifact.graph

    # Find BoolOp node in AST
    boolop_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp):
            boolop_node = node
            break

    if boolop_node:
        flow_builder = ExpressionFlowBuilder()
        result = flow_builder.build_boolop_flow(
            boolop_node,
            cfg,
            function_id,
            'test.py',
            code
        )

        # Should create entry, value, and exit nodes
        assert len(result.added_nodes) >= 3, "Should create at least 3 nodes for BoolOp"
        assert result.entry_node_id is not None
        assert result.exit_node_id is not None


def test_ifexp_flow():
    """Test that IfExp (ternary) expressions are expanded into flow nodes."""
    code = '''
def f():
    result = x if condition else y
'''

    tree = ast.parse(code)
    func_def = tree.body[0]
    function_id = 'test::f'

    cfg_builder = PythonCFGBuilder()
    cfg_artifact = cfg_builder.build_function(
        function_ast=func_def,
        function_id=function_id,
        source=code,
        file_path='test.py'
    )
    cfg = cfg_artifact.graph

    # Find IfExp node in AST
    ifexp_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.IfExp):
            ifexp_node = node
            break

    if ifexp_node:
        flow_builder = ExpressionFlowBuilder()
        result = flow_builder.build_ifexp_flow(
            ifexp_node,
            cfg,
            function_id,
            'test.py',
            code
        )

        # Should create test, body, orelse, and exit nodes
        assert len(result.added_nodes) >= 4, "Should create at least 4 nodes for IfExp"
        assert result.entry_node_id is not None
        assert result.exit_node_id is not None

        # Should have true and false edges
        true_edges = [e for e in result.added_edges if e.kind == 'true']
        false_edges = [e for e in result.added_edges if e.kind == 'false']
        assert len(true_edges) > 0, "Should have true edge"
        assert len(false_edges) > 0, "Should have false edge"


def test_expression_flow_builder():
    """Test that ExpressionFlowBuilder can be instantiated."""
    builder = ExpressionFlowBuilder()
    assert builder is not None
    assert builder._node_counter == 0
    assert builder._edge_counter == 0
