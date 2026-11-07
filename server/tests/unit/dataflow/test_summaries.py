"""Tests for call summaries and library models."""
import pytest
from ai_agents.intelligence.dataflow.summaries import SummaryRegistry, FunctionSummary, infer_call_summary


def test_builtin_pure_functions():
    """Test that pure built-in functions are registered."""
    registry = SummaryRegistry()

    # Check pure functions
    assert registry.has_summary('builtins.abs')
    assert registry.has_summary('builtins.len')
    assert registry.has_summary('builtins.max')

    summary = registry.get_summary('builtins.abs')
    assert summary.pure == True
    assert summary.returns_from == [0]


def test_mutating_list_methods():
    """Test that mutating list methods are registered."""
    registry = SummaryRegistry()

    # Check list methods
    assert registry.has_summary('list.append')
    assert registry.has_summary('list.extend')
    assert registry.has_summary('list.pop')

    append_summary = registry.get_summary('list.append')
    assert append_summary.mutates == ['self']
    assert append_summary.reads == [1]
    assert append_summary.pure == False


def test_mutating_dict_methods():
    """Test that mutating dict methods are registered."""
    registry = SummaryRegistry()

    # Check dict methods
    assert registry.has_summary('dict.update')
    assert registry.has_summary('dict.pop')

    update_summary = registry.get_summary('dict.update')
    assert update_summary.mutates == ['self']
    assert update_summary.reads == [1]


def test_security_sinks():
    """Test that security sinks are registered."""
    registry = SummaryRegistry()

    # Check security sinks
    assert registry.has_summary('os.system')
    assert registry.has_summary('subprocess.run')
    assert registry.has_summary('eval')

    os_system = registry.get_summary('os.system')
    assert 'command' in os_system.sinks


def test_method_name_fallback():
    """Test that method name fallback works."""
    registry = SummaryRegistry()

    # Get summary by method name only
    summary = registry.get_summary_by_method_name('append')
    assert summary is not None
    assert summary.qualified_name == 'list.append'


def test_add_custom_summary():
    """Test that custom summaries can be added."""
    registry = SummaryRegistry()

    # Add custom summary
    custom = FunctionSummary(
        qualified_name='my_module.my_function',
        pure=True,
        returns_from=[0],
        reads=[0, 1]
    )
    registry.add_summary(custom)

    # Check it was added
    assert registry.has_summary('my_module.my_function')
    retrieved = registry.get_summary('my_module.my_function')
    assert retrieved.pure == True
    assert retrieved.returns_from == [0]


def test_save_and_load_summaries():
    """Test that summaries can be saved to and loaded from file."""
    import tempfile
    import os

    registry = SummaryRegistry()

    # Add custom summary
    custom = FunctionSummary(
        qualified_name='test.custom',
        pure=True,
        returns_from=[0]
    )
    registry.add_summary(custom)

    # Save to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name

    try:
        registry.save_to_file(temp_path)

        # Load into new registry
        new_registry = SummaryRegistry()
        new_registry.load_from_file(temp_path)

        # Check custom summary was loaded
        assert new_registry.has_summary('test.custom')
        assert new_registry.get_summary('test.custom').pure == True
    finally:
        os.unlink(temp_path)


def test_infer_call_summary():
    """Test that call summaries can be inferred from operations."""
    import ast
    from ai_agents.intelligence.dataflow.python_extractor import PythonDefUseExtractor
    from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder

    code = '''
def f():
    a = [1, 2, 3]
    a.append(4)
    return a
'''

    # Parse and build CFG
    tree = ast.parse(code)
    func_def = tree.body[0]
    function_id = 'test::f'

    cfg_builder = PythonCFGBuilder()
    cfg_artifact = cfg_builder.build_function(
        function_ast=func_def,
        function_id=function_id,
        source=code,
        file_path='test.py'
    )

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Find append operation
    append_ops = [op for op in facts.operations if op.operation == 'Call' and 'append' in op.expression.lower()]

    if append_ops:
        registry = SummaryRegistry()
        summary = infer_call_summary(append_ops[0], facts, registry)

        # Should infer as list.append
        assert summary.qualified_name == 'list.append'
        assert summary.mutates == ['self']
