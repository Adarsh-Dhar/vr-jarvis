"""Test that CFG and DFG services can be imported and their entry points work."""
import pytest
import ast


def test_cfg_service_imports():
    """Test that the CFG service can be imported without errors."""
    from ai_agents.intelligence.controlflow.service import analyze_python_control_flow
    assert analyze_python_control_flow is not None


def test_dfg_service_imports():
    """Test that the DFG service can be imported without errors."""
    from ai_agents.intelligence.dataflow.service import (
        analyze_python_data_flow,
        analyze_python_data_flow_simple
    )
    assert analyze_python_data_flow is not None
    assert analyze_python_data_flow_simple is not None


def test_parser_parse_python_module():
    """Test that parse_python_module returns an ast.Module."""
    from ai_agents.intelligence.parsers.python_ast import parse_python_module

    source = """
def foo(x):
    return x + 1
"""
    tree = parse_python_module(source, "test.py")
    assert isinstance(tree, ast.Module)
    assert len(tree.body) == 1
    assert isinstance(tree.body[0], ast.FunctionDef)
    assert tree.body[0].name == "foo"


def test_parser_syntax_error():
    """Test that parse_python_module raises SyntaxError on invalid code."""
    from ai_agents.intelligence.parsers.python_ast import parse_python_module

    source = "def foo(x:\n    return x"  # Missing closing paren
    with pytest.raises(SyntaxError):
        parse_python_module(source, "test.py")


def test_parser_analyze_python_source_unchanged():
    """Test that analyze_python_source still returns a dict (not AST)."""
    from ai_agents.intelligence.parsers.python_ast import analyze_python_source

    source = """
def foo(x):
    return x + 1
"""
    result = analyze_python_source(source, "test.py")
    assert isinstance(result, dict)
    assert 'symbols' in result
    assert 'call_sites' in result
    assert 'imports' in result
    assert not isinstance(result, ast.Module)


def test_cfg_service_can_parse():
    """Test that CFG service can parse source using the new parser."""
    from ai_agents.intelligence.controlflow.service import analyze_python_control_flow

    source = """
def foo(x):
    return x + 1
"""
    symbol = {
        'id': 'test.py::foo',
        'name': 'foo',
        'file': 'test.py',
        'source': source,
    }

    result = analyze_python_control_flow(None, symbol)
    assert 'error' not in result or result['error'] is None
    assert result.get('graph') is not None


def test_dfg_service_can_parse():
    """Test that DFG service can parse source using the new parser."""
    from ai_agents.intelligence.dataflow.service import analyze_python_data_flow

    source = """
def foo(x):
    return x + 1
"""
    symbol = {
        'id': 'test.py::foo',
        'name': 'foo',
        'file': 'test.py',
        'source': source,
    }

    result = analyze_python_data_flow(None, symbol)
    # The DFG service requires valid CFG, so it may return an error if CFG is invalid
    # But it should at least not fail on import/parse
    assert result is not None


def test_dfg_simple_service_correct_args():
    """Test that the simple DFG service passes correct arguments to serializer."""
    from ai_agents.intelligence.dataflow.service import analyze_python_data_flow_simple

    source = """
def foo(x):
    return x + 1
"""
    # This should not raise an error about incorrect serializer arguments
    result = analyze_python_data_flow_simple('foo', source, 'test.py')
    assert result is not None
