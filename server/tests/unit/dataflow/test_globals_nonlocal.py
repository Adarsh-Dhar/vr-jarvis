"""Test DFG handling of global and nonlocal declarations."""
import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_global_declaration():
    """Test that global declarations are tracked as definitions."""
    source = """
def foo():
    global x
    x = 1
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::foo",
        source=source,
        file_path="test.py"
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have a global definition
    global_defs = [d for d in facts.definitions if d.kind == 'global']
    assert len(global_defs) == 1
    assert global_defs[0].variable == 'x'
    assert global_defs[0].binding_key == 'global::x'


def test_multiple_globals():
    """Test multiple global declarations."""
    source = """
def foo():
    global x, y, z
    x = 1
    y = 2
    z = 3
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::foo",
        source=source,
        file_path="test.py"
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have three global definitions
    global_defs = [d for d in facts.definitions if d.kind == 'global']
    assert len(global_defs) == 3
    variables = {d.variable for d in global_defs}
    assert variables == {'x', 'y', 'z'}


def test_nonlocal_declaration():
    """Test that nonlocal declarations are tracked as definitions."""
    source = """
def outer():
    x = 1
    def inner():
        nonlocal x
        x = 2
    return inner
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::outer",
        source=source,
        file_path="test.py"
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have a nonlocal definition
    nonlocal_defs = [d for d in facts.definitions if d.kind == 'nonlocal']
    assert len(nonlocal_defs) == 1
    assert nonlocal_defs[0].variable == 'x'
    assert 'nonlocal::test::outer::x' in nonlocal_defs[0].binding_key


def test_multiple_nonlocals():
    """Test multiple nonlocal declarations."""
    source = """
def outer():
    x = 1
    y = 2
    def inner():
        nonlocal x, y
        x = 3
        y = 4
    return inner
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::outer",
        source=source,
        file_path="test.py"
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have two nonlocal definitions
    nonlocal_defs = [d for d in facts.definitions if d.kind == 'nonlocal']
    assert len(nonlocal_defs) == 2
    variables = {d.variable for d in nonlocal_defs}
    assert variables == {'x', 'y'}


def test_global_with_assignment():
    """Test that global declaration and assignment are both tracked."""
    source = """
def foo():
    global x
    x = 10
    x = x + 1
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::foo",
        source=source,
        file_path="test.py"
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have one global declaration
    global_defs = [d for d in facts.definitions if d.kind == 'global']
    assert len(global_defs) == 1
    
    # Should have two regular assignments
    assign_defs = [d for d in facts.definitions if d.kind == 'assignment']
    assert len(assign_defs) == 2


def test_nonlocal_with_nested_scope():
    """Test that nonlocal declarations are tracked even in nested functions."""
    source = """
def outer():
    x = 1
    def inner():
        nonlocal x
        x = 2
    return inner
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::outer",
        source=source,
        file_path="test.py"
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have a nonlocal definition
    nonlocal_defs = [d for d in facts.definitions if d.kind == 'nonlocal']
    assert len(nonlocal_defs) == 1
    assert nonlocal_defs[0].variable == 'x'
    assert 'nonlocal::test::outer::x' in nonlocal_defs[0].binding_key
