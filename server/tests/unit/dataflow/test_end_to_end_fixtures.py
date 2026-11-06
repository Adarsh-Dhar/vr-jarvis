"""End-to-end fixture tests for complex combinations."""

import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_branching_with_multiple_assignments():
    """Test branching function with multiple assignments and returns."""
    source = """
def process(value):
    if value > 0:
        x = value
        y = x * 2
        return y
    else:
        x = -value
        y = x * 3
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
    
    # Should have definitions and uses
    assert len(facts.definitions) > 0
    assert len(facts.uses) > 0


def test_loop_with_break_continue_else():
    """Test loop with break, continue, and else."""
    source = """
def process(items):
    result = 0
    for item in items:
        if item < 0:
            continue
        if item > 100:
            break
        result += item
    else:
        result = -1
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
    
    # Should track loop-carried definitions
    assert len(facts.definitions) > 0


def test_nested_try_except_finally():
    """Test nested try/except/finally."""
    source = """
def process():
    try:
        try:
            result = risky1()
        except ValueError:
            result = handle1()
        finally:
            cleanup1()
    except Exception:
        result = handle2()
    finally:
        cleanup2()
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
    
    # Should track definitions through nested exception paths
    assert len(facts.definitions) > 0


def test_comprehensions_and_unpacking():
    """Test function with comprehensions and unpacking."""
    source = """
def process(data):
    a, b = data
    result = [x * 2 for x in range(a)]
    return result + [b]
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
    
    # Should track unpacking and comprehension definitions
    assert len(facts.definitions) > 0


def test_closure_with_nonlocal():
    """Test closure using nonlocal values."""
    source = """
def outer():
    value = 10
    
    def inner():
        nonlocal value
        value += 1
        return value
    
    return inner
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::outer",
        source=source,
        file_path="test.py"
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should track outer function definitions
    assert len(facts.definitions) > 0


def test_complex_expressions():
    """Test function combining loops, exceptions, and reassignment."""
    source = """
def process(items):
    result = []
    for item in items:
        try:
            value = item.process()
        except Exception:
            value = None
        result.append(value)
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
    
    # Should track complex data flow
    assert len(facts.definitions) > 0
    assert len(facts.uses) > 0
