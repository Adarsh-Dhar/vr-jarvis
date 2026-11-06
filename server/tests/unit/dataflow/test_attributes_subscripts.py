"""Test DFG handling of attribute and subscript access."""

import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_attribute_access():
    """Test that attribute access is tracked as an operation."""
    source = """
def process(obj):
    x = obj.value
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have an Attribute operation
    attr_ops = [op for op in facts.operations if op.operation == 'Attribute']
    assert len(attr_ops) == 1
    assert attr_ops[0].metadata.get('attribute') == 'value'


def test_chained_attributes():
    """Test chained attribute access."""
    source = """
def process(obj):
    x = obj.attr1.attr2
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have Attribute operations for both attr1 and attr2
    attr_ops = [op for op in facts.operations if op.operation == 'Attribute']
    assert len(attr_ops) >= 2  # At least 2 for the chained access


def test_subscript_access():
    """Test that subscript access is tracked as an operation."""
    source = """
def process(arr):
    x = arr[0]
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have a Subscript operation
    sub_ops = [op for op in facts.operations if op.operation == 'Subscript']
    assert len(sub_ops) >= 1


def test_subscript_with_slice():
    """Test subscript with slice notation."""
    source = """
def process(arr):
    x = arr[1:5]
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have a Subscript operation
    sub_ops = [op for op in facts.operations if op.operation == 'Subscript']
    assert len(sub_ops) >= 1


def test_attribute_in_expression():
    """Test attribute access within larger expression."""
    source = """
def process(obj):
    x = obj.value + 1
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have Attribute and Add operations
    attr_ops = [op for op in facts.operations if op.operation == 'Attribute']
    add_ops = [op for op in facts.operations if op.operation == 'Add']
    assert len(attr_ops) >= 1
    assert len(add_ops) >= 1


def test_subscript_in_loop():
    """Test subscript access in loop."""
    source = """
def process(arr):
    for i in range(len(arr)):
        x = arr[i]
        print(x)
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
    
    # Should have a Subscript operation
    sub_ops = [op for op in facts.operations if op.operation == 'Subscript']
    assert len(sub_ops) >= 1
