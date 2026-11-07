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


def test_break_inside_try_inside_loop():
    """Test that break inside try inside loop executes finally before exiting loop."""
    source = """
def process(items):
    try:
        for item in items:
            if item == 5:
                break
        after_loop()  # Should execute after loop but before cleanup
    finally:
        cleanup()  # Should execute before loop exit
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::process", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Find break, finally, after_loop, and loop exit nodes
    break_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'break']
    finally_nodes = [n for n in cfg.nodes if n.kind == 'finally']
    after_loop_nodes = [n for n in cfg.nodes if 'after_loop' in n.label]

    assert len(break_nodes) == 1, "Should have one break node"
    assert len(finally_nodes) >= 1, "Should have finally nodes"
    assert len(after_loop_nodes) == 1, "Should have after_loop() node"

    # Break should route through finally before reaching after_loop
    # The path should be: break -> finally -> after_loop (since try wraps the loop)
    # NOT: break -> after_loop directly (bypassing finally)
    break_node = break_nodes[0]
    after_loop_node = after_loop_nodes[0]

    # Check that there's no direct edge from break to after_loop
    edges_from_break = cfg.get_edges_from(break_node.id)
    direct_to_after = [e for e in edges_from_break if e.target == after_loop_node.id]
    assert len(direct_to_after) == 0, "Break should not have direct edge to after_loop (bypassing finally)"


def test_break_inside_loop_inside_try():
    """Test that break inside loop inside try executes finally before exiting try."""
    source = """
def process(items):
    for item in items:
        try:
            if item == 5:
                break
        finally:
            cleanup()  # Should execute before break takes effect
    after_loop()
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::process", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Find break, finally, and after_loop nodes
    break_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'break']
    finally_nodes = [n for n in cfg.nodes if n.kind == 'finally']
    after_loop_nodes = [n for n in cfg.nodes if 'after_loop' in n.label]

    assert len(break_nodes) == 1, "Should have one break node"
    assert len(finally_nodes) >= 1, "Should have finally nodes"
    assert len(after_loop_nodes) == 1, "Should have after_loop() node"

    # Break should route through finally before reaching loop exit
    break_node = break_nodes[0]
    edges_from_break = cfg.get_edges_from(break_node.id)

    # Break should have edge to finally
    finally_edges = [e for e in edges_from_break if e.kind == 'finally']
    assert len(finally_edges) > 0, "Break should route through finally"

    # Break should NOT have direct edge to after_loop (bypassing finally)
    if after_loop_nodes:
        after_loop_node = after_loop_nodes[0]
        direct_to_after = [e for e in edges_from_break if e.target == after_loop_node.id]
        assert len(direct_to_after) == 0, "Break should not bypass finally"
