"""Test DFG binding consistency."""

import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_definition_binding_keys_consistent():
    """Test that definitions use consistent binding keys."""
    source = """
def process():
    x = 1
    x = 2
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
    
    # All definitions of 'x' should have the same binding key
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    binding_keys = {d.binding_key for d in x_defs}
    assert len(binding_keys) == 1


def test_parameter_binding_key():
    """Test that parameters have correct binding keys."""
    source = """
def process(value):
    result = value + 1
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
    
    # Parameter should have a binding key
    param_defs = [d for d in facts.definitions if d.kind == 'parameter']
    assert len(param_defs) >= 1
    assert param_defs[0].binding_key is not None


def test_uses_reference_valid_bindings():
    """Test that uses reference valid binding keys."""
    source = """
def process():
    x = 1
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
    
    # Collect all binding keys from definitions
    binding_keys = {d.binding_key for d in facts.definitions}
    
    # All uses should reference valid binding keys
    for use in facts.uses:
        assert use.binding_key in binding_keys


def test_augmented_assignment_binding_consistency():
    """Test that augmented assignments maintain binding consistency."""
    source = """
def process():
    x = 1
    x += 1
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
    
    # All definitions of 'x' should have the same binding key
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    binding_keys = {d.binding_key for d in x_defs}
    assert len(binding_keys) == 1
