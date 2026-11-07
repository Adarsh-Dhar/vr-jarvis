"""Test qualified function name resolution with nested functions."""
import ast
from ai_agents.intelligence.parsers.python_symbol_locator import find_function_ast, _compute_qualname


def test_qualified_name_nested_functions():
    """Qualified names should distinguish nested functions with same short name."""
    source = """
class Outer:
    def helper(self):
        return 1
    
    class Inner:
        def helper(self):
            return 2
"""
    tree = ast.parse(source)
    
    # Find the first helper (Outer.helper)
    symbol1 = {
        'name': 'helper',
        'qualname': 'Outer.helper',
        'file': 'test.py',
        'start': 3,
    }
    func1 = find_function_ast(tree, symbol1)
    assert func1 is not None, "Should find Outer.helper"
    assert func1.lineno == 3, "Should find the correct helper"
    
    # Find the second helper (Outer.Inner.helper)
    symbol2 = {
        'name': 'helper',
        'qualname': 'Outer.Inner.helper',
        'file': 'test.py',
        'start': 7,
    }
    func2 = find_function_ast(tree, symbol2)
    assert func2 is not None, "Should find Outer.Inner.helper"
    assert func2.lineno == 7, "Should find the correct helper"
    
    # Verify they are different functions
    assert func1 != func2, "Should resolve to different functions"


def test_compute_qualname_simple():
    """Compute qualname for a simple function."""
    source = """
def simple():
    pass
"""
    tree = ast.parse(source)
    func = tree.body[0]
    qualname = _compute_qualname(func, tree)
    assert qualname == 'simple', f"Expected 'simple', got '{qualname}'"


def test_compute_qualname_nested_in_class():
    """Compute qualname for a function nested in a class."""
    source = """
class MyClass:
    def method(self):
        pass
"""
    tree = ast.parse(source)
    class_def = tree.body[0]
    func = class_def.body[0]
    qualname = _compute_qualname(func, tree)
    assert qualname == 'MyClass.method', f"Expected 'MyClass.method', got '{qualname}'"


def test_compute_qualname_nested_in_function():
    """Compute qualname for a function nested in another function."""
    source = """
def outer():
    def inner():
        pass
    return inner
"""
    tree = ast.parse(source)
    outer_func = tree.body[0]
    inner_func = outer_func.body[0]
    qualname = _compute_qualname(inner_func, tree)
    assert qualname == 'outer.inner', f"Expected 'outer.inner', got '{qualname}'"


def test_compute_qualname_deeply_nested():
    """Compute qualname for deeply nested functions."""
    source = """
class Outer:
    class Middle:
        def method(self):
            def nested():
                pass
            return nested
"""
    tree = ast.parse(source)
    outer_class = tree.body[0]
    middle_class = outer_class.body[0]
    method = middle_class.body[0]
    nested_func = method.body[0]
    qualname = _compute_qualname(nested_func, tree)
    assert qualname == 'Outer.Middle.method.nested', f"Expected 'Outer.Middle.method.nested', got '{qualname}'"
