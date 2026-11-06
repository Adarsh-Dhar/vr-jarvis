"""Test DFG loop-carried definitions."""

import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_loop_carried_reassignment():
    """Test that loop-carried definitions are tracked correctly."""
    source = """
def process():
    x = 0
    for i in range(10):
        x = x + 1
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
    
    # Should have two definitions of x (initial + loop)
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) >= 2
    
    # Should have uses of x (in loop and return)
    x_uses = [u for u in facts.uses if u.variable == 'x']
    assert len(x_uses) >= 2


def test_while_loop_accumulation():
    """Test while loop with accumulation."""
    source = """
def process():
    total = 0
    i = 0
    while i < 10:
        total = total + i
        i = i + 1
    return total
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
    
    # Should have multiple definitions of total and i
    total_defs = [d for d in facts.definitions if d.variable == 'total']
    i_defs = [d for d in facts.definitions if d.variable == 'i']
    assert len(total_defs) >= 2
    assert len(i_defs) >= 2


def test_nested_loop_definitions():
    """Test definitions in nested loops."""
    source = """
def process():
    x = 0
    for i in range(10):
        for j in range(10):
            x = x + 1
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
    
    # Should track x through nested loops
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    x_uses = [u for u in facts.uses if u.variable == 'x']
    assert len(x_defs) >= 2
    assert len(x_uses) >= 2


def test_loop_else_variable():
    """Test variable defined in loop else clause."""
    source = """
def process():
    for i in range(10):
        if i == 5:
            break
    else:
        x = 100
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
    
    # Should have x definition in else clause
    x_defs = [d for d in facts.definitions if d.variable == 'x']
    assert len(x_defs) >= 1
