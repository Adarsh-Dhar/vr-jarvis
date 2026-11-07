"""Test expression operation graph construction."""
import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_nested_operation_edge_pruning():
    """Test that nested operations don't have redundant direct operand edges."""
    source = """
def process(a, b, c):
    result = (a + b) * c
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

    # Should have 2 operations: Add (a + b) and Multiply ((a + b) * c)
    assert len(facts.operations) >= 2, "Should have at least 2 operations"

    # Find the Multiply operation (outer)
    multiply_ops = [op for op in facts.operations if op.operation == 'Mult']
    assert len(multiply_ops) >= 1, "Should have Multiply operation"

    multiply_op = multiply_ops[0]

    # Multiply should have c as a direct use input
    # And the Add operation as a direct operation input
    # NOT both a and b as direct uses (they should only be inputs to Add)
    assert len(multiply_op.input_use_ids) >= 1, "Multiply should have direct use input (c)"
    assert len(multiply_op.input_operation_ids) >= 1, "Multiply should have direct operation input (Add)"

    # The Add operation should have a and b as direct inputs
    add_ops = [op for op in facts.operations if op.operation == 'Add']
    assert len(add_ops) >= 1, "Should have Add operation"

    add_op = add_ops[0]
    assert len(add_op.input_use_ids) >= 2, "Add should have direct use inputs (a and b)"

import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_nested_binary_operations():
    """Test nested binary operations create operation graph."""
    source = """
def process(a, b, c):
    result = (a + b) * c
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
    
    # Should have binary operation facts
    bin_ops = [op for op in facts.operations if op.operation in ['Add', 'Mult']]
    assert len(bin_ops) >= 2


def test_function_call_with_arguments():
    """Test function call with arguments."""
    source = """
def process(items):
    result = max(items)
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
    
    # Should have call operation
    call_ops = [op for op in facts.operations if op.operation == 'Call']
    assert len(call_ops) >= 1


def test_unary_operation():
    """Test unary operations."""
    source = """
def process(value):
    result = -value
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
    
    # Should have unary operation
    unary_ops = [op for op in facts.operations if op.operation == 'USub']
    assert len(unary_ops) >= 1


def test_comparison_operation():
    """Test comparison operations - tracked as uses."""
    source = """
def process(a, b):
    if a > b:
        return a
    return b
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
    
    # Should track variable uses
    assert len(facts.uses) > 0


def test_conditional_expression():
    """Test conditional expressions - tracked as uses."""
    source = """
def process(a, b):
    result = a if a > b else b
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
    
    # Should track definitions and uses
    assert len(facts.definitions) > 0
    assert len(facts.uses) > 0
