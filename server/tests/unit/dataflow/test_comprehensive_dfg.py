"""Comprehensive DFG regression tests."""

import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_complex_function_with_all_constructs():
    """Test a function with multiple control-flow constructs."""
    source = """
def process(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
        elif item < 0:
            result.append(abs(item))
        else:
            result.append(0)
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
    
    # Should track all variables
    assert len(facts.definitions) > 0
    assert len(facts.uses) > 0


def test_function_with_parameters_and_operations():
    """Test function with parameters and complex operations."""
    source = """
def calculate(a, b, c):
    x = a + b
    y = x * c
    z = y - a
    return z
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::calculate",
        source=source,
        file_path="test.py"
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have parameter definitions
    param_defs = [d for d in facts.definitions if d.kind == 'parameter']
    assert len(param_defs) == 3
    
    # Should have operation facts for binary operations
    assert len(facts.operations) >= 3


def test_nested_control_flow():
    """Test nested if/else in loops."""
    source = """
def process(items):
    results = []
    for item in items:
        if item > 10:
            if item < 20:
                results.append("small")
            else:
                results.append("large")
        else:
            results.append("tiny")
    return results
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
    
    # Should track through nested structure
    assert len(facts.definitions) > 0
    assert len(facts.uses) > 0


def test_augmented_assignments():
    """Test augmented assignments."""
    source = """
def process():
    x = 0
    x += 1
    x *= 2
    x -= 3
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
    
    # Should have multiple definitions of x (initial + augmented)
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) >= 4


def test_function_calls_in_expressions():
    """Test function calls in expressions."""
    source = """
def process():
    x = len([1, 2, 3])
    y = abs(-5)
    z = max(x, y)
    return z
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
    
    # Should have call operations
    call_ops = [op for op in facts.operations if op.operation == 'Call']
    assert len(call_ops) >= 3


def test_boolean_expressions():
    """Test boolean expressions in conditions."""
    source = """
def process(a, b, c):
    if a and b:
        x = 1
    elif b or c:
        x = 2
    else:
        x = 3
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
    
    # Should track parameters and definitions
    param_defs = [d for d in facts.definitions if d.kind == 'parameter']
    assert len(param_defs) == 3
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) >= 3
