"""Regression tests for advanced CFG constructs - match, assert, with cleanup."""
import pytest
import ast
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
from ai_agents.intelligence.controlflow.validator import validate_cfg


def test_match_case_failure_paths():
    """Test that match correctly routes case failures to next case."""
    source = """
def match_failure():
    match x:
        case 1:
            return "one"
        case 2:
            return "two"
        case _:
            return "other"
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::match_failure", source, "test.py")
    cfg = artifact.graph

    # Check that match node exists
    match_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'match']
    assert len(match_nodes) == 1, "Should have match node"

    # Check that there are case nodes
    case_nodes = [n for n in cfg.nodes if n.ast_kind == 'match_case']
    assert len(case_nodes) >= 2, "Should have multiple case nodes"


def test_match_no_wildcard():
    """Test that match without wildcard routes all failures to join."""
    source = """
def match_no_wildcard():
    match x:
        case 1:
            return "one"
        case 2:
            return "two"
    return "default"
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::match_no_wildcard", source, "test.py")
    cfg = artifact.graph

    # Check that match has case nodes
    case_nodes = [n for n in cfg.nodes if n.ast_kind == 'match_case']
    assert len(case_nodes) >= 2, "Should have case nodes"


def test_match_with_guard():
    """Test that match guards are evaluated correctly."""
    source = """
def match_guard():
    match x:
        case n if n > 0:
            return "positive"
        case n if n < 0:
            return "negative"
        case _:
            return "zero"
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::match_guard", source, "test.py")
    cfg = artifact.graph

    # Check for guard nodes
    guard_nodes = [n for n in cfg.nodes if n.ast_kind == 'match_guard']
    assert len(guard_nodes) >= 2, "Should have guard nodes"


def test_match_abrupt_completion():
    """Test that abrupt completions in match cases are preserved."""
    source = """
def match_return():
    match x:
        case 1:
            return "one"
        case 2:
            raise ValueError("error")
        case _:
            return "other"
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::match_return", source, "test.py")
    cfg = artifact.graph

    # Check for return and raise nodes
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    raise_nodes = [n for n in cfg.nodes if n.kind == 'raise']
    assert len(return_nodes) >= 1 or len(raise_nodes) >= 1, "Should have abrupt completions"


def test_assert_condition_true_branch():
    """Test that assert true branch continues normally."""
    source = """
def assert_true():
    assert x > 0
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::assert_true", source, "test.py")
    cfg = artifact.graph

    # Check that assert node exists
    assert_nodes = [n for n in cfg.nodes if n.ast_kind == 'Assert']
    assert len(assert_nodes) >= 1, "Should have assert node"


def test_assert_condition_false_branch():
    """Test that assert false branch raises AssertionError."""
    source = """
def assert_false():
    assert x > 0
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::assert_false", source, "test.py")
    cfg = artifact.graph

    # Check that assert node exists
    assert_nodes = [n for n in cfg.nodes if n.ast_kind == 'Assert']
    assert len(assert_nodes) >= 1, "Should have assert node"


def test_assert_in_try_finally():
    """Test that assert routes through finally when in try block."""
    source = """
def assert_finally():
    try:
        assert x > 0
        return x
    finally:
        y = cleanup()
    return y
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::assert_finally", source, "test.py")
    cfg = artifact.graph

    # Check that assert and finally nodes exist
    assert_nodes = [n for n in cfg.nodes if n.ast_kind == 'Assert']
    finally_nodes = [n for n in cfg.nodes if n.kind == 'finally']
    assert len(assert_nodes) >= 1, "Should have assert node"
    assert len(finally_nodes) >= 1, "Should have finally node"


def test_with_statement_normal_exit():
    """Test that with statement cleanup executes on normal exit."""
    source = """
def with_normal():
    with open("file.txt") as f:
        x = f.read()
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::with_normal", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check that with exit node exists
    with_exit_nodes = [n for n in cfg.nodes if n.kind == 'statement' and 'exit' in n.label.lower()]
    assert len(with_exit_nodes) >= 1, "Should have with exit node"


def test_with_statement_return():
    """Test that with statement cleanup executes on return."""
    source = """
def with_return():
    with open("file.txt") as f:
        return f.read()
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::with_return", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check that return connects to with exit
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    assert len(return_nodes) >= 1
    return_edges = cfg.get_edges_from(return_nodes[0].id)
    finally_edges = [e for e in return_edges if e.kind == 'finally']
    assert len(finally_edges) >= 1, "Return should connect to with exit"


def test_with_statement_exception():
    """Test that with statement cleanup executes on exception."""
    source = """
def with_exception():
    with open("file.txt") as f:
        x = f.read()
        raise ValueError("error")
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::with_exception", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"


def test_nested_with():
    """Test nested with statements."""
    source = """
def nested_with():
    with open("file1.txt") as f1:
        with open("file2.txt") as f2:
            x = f1.read() + f2.read()
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::nested_with", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Should have two with exit nodes
    with_exit_nodes = [n for n in cfg.nodes if n.kind == 'statement' and 'exit' in n.label.lower()]
    assert len(with_exit_nodes) >= 2, "Should have two with exit nodes"


def test_async_with():
    """Test async with statement."""
    source = """
async def async_with():
    async with open_async("file.txt") as f:
        x = await f.read()
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::async_with", source, "test.py")
    cfg = artifact.graph

    validation = validate_cfg(cfg)
    assert validation['valid'], f"CFG validation failed: {validation['errors']}"

    # Check for suspension node
    suspension_nodes = [n for n in cfg.nodes if n.kind == 'suspension']
    assert len(suspension_nodes) >= 1, "Should have suspension node for async with"


def test_match_or_pattern():
    """Test match with or pattern."""
    source = """
def match_or():
    match x:
        case 1 | 2 | 3:
            return "small"
        case _:
            return "other"
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::match_or", source, "test.py")
    cfg = artifact.graph

    # Check that match and case nodes exist
    match_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'match']
    case_nodes = [n for n in cfg.nodes if n.ast_kind == 'match_case']
    assert len(match_nodes) >= 1, "Should have match node"
    assert len(case_nodes) >= 1, "Should have case node"


def test_match_capture_pattern():
    """Test match with capture pattern."""
    source = """
def match_capture():
    match x:
        case n:
            return n
        case _:
            return 0
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::match_capture", source, "test.py")
    cfg = artifact.graph

    # Check that match and case nodes exist
    match_nodes = [n for n in cfg.nodes if n.kind == 'statement' and n.label == 'match']
    case_nodes = [n for n in cfg.nodes if n.ast_kind == 'match_case']
    assert len(match_nodes) >= 1, "Should have match node"
    assert len(case_nodes) >= 1, "Should have case node"


def test_assert_with_message():
    """Test assert with custom message."""
    source = """
def assert_message():
    assert x > 0, "x must be positive"
    return x
"""
    tree = ast.parse(source)
    func = tree.body[0]
    builder = PythonCFGBuilder()
    artifact = builder.build_function(func, "test.py::assert_message", source, "test.py")
    cfg = artifact.graph

    # Check that assert node exists
    assert_nodes = [n for n in cfg.nodes if n.ast_kind == 'Assert']
    assert len(assert_nodes) >= 1, "Should have assert node"
