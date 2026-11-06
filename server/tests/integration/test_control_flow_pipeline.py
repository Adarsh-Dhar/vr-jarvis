"""Integration test for control-flow analysis pipeline."""
import ast
import pytest
from ai_agents.intelligence.controlflow import (
    PythonCFGBuilder,
    validate_cfg,
    cfg_to_unity_format,
)


def test_control_flow_pipeline():
    """Test the complete control-flow analysis pipeline."""
    code = """
def example(value, items):
    if value > 100:
        result = 1
    else:
        result = 2
    for item in items:
        if item == 0:
            continue
        if item < 0:
            break
        result += item
    try:
        result = calculate(result)
    except ValueError:
        result = 0
    finally:
        cleanup()
    return result
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    # Step 1: Build CFG
    builder = PythonCFGBuilder()
    cfg = builder.build_function(
        function_ast=func_node,
        function_id="test::example",
        source=code,
        file_path="test.py"
    )

    # Step 2: Validate CFG
    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Step 3: Convert to dict
    cfg_dict = cfg.to_dict()
    assert 'nodes' in cfg_dict
    assert 'edges' in cfg_dict
    assert len(cfg_dict['nodes']) > 0
    assert len(cfg_dict['edges']) > 0

    # Step 4: Convert to Unity format
    unity_graph = cfg_to_unity_format(cfg)
    assert 'graph_type' in unity_graph
    assert unity_graph['graph_type'] == 'control_flow'
    assert 'nodes' in unity_graph
    assert 'edges' in unity_graph

    # Verify Unity nodes have required fields
    for node in unity_graph['nodes']:
        assert 'id' in node
        assert 'name' in node
        assert 'node_kind' in node
        assert 'function_id' in node
        assert 'file' in node
        assert 'line' in node

    # Verify Unity edges have required fields
    for edge in unity_graph['edges']:
        assert 'src' in edge
        assert 'dst' in edge
        assert 'edge_kind' in edge


def test_control_flow_with_branches():
    """Test control-flow pipeline with complex branches."""
    code = """
def process(data):
    if data:
        for item in data:
            if item.active:
                process(item)
            else:
                skip(item)
    else:
        return None
    finish()
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
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Should have multiple condition nodes for nested branches
    condition_nodes = [n for n in cfg.nodes if n.kind == 'condition']
    assert len(condition_nodes) >= 2, "Should have at least 2 condition nodes"


def test_control_flow_with_exceptions():
    """Test control-flow pipeline with exception handling."""
    code = """
def process():
    try:
        result = risky_operation()
    except ValueError as e:
        result = handle_error(e)
    except Exception:
        result = default_value()
    else:
        commit(result)
    finally:
        cleanup()
    return result
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
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Should have exception dispatch and finally nodes
    dispatch_nodes = [n for n in cfg.nodes if n.kind == 'exception_dispatch']
    finally_nodes = [n for n in cfg.nodes if n.kind == 'finally']
    assert len(dispatch_nodes) >= 1, "Should have exception dispatch node"
    assert len(finally_nodes) >= 1, "Should have finally node"
