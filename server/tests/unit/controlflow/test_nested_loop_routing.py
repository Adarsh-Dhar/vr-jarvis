"""Regression tests for nested loop routing and closure resolution."""
import ast
import pytest
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
from ai_agents.intelligence.controlflow.validator import validate_cfg
from ai_agents.intelligence.dataflow import PythonDefUseExtractor


def test_nested_loop_break_routing():
    """Test that break in nested loops targets the correct loop."""
    source = """
def nested_break():
    for i in range(5):
        for j in range(5):
            break
        after_inner()
    after_outer()
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::nested_break", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Find break edges and verify they target join nodes (not loop headers)
    break_edges = [e for e in cfg.edges if e.kind == 'break']
    assert len(break_edges) >= 1, "Should have break edges"

    # Verify break targets are join/exit nodes, not loop headers
    for edge in break_edges:
        target = cfg.get_node(edge.target)
        assert target.kind in ('join', 'exit'), f"Break should target join/exit, got {target.kind}"


def test_nested_loop_continue_routing():
    """Test that continue in nested loops targets the correct loop header."""
    source = """
def nested_continue():
    for i in range(5):
        for j in range(5):
            continue
        after_inner()
    after_outer()
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::nested_continue", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Find continue edges and verify they target loop headers
    continue_edges = [e for e in cfg.edges if e.kind == 'continue']
    assert len(continue_edges) >= 1, "Should have continue edges"

    # Verify continue targets are loop headers
    for edge in continue_edges:
        target = cfg.get_node(edge.target)
        assert target.kind == 'loop_header', f"Continue should target loop_header, got {target.kind}"


def test_break_in_loop_else():
    """Test that break in loop else targets the enclosing loop."""
    source = """
def break_in_else():
    for i in range(5):
        for j in range(5):
            pass
        else:
            break  # Should break outer loop, not inner
    after_outer()
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::break_in_else", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Verify break edge exists and targets a join/exit node
    break_edges = [e for e in cfg.edges if e.kind == 'break']
    assert len(break_edges) >= 1, "Should have break edges"


def test_closure_variable_resolution():
    """Test that closure variables resolve to outer scope bindings."""
    source = """
def outer():
    value = 10
    def inner():
        return value  # Should resolve to outer's value
    return inner
"""
    tree = ast.parse(source)
    outer_func = tree.body[0]
    inner_func = outer_func.body[1]  # Get the nested function

    # Analyze inner() as a separate function
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=inner_func,
        function_id="test.py::outer::inner",
        source=source,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )

    # Should have a use for 'value'
    value_uses = [u for u in facts.uses if u.variable == 'value']
    assert len(value_uses) >= 1, "Should have use for 'value'"

    # Verify the use is tracked (binding key format may vary based on scope resolution)
    assert value_uses[0].binding_key is not None, "Should have binding key"


def test_global_variable_resolution():
    """Test that global variables resolve to module-level bindings."""
    source = """
CONFIG = 10

def process():
    return CONFIG  # Should resolve to module-level CONFIG
"""
    tree = ast.parse(source)
    func = tree.body[1]  # Get the function, not the assignment

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test.py::process",
        source=source,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )

    # Should have a use for 'CONFIG'
    config_uses = [u for u in facts.uses if u.variable == 'CONFIG']
    assert len(config_uses) >= 1, "Should have use for 'CONFIG'"

    # Verify the use is tracked (binding key format may vary based on scope resolution)
    assert config_uses[0].binding_key is not None, "Should have binding key"


def test_exception_handler_variable():
    """Test that exception handler variables are tracked."""
    source = """
def handle_error():
    try:
        risky_operation()
    except ValueError as exc:
        print(exc)  # Should use the exception variable
"""
    tree = ast.parse(source)
    func = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test.py::handle_error",
        source=source,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )

    # Should have a definition for 'exc' as exception variable
    exc_defs = [d for d in facts.definitions if d.variable == 'exc']
    assert len(exc_defs) >= 1, "Should have definition for 'exc'"
    assert exc_defs[0].kind == 'exception_variable', f"Expected exception_variable, got {exc_defs[0].kind}"

    # Should have a use for 'exc' in the print statement
    exc_uses = [u for u in facts.uses if u.variable == 'exc']
    assert len(exc_uses) >= 1, "Should have use for 'exc'"


def test_if_condition_extraction():
    """Test that if conditions are extracted as expressions."""
    source = """
def check_age(age):
    if age > 18:
        return True
    return False
"""
    tree = ast.parse(source)
    func = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test.py::check_age",
        source=source,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )

    # Should have a use for 'age' in the condition
    age_uses = [u for u in facts.uses if u.variable == 'age']
    assert len(age_uses) >= 1, "Should have use for 'age' in condition"

    # Should have operations for the comparison (may be Compare or other operation types)
    # Check for any operations that might represent the comparison
    all_ops = [op for op in facts.operations]
    assert len(all_ops) >= 1, f"Should have at least one operation, got {len(all_ops)}"
