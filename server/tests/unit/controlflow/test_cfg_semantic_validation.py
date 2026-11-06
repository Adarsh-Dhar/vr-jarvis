"""Test CFG semantic validation."""

import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder
from ai_agents.intelligence.controlflow.validator import validate_cfg


def test_cfg_unique_node_ids():
    """Test that CFG nodes have unique IDs."""
    source = """
def process(value):
    if value > 0:
        return value
    else:
        return -value
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
    
    result = validate_cfg(artifact.graph)
    
    assert result['valid'] is True
    assert len(result['errors']) == 0


def test_cfg_unique_edge_ids():
    """Test that CFG edges have unique IDs."""
    source = """
def process(items):
    for item in items:
        if item > 0:
            break
    return len(items)
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
    
    result = validate_cfg(artifact.graph)
    
    assert result['valid'] is True
    assert len(result['errors']) == 0


def test_cfg_valid_entry_exit():
    """Test that CFG has valid entry and exit nodes."""
    source = """
def process():
    return 42
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
    
    result = validate_cfg(artifact.graph)
    
    assert result['valid'] is True
    assert artifact.graph.entry_node_id is not None


def test_cfg_break_bypasses_else():
    """Test that break bypasses loop else."""
    source = """
def process(items):
    for item in items:
        if item > 10:
            break
    else:
        x = 100
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
    
    result = validate_cfg(artifact.graph)
    
    assert result['valid'] is True


def test_cfg_valid_source_locations():
    """Test that CFG nodes have valid source locations."""
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
    
    result = validate_cfg(artifact.graph)
    
    assert result['valid'] is True
    # All nodes should have valid line numbers
    for node in artifact.graph.nodes:
        assert node.start_line > 0
