"""Test CFG validation."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_valid_cfg():
    """Test validation of a valid CFG."""
    code = """
def process(value):
    if value:
        return 1
    else:
        return 0
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    builder = PythonCFGBuilder()
    cfg = builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG should be valid: {validation['errors']}"
    assert len(validation['errors']) == 0, "Should have no errors"


def test_cfg_with_entry():
    """Test that CFG has an entry node."""
    code = "def process(): return 0"
    tree = ast.parse(code)
    func_node = tree.body[0]

    builder = PythonCFGBuilder()
    cfg = builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    entry_nodes = [n for n in cfg.nodes if n.kind == 'entry']
    assert len(entry_nodes) == 1, "Should have exactly one entry node"


def test_return_no_successors():
    """Test that return nodes have no successors."""
    code = "def process(): return 0"
    tree = ast.parse(code)
    func_node = tree.body[0]

    builder = PythonCFGBuilder()
    cfg = builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    for return_node in return_nodes:
        outgoing = cfg.get_edges_from(return_node.id)
        assert len(outgoing) == 0, "Return node should have no outgoing edges"
