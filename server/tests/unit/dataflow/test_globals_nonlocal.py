"""Test DFG handling of global and nonlocal declarations."""
import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_global_declaration():
    """Test that global declarations do not create value definitions."""
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

    # Should NOT have a global definition (global is a scope marker, not value definition)
    global_defs = [d for d in facts.definitions if d.kind == 'global']
    assert len(global_defs) == 0

    # Should have a regular assignment definition
    assign_defs = [d for d in facts.definitions if d.kind == 'assignment']
    assert len(assign_defs) == 1
    assert assign_defs[0].variable == 'x'


def test_multiple_globals():
    """Test multiple global declarations do not create value definitions."""
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

    # Should NOT have global definitions
    global_defs = [d for d in facts.definitions if d.kind == 'global']
    assert len(global_defs) == 0

    # Should have three regular assignment definitions
    assign_defs = [d for d in facts.definitions if d.kind == 'assignment']
    assert len(assign_defs) == 3
    variables = {d.variable for d in assign_defs}
    assert variables == {'x', 'y', 'z'}


def test_nonlocal_declaration():
    """Test that nonlocal declarations do not create value definitions."""
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

    # Should NOT have a nonlocal definition (nonlocal is a scope marker, not value definition)
    nonlocal_defs = [d for d in facts.definitions if d.kind == 'nonlocal']
    assert len(nonlocal_defs) == 0

    # Should have regular assignment definitions for x
    assign_defs = [d for d in facts.definitions if d.kind == 'assignment' and d.variable == 'x']
    assert len(assign_defs) >= 1


def test_multiple_nonlocals():
    """Test multiple nonlocal declarations do not create value definitions."""
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

    # Should NOT have nonlocal definitions
    nonlocal_defs = [d for d in facts.definitions if d.kind == 'nonlocal']
    assert len(nonlocal_defs) == 0

    # Should have regular assignment definitions
    assign_defs = [d for d in facts.definitions if d.kind == 'assignment']
    assert len(assign_defs) >= 2


def test_global_with_assignment():
    """Test that global declaration and assignment are tracked correctly."""
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

    # Should NOT have a global definition
    global_defs = [d for d in facts.definitions if d.kind == 'global']
    assert len(global_defs) == 0

    # Should have two regular assignments
    assign_defs = [d for d in facts.definitions if d.kind == 'assignment']
    assert len(assign_defs) == 2


def test_nonlocal_with_nested_scope():
    """Test that nonlocal declarations do not create value definitions in nested functions."""
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

    # Should NOT have a nonlocal definition
    nonlocal_defs = [d for d in facts.definitions if d.kind == 'nonlocal']
    assert len(nonlocal_defs) == 0

    # Should have regular assignment definitions
    assign_defs = [d for d in facts.definitions if d.kind == 'assignment']
    assert len(assign_defs) >= 1
