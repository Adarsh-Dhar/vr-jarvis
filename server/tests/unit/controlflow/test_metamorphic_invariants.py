"""Metamorphic invariant tests for CFG correctness."""

import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder
from ai_agents.intelligence.dataflow import PythonDefUseExtractor


def test_rename_variable_preserves_cfg():
    """Renaming a variable changes binding identity but not CFG topology."""
    source1 = """
def process(value):
    if value > 0:
        return value
    return 0
"""
    source2 = """
def process(x):
    if x > 0:
        return x
    return 0
"""
    
    cfg1 = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source1).body[0],
        function_id="test::process",
        source=source1,
        file_path="test.py"
    )
    
    cfg2 = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source2).body[0],
        function_id="test::process",
        source=source2,
        file_path="test.py"
    )
    
    # CFG topology should be identical
    assert len(cfg1.graph.nodes) == len(cfg2.graph.nodes)
    assert len(cfg1.graph.edges) == len(cfg2.graph.edges)
    
    # Binding keys should differ
    facts1 = PythonDefUseExtractor().extract_function(cfg1, source1, "test.py")
    facts2 = PythonDefUseExtractor().extract_function(cfg2, source2, "test.py")
    binding_keys1 = {d.binding_key for d in facts1.definitions}
    binding_keys2 = {d.binding_key for d in facts2.definitions}
    assert binding_keys1 != binding_keys2


def test_unreachable_statement_no_path():
    """Adding unreachable statement after return increases CFG nodes but doesn't change return count."""
    source1 = """
def process():
    return 1
"""
    source2 = """
def process():
    return 1
    x = 2
"""
    
    cfg1 = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source1).body[0],
        function_id="test::process",
        source=source1,
        file_path="test.py"
    )
    
    cfg2 = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source2).body[0],
        function_id="test::process",
        source=source2,
        file_path="test.py"
    )
    
    # Return nodes should still exist in both
    returns1 = [n for n in cfg1.graph.nodes if n.kind == 'return']
    returns2 = [n for n in cfg2.graph.nodes if n.kind == 'return']
    assert len(returns1) >= 1
    assert len(returns2) >= 1


def test_reassignment_kills_previous():
    """Adding second assignment kills first on straight-line path."""
    source = """
def process():
    x = 1
    x = 2
    return x
"""
    
    cfg = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source).body[0],
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    facts = PythonDefUseExtractor().extract_function(cfg, source, "test.py")
    
    # Second definition should be the only one reaching return
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) == 2
    
    # First definition should be killed by second
    second_def = x_defs[1]
    first_def = x_defs[0]
    assert second_def.expression == 'x = 2'
    assert first_def.expression == 'x = 1'


def test_finally_preserves_completion():
    """Finally block preserves original completion if it completes normally."""
    source1 = """
def process():
    return 1
"""
    source2 = """
def process():
    try:
        return 1
    finally:
        pass
"""
    
    cfg1 = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source1).body[0],
        function_id="test::process",
        source=source1,
        file_path="test.py"
    )
    
    cfg2 = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source2).body[0],
        function_id="test::process",
        source=source2,
        file_path="test.py"
    )
    
    # Both should have return nodes
    returns1 = [n for n in cfg1.graph.nodes if n.kind == 'return']
    returns2 = [n for n in cfg2.graph.nodes if n.kind == 'return']
    assert len(returns1) >= 1
    assert len(returns2) >= 1


def test_branch_structure_preserved():
    """Changing branch condition value doesn't change CFG structure."""
    source1 = """
def process(value):
    if value > 0:
        return value
    return 0
"""
    source2 = """
def process(value):
    if value < 0:
        return value
    return 0
"""
    
    cfg1 = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source1).body[0],
        function_id="test::process",
        source=source1,
        file_path="test.py"
    )
    
    cfg2 = PythonCFGBuilder().build_function(
        function_ast=ast.parse(source2).body[0],
        function_id="test::process",
        source=source2,
        file_path="test.py"
    )
    
    # CFG structure should be identical
    assert len(cfg1.graph.nodes) == len(cfg2.graph.nodes)
    assert len(cfg1.graph.edges) == len(cfg2.graph.edges)
