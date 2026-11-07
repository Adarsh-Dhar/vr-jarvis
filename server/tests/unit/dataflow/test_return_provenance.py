"""Test return provenance - connecting return expressions to return-value sink."""
import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder
from ai_agents.intelligence.dataflow import PythonDefUseExtractor


def test_return_operation_has_sink():
    """Verify return expression root operation is connected to return-value sink."""
    source = """
def process(a, b):
    return a + b
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test::process", source, "test.py")
    cfg = artifact.graph

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(artifact, source, "test.py")

    # Should have return-value sink operation
    return_sink_ops = [op for op in facts.operations if op.operation == 'return_value']
    assert len(return_sink_ops) >= 1, "Should have return-value sink operation"

    # Should have Add operation for a + b
    add_ops = [op for op in facts.operations if op.operation == 'Add']
    assert len(add_ops) >= 1, "Should have Add operation"

    # Return sink should reference the Add operation
    return_sink = return_sink_ops[0]
    assert len(return_sink.input_operation_ids) >= 1, "Return sink should reference operation"


def test_lambda_has_parameter_definitions():
    """Verify lambda creates parameter definitions."""
    source = """
def process():
    callback = lambda x: x + offset
    return callback
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test::process", source, "test.py")
    cfg = artifact.graph

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(artifact, source, "test.py")

    # Should have lambda operation
    lambda_ops = [op for op in facts.operations if op.operation == 'Lambda']
    assert len(lambda_ops) >= 1, "Should have Lambda operation"

    # Lambda should have parameter definitions
    lambda_op = lambda_ops[0]
    assert len(lambda_op.output_definition_ids) >= 1, "Lambda should produce parameter definitions"

    # Should have parameter definition for 'x'
    param_defs = [d for d in facts.definitions if d.kind == 'lambda_parameter']
    assert len(param_defs) >= 1, "Should have lambda parameter definition"


def test_starred_unpacking_uses_actual_name():
    """Verify starred unpacking uses underlying variable name."""
    source = """
def process(values):
    first, *remaining = values
    return first, remaining
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test::process", source, "test.py")
    cfg = artifact.graph

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(artifact, source, "test.py")

    # Should have definition for 'remaining' (not '*remaining')
    remaining_defs = [d for d in facts.definitions if d.variable == 'remaining']
    assert len(remaining_defs) >= 1, "Should have definition for 'remaining'"

    # Should be marked as starred
    remaining_def = remaining_defs[0]
    assert remaining_def.metadata.get('is_starred', False), "Should be marked as starred"
