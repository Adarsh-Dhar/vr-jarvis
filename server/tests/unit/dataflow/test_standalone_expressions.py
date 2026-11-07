"""Test standalone expression statements create operation nodes."""
import ast
from ai_agents.intelligence.dataflow.python_extractor import PythonDefUseExtractor
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder


def test_standalone_function_call_creates_operation():
    """Standalone function call should create an operation node."""
    source = """
def process():
    result = 10
    cleanup()
    return result
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py",
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py",
    )
    
    # Should have an operation for the standalone cleanup() call
    operations = [op for op in facts.operations if 'cleanup' in op.expression]
    assert len(operations) > 0, "Standalone function call should create an operation"


def test_standalone_method_call_creates_operation():
    """Standalone method call should create an operation node."""
    source = """
def process(items):
    items.append(10)
    return items
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py",
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py",
    )
    
    # Should have an operation for the standalone items.append() call
    operations = [op for op in facts.operations if 'append' in op.expression]
    assert len(operations) > 0, "Standalone method call should create an operation"


def test_standalone_mutation_creates_operation():
    """Standalone mutation (e.g., list.extend) should create an operation node."""
    source = """
def process(a, b):
    a.update(b)
    return a
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py",
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py",
    )
    
    # Should have an operation for the standalone a.update() call
    operations = [op for op in facts.operations if 'update' in op.expression]
    assert len(operations) > 0, "Standalone mutation should create an operation"
