"""Test DFG definitions on exception paths."""

import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_exception_handler_assignment():
    """Test assignment in exception handler."""
    source = """
def process():
    try:
        x = risky_operation()
    except ValueError:
        x = "error"
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
    
    # Should have two definitions of x (try and except)
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) >= 2


def test_multiple_exception_handlers():
    """Test multiple exception handlers with different assignments."""
    source = """
def process():
    try:
        x = risky_operation()
    except ValueError:
        x = "value_error"
    except TypeError:
        x = "type_error"
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
    
    # Should have three definitions of x (try + 2 handlers)
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) >= 3


def test_exception_else_clause():
    """Test assignment in else clause after try."""
    source = """
def process():
    try:
        x = risky_operation()
    except ValueError:
        x = "error"
    else:
        y = x + 1
    return y
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
    
    # Should have x definitions and y definition
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    y_defs = [d for d in facts.definitions if d.variable == 'y']
    assert len(x_defs) >= 2
    assert len(y_defs) >= 1


def test_finally_clause_assignment():
    """Test assignment in finally clause."""
    source = """
def process():
    x = 0
    try:
        y = risky_operation()
    except ValueError:
        y = "error"
    finally:
        x = 1
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
    
    # Should have two definitions of x (initial + finally)
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) >= 2


def test_exception_reassignment_after_handler():
    """Test reassignment after exception handler."""
    source = """
def process():
    x = 0
    try:
        risky_operation()
    except ValueError:
        x = 10
    x = x + 1
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
    
    # Should have three definitions of x (initial + handler + reassignment)
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) >= 3


def test_exception_variable_binding_consistency():
    """Test that exception variable definition and use have consistent binding keys."""
    source = """
def process():
    try:
        operation()
    except ValueError as exc:
        return exc  # Should use the same binding as the definition
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

    # Should have a definition for 'exc'
    exc_defs = [d for d in facts.definitions if d.variable == 'exc']
    assert len(exc_defs) >= 1, "Should have definition for 'exc'"

    # Should have a use for 'exc'
    exc_uses = [u for u in facts.uses if u.variable == 'exc']
    assert len(exc_uses) >= 1, "Should have use for 'exc'"

    # Check that definition and use have the same binding key
    def_binding = exc_defs[0].binding_key
    use_binding = exc_uses[0].binding_key
    assert def_binding == use_binding, f"Binding keys should match: def={def_binding}, use={use_binding}"
