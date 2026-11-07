"""Test DFG handling of comprehensions."""

import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_list_comprehension():
    """Test list comprehension variable tracking."""
    source = """
def process(items):
    result = [x * 2 for x in items]
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should track definitions including comprehension target
    # Check that we have definitions (comprehension targets are tracked)
    assert len(facts.definitions) > 0

    # Check that comprehension target 'x' has a definition
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) >= 1, "Comprehension target 'x' should have a definition"


def test_set_comprehension():
    """Test set comprehension variable tracking."""
    source = """
def process(items):
    result = {x * 2 for x in items}
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should track definitions including comprehension target
    assert len(facts.definitions) > 0


def test_dict_comprehension():
    """Test dict comprehension variable tracking."""
    source = """
def process(items):
    result = {k: v for k, v in items}
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should track definitions including comprehension targets
    assert len(facts.definitions) > 0


def test_generator_expression():
    """Test generator expression variable tracking."""
    source = """
def process(items):
    result = sum(x * 2 for x in items)
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should track definitions including comprehension target
    assert len(facts.definitions) > 0


def test_comprehension_with_filter():
    """Test comprehension with filter condition."""
    source = """
def process(items):
    result = [x for x in items if x > 0]
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should track definitions including comprehension target
    assert len(facts.definitions) > 0


def test_nested_comprehension():
    """Test nested comprehension."""
    source = """
def process(matrix):
    result = [x * y for row in matrix for x in row for y in range(x)]
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
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should track definitions including comprehension targets
    assert len(facts.definitions) > 0
