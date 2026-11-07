"""Tests for mutation and deletion tracking."""
import pytest
import ast
from ai_agents.intelligence.dataflow.python_extractor import PythonDefUseExtractor
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
from ai_agents.intelligence.dataflow.mutation_tracker import MutationTracker, MutationRegistry


def test_tracks_mutating_methods():
    """Test that mutating method calls are tracked."""
    code = '''
def f():
    a = [1, 2, 3]
    a.append(4)
    a.extend([5, 6])
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

    # Track mutations
    tracker = MutationTracker()
    result = tracker.track_mutations(facts)

    # Should detect 2 mutations (append and extend)
    assert len(result.mutations) >= 2, "Should detect append and extend mutations"

    # Verify mutation kinds
    method_mutations = [m for m in result.mutations if m.kind == 'method_mutation']
    assert len(method_mutations) >= 2, "Should have method mutations"


def test_tracks_deletions():
    """Test that deletion events are tracked."""
    code = '''
def f():
    a = [1, 2, 3]
    del a
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

    # Track mutations
    tracker = MutationTracker()
    result = tracker.track_mutations(facts)

    # Should detect deletion
    assert len(result.deletion_events) > 0, "Should detect deletion event"
    assert result.deletion_events[0].kind == 'delete', "Deletion should have kind 'delete'"


def test_mutation_registry():
    """Test that mutation registry can be queried."""
    registry = MutationRegistry()

    # Check known mutating methods
    assert registry.is_mutating_method('append') == True
    assert registry.is_mutating_method('sort') == True
    assert registry.is_mutating_method('update') == True

    # Check non-mutating methods
    assert registry.is_mutating_method('copy') == False
    assert registry.is_mutating_method('get') == False

    # Get mutation info
    info = registry.get_mutation_info('append')
    assert info is not None
    assert info.get('mutates_receiver') == True

    # Add user-defined mutation
    registry.add_user_mutation('my_module.mutate', {'mutates_receiver': True})
    assert 'my_module.mutate' in registry.get_all_mutating_methods()


def test_affected_bindings():
    """Test that affected bindings are tracked."""
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

    # Track mutations
    tracker = MutationTracker()
    result = tracker.track_mutations(facts)

    # Should have affected bindings
    assert len(result.affected_bindings) > 0, "Should track affected bindings"


def test_get_mutation_metadata():
    """Test that mutation metadata can be retrieved for calls."""
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
        tracker = MutationTracker()
        metadata = tracker.get_mutation_metadata_for_call(append_ops[0], receiver_binding='a')

        assert metadata['side_effect'] == 'known_mutation', "append should be known mutation"
        assert metadata['confidence'] == 'high', "append should have high confidence"
        assert metadata['mutation_kind'] == 'append', "mutation_kind should be 'append'"
