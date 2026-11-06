"""Test tuple unpacking in DFG extraction."""
import ast
import pytest
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_tuple_unpacking_creates_separate_definitions():
    """Test that tuple unpacking creates separate definitions for each variable."""
    code = """
def process(values):
    x, y = values
    return x + y
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

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=code,
        file_path="test.py"
    )

    # Should have separate definitions for x and y
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    y_defs = [d for d in facts.definitions if d.variable == 'y']
    
    assert len(x_defs) >= 1, "Should have definition for x"
    assert len(y_defs) >= 1, "Should have definition for y"
    
    # x and y should have different binding keys
    x_binding = x_defs[0].binding_key
    y_binding = y_defs[0].binding_key
    assert x_binding != y_binding, "x and y should have different binding keys"


def test_nested_tuple_unpacking():
    """Test that nested tuple unpacking works correctly."""
    code = """
def process(values):
    (x, (y, z)) = values
    return x + y + z
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

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=code,
        file_path="test.py"
    )

    # Should have definitions for x, y, z
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    y_defs = [d for d in facts.definitions if d.variable == 'y']
    z_defs = [d for d in facts.definitions if d.variable == 'z']
    
    assert len(x_defs) >= 1, "Should have definition for x"
    assert len(y_defs) >= 1, "Should have definition for y"
    assert len(z_defs) >= 1, "Should have definition for z"
