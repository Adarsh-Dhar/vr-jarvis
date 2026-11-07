"""Test that operation and use IDs are unique across statements."""
import pytest
from ai_agents.intelligence.dataflow.python_extractor import PythonDefUseExtractor
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
import ast


def test_ids_unique_across_statements():
    """Test that operation and use IDs are unique across all statements in a function."""
    code = '''
def f(a):
    x = a + 1
    y = a + 2
    z = foo(x) + foo(y)
    return x + y
'''
    function_ast = ast.parse(code).body[0]
    file_path = "test.py"

    # Build CFG first
    cfg_builder = PythonCFGBuilder()
    cfg_artifact = cfg_builder.build_function(function_ast, "test::f", code, file_path)

    # Extract DFG
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(cfg_artifact, code, file_path)

    # Check operation IDs are unique
    op_ids = [op.id for op in facts.operations]
    assert len(op_ids) == len(set(op_ids)), f'duplicate operation ids: {op_ids}'

    # Check use IDs are unique
    use_ids = [use.id for use in facts.uses]
    assert len(use_ids) == len(set(use_ids)), f'duplicate use ids: {use_ids}'
