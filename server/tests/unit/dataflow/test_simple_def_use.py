"""Test simple definition-use extraction."""
import ast
import pytest
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_simple_assignment():
    """Test definition/use extraction for simple assignment."""
    code = """
def process(value):
    x = value * 2
    return x
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        function_ast=func_node,
        function_id="test::process",
        source=code
    )

    # Should have at least one definition (x = value * 2)
    assert len(facts.definitions) >= 1, "Should have at least one definition"

    # Should have uses (value, x in return)
    assert len(facts.uses) >= 1, "Should have at least one use"

    # Check that x is defined
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) >= 1, "x should be defined"


def test_multiple_assignments():
    """Test definition/use extraction for multiple assignments."""
    code = """
def process(a, b):
    x = a
    y = b
    z = x + y
    return z
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        function_ast=func_node,
        function_id="test::process",
        source=code
    )

    # Should have parameter definitions (a, b)
    param_defs = [d for d in facts.definitions if d.kind == 'parameter']
    assert len(param_defs) >= 2, "Should have at least 2 parameter definitions"

    # Should have assignment definitions (x, y, z)
    assign_defs = [d for d in facts.definitions if d.kind == 'assignment']
    assert len(assign_defs) >= 3, "Should have at least 3 assignment definitions"


def test_annotated_assignment():
    """Test definition/use extraction for annotated assignment."""
    code = """
def process(value):
    x: int = value * 2
    return x
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        function_ast=func_node,
        function_id="test::process",
        source=code
    )

    # Should have annotated assignment definition
    ann_defs = [d for d in facts.definitions if d.kind == 'annotated_assignment']
    assert len(ann_defs) >= 1, "Should have at least one annotated assignment"


def test_augmented_assignment():
    """Test definition/use extraction for augmented assignment."""
    code = """
def process(value):
    total = 0
    total += value
    return total
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        function_ast=func_node,
        function_id="test::process",
        source=code
    )

    # Should have augmented assignment definition
    aug_defs = [d for d in facts.definitions if d.kind == 'augmented_assignment']
    assert len(aug_defs) >= 1, "Should have at least one augmented assignment"

    # total should be used in the augmented assignment
    total_uses = [u for u in facts.uses if u.variable == 'total']
    assert len(total_uses) >= 1, "total should be used in augmented assignment"
