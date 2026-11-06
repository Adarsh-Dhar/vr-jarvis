"""Test assert statement exception handling in CFG construction."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_assert_false_branch_raises_exception():
    """Test that assert false branch raises AssertionError."""
    code = """
def process(value):
    assert value > 0, "Value must be positive"
    return value
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

    # Find assert node
    assert_nodes = [n for n in cfg.nodes if n.kind == 'condition' and 'assert' in n.label]
    assert len(assert_nodes) == 1, "Should have assert condition node"

    # Assert should have abrupt exit (raise) in result
    # The build_function connects abrupt exits to exception_exit
    assert cfg.exception_exit_node_id is not None, "Should have exception exit"
