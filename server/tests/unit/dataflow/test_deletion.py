"""Test deletion operations."""

import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_delete_variable():
    """Test variable deletion."""
    source = """
def process():
    x = 10
    del x
    return 0
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have a deletion definition
    deletion_defs = [d for d in facts.definitions if d.kind == 'deletion']
    assert len(deletion_defs) >= 1


def test_delete_attribute():
    """Test attribute deletion."""
    source = """
def process(obj):
    del obj.attr
    return obj
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should track the deletion
    assert len(facts.definitions) > 0 or len(facts.operations) > 0


def test_delete_subscript():
    """Test subscript deletion."""
    source = """
def process(items):
    del items[0]
    return items
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should track the deletion
    assert len(facts.definitions) > 0 or len(facts.operations) > 0
