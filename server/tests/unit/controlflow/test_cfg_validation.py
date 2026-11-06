"""Test CFG validation with exact correctness assertions."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg


def test_cfg_has_entry_and_exit():
    """Test that CFG has entry and exit nodes."""
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    assert cfg.entry_node_id is not None, "CFG should have entry_node_id"
    assert cfg.exit_node_id is not None, "CFG should have exit_node_id"
    assert cfg.exception_exit_node_id is not None, "CFG should have exception_exit_node_id"

    entry = cfg.get_node(cfg.entry_node_id)
    assert entry is not None, "Entry node should exist"
    assert entry.kind == "entry", f"Entry node should be entry kind, got {entry.kind}"

    exit = cfg.get_node(cfg.exit_node_id)
    assert exit is not None, "Exit node should exist"
    assert exit.kind == "exit", f"Exit node should be exit kind, got {exit.kind}"


def test_return_nodes_have_no_successors():
    """Test that return nodes have no outgoing edges except to exit."""
    code = """
def process(value):
    if value:
        return 1
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    return_nodes = [n for n in cfg.nodes if n.kind == "return"]
    assert len(return_nodes) >= 1, "Should have at least one return node"

    for return_node in return_nodes:
        outgoing = cfg.get_edges_from(return_node.id)
        # Return nodes should only connect to exit with return edge
        for edge in outgoing:
            assert edge.target == cfg.exit_node_id, f"Return node {return_node.id} should only connect to exit"
            assert edge.kind == "return", f"Return edge should be return kind, got {edge.kind}"


def test_no_duplicate_node_ids():
    """Test that CFG has no duplicate node IDs."""
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    node_ids = [n.id for n in cfg.nodes]
    assert len(node_ids) == len(set(node_ids)), "Node IDs should be unique"


def test_no_duplicate_edge_ids():
    """Test that CFG has no duplicate edge IDs."""
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    edge_ids = [e.id for e in cfg.edges]
    assert len(edge_ids) == len(set(edge_ids)), "Edge IDs should be unique"


def test_all_edge_endpoints_exist():
    """Test that all edges reference existing nodes."""
    code = """
def process(value):
    if value:
        return 1
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
    assert validation["valid"], f"CFG validation failed: {validation['errors']}"

    node_ids = {n.id for n in cfg.nodes}
    for edge in cfg.edges:
        assert edge.source in node_ids, f"Edge {edge.id} source {edge.source} does not exist"
        assert edge.target in node_ids, f"Edge {edge.id} target {edge.target} does not exist"
