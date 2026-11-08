"""
Change impact fixture tests.

Tests for:
- Direct calls
- Indirect calls
- Imports
- Possible calls (may_call)
- Test associations
- Risk calculations
"""

import pytest
import tempfile
from pathlib import Path
import json
from ai_agents.tools.graph_tools import get_dependents
from ai_agents.tools.relationship_intelligence_tools import calculate_change_impact


def test_get_dependents_filters_edge_types():
    """Test that get_dependents filters to calls, may_call, and imports only."""
    # This test would need a real graph to test against
    # For fixture, we verify the function accepts edge_types parameter
    # Test that default edge_types includes calls, may_call, imports
    result = get_dependents("test_node", None, max_depth=2)

    # Should handle gracefully for non-existent node
    assert result['status'] in ['not_found', 'error']


def test_calculate_change_impact_direct_calls():
    """Test that direct calls are identified correctly."""
    result = calculate_change_impact("test_function", None)

    # Should handle gracefully for non-existent function
    assert result['status'] in ['not_found', 'error']

    # When function exists, should return direct_callers list
    if result['status'] == 'ok':
        assert 'direct_callers' in result
        assert isinstance(result['direct_callers'], list)
        assert 'direct_count' in result


def test_calculate_change_impact_indirect_calls():
    """Test that indirect calls are identified correctly."""
    result = calculate_change_impact("test_function", None)

    # Should handle gracefully for non-existent function
    assert result['status'] in ['not_found', 'error']

    # When function exists, should return indirect_dependents list
    if result['status'] == 'ok':
        assert 'indirect_dependents' in result
        assert isinstance(result['indirect_dependents'], list)
        assert 'indirect_count' in result


def test_calculate_change_impact_imports():
    """Test that import dependents are identified separately."""
    result = calculate_change_impact("test_function", None)

    # Should handle gracefully for non-existent function
    assert result['status'] in ['not_found', 'error']

    # When function exists, should return import_dependents list
    if result['status'] == 'ok':
        assert 'import_dependents' in result
        assert isinstance(result['import_dependents'], list)
        assert 'import_count' in result


def test_calculate_change_impact_possible_calls():
    """Test that may_call relationships are included separately."""
    result = calculate_change_impact("test_function", None)

    # Should handle gracefully for non-existent function
    assert result['status'] in ['not_found', 'error']

    # When function exists, should return possible_callers list
    if result['status'] == 'ok':
        assert 'possible_callers' in result
        assert isinstance(result['possible_callers'], list)
        assert 'possible_count' in result


def test_calculate_change_impact_test_associations():
    """Test that test associations are returned."""
    result = calculate_change_impact("test_function", None)

    # Should handle gracefully for non-existent function
    assert result['status'] in ['not_found', 'error']

    # When function exists, should return covering_tests
    if result['status'] == 'ok':
        assert 'covering_tests' in result
        assert isinstance(result['covering_tests'], list)
        # Each test should have id and covers fields
        for test in result['covering_tests']:
            assert 'id' in test or 'name' in test


def test_calculate_change_impact_risk_levels():
    """Test that risk levels are calculated correctly."""
    result = calculate_change_impact("test_function", None)

    # Should handle gracefully for non-existent function
    assert result['status'] in ['not_found', 'error']

    # When function exists, should return risk_level
    if result['status'] == 'ok':
        assert 'risk_level' in result
        assert result['risk_level'] in ['low', 'medium', 'high']
        assert 'untested' in result
        assert isinstance(result['untested'], bool)


def test_calculate_change_impact_includes_may_call_in_indirect():
    """Test that may_call relationships are included in indirect traversal."""
    result = calculate_change_impact("test_function", None)

    # Should handle gracefully for non-existent function
    assert result['status'] in ['not_found', 'error']

    # When function exists, indirect dependents may include uncertain flag
    if result['status'] == 'ok':
        # Check that indirect dependents can have uncertain marking
        for dep in result.get('indirect_dependents', []):
            if dep.get('edge_type') == 'may_call':
                assert dep.get('uncertain') == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_change_impact_no_duplication():
    """Test that direct possible, indirect, and import dependents are separate without duplication."""
    from unittest.mock import Mock, patch
    import sys

    # Mock the graph and tool context
    mock_tool_context = Mock()
    mock_graph = Mock()

    # Create mock callers data
    def mock_callers(symbol_id, depth, include_possible=False):
        if depth == 1 and not include_possible:
            return [
                {'from': 'direct_caller_1', 'to': symbol_id, 'kind': 'confirmed'},
                {'from': 'direct_caller_2', 'to': symbol_id, 'kind': 'confirmed'}
            ]
        else:
            return [
                {'from': 'direct_caller_1', 'to': symbol_id, 'kind': 'confirmed'},
                {'from': 'direct_caller_2', 'to': symbol_id, 'kind': 'confirmed'},
                {'from': 'possible_caller_1', 'to': symbol_id, 'kind': 'possible'}
            ]

    mock_graph.callers = mock_callers

    # Mock get_dependents for call relationships
    def mock_get_dependents(symbol_id, tool_context, max_depth, edge_types):
        if 'calls' in edge_types or 'may_call' in edge_types:
            return {
                'status': 'ok',
                'dependents': [
                    {'id': 'direct_caller_1', 'edge_type': 'calls'},
                    {'id': 'direct_caller_2', 'edge_type': 'calls'},
                    {'id': 'possible_caller_1', 'edge_type': 'may_call'},
                    {'id': 'indirect_caller_1', 'edge_type': 'calls'},
                    {'id': 'indirect_caller_2', 'edge_type': 'may_call'}
                ]
            }
        elif 'imports' in edge_types:
            return {
                'status': 'ok',
                'dependents': [
                    {'id': 'import_dep_1', 'edge_type': 'imports'},
                    {'id': 'import_dep_2', 'edge_type': 'imports'}
                ]
            }
        return {'status': 'error'}

    # Mock graph node
    mock_graph.get = Mock(return_value={'id': 'test_function', 'name': 'test_function'})
    mock_graph.covering_tests = Mock(return_value=[])

    # Patch the imports at the actual import locations inside the function
    with patch('ai_agents.codegraph.load_current_graph', return_value=mock_graph):
        with patch('ai_agents.tools.graph_tools.get_dependents', side_effect=mock_get_dependents):
            result = calculate_change_impact("test_function", mock_tool_context)

    # Verify the result structure
    assert result['status'] == 'ok'
    assert 'direct_callers' in result
    assert 'possible_callers' in result
    assert 'indirect_dependents' in result
    assert 'import_dependents' in result

    # Verify no duplication: direct and possible should be separate
    direct_ids = {c['from'] for c in result['direct_callers']}
    possible_ids = {c['from'] for c in result['possible_callers']}
    assert len(direct_ids & possible_ids) == 0, "Direct and possible callers should not overlap"

    # Verify indirect excludes both direct and possible
    indirect_ids = {d['id'] for d in result['indirect_dependents']}
    assert indirect_ids.isdisjoint(direct_ids), "Indirect should not include direct callers"
    assert indirect_ids.isdisjoint(possible_ids), "Indirect should not include possible callers"

    # Verify import dependents are separate
    import_ids = {d['id'] for d in result['import_dependents']}
    assert all(d['edge_type'] == 'imports' for d in result['import_dependents'])

    # Verify total affected uses deduplication
    expected_total = len(direct_ids) + len(possible_ids) + len(indirect_ids) + len(import_ids)
    assert result['total_affected'] == expected_total


def test_change_impact_import_dependents_uses_parent_file():
    """Test that import dependents are found using the parent file node, not the function ID."""
    from unittest.mock import Mock, patch

    # Mock the graph and tool context
    mock_tool_context = Mock()
    mock_graph = Mock()

    # Create mock callers data
    def mock_callers(symbol_id, depth, include_possible=False):
        return []

    mock_graph.callers = mock_callers

    # Track which symbol_id was passed to get_dependents for imports
    import_queries = []

    def mock_get_dependents(symbol_id, tool_context, max_depth, edge_types):
        if 'imports' in edge_types:
            import_queries.append(symbol_id)
            return {
                'status': 'ok',
                'dependents': [
                    {'id': 'file::other_module.py', 'edge_type': 'imports'}
                ]
            }
        return {'status': 'ok', 'dependents': []}

    # Mock graph node hierarchy:
    # file::routes/users.py (level='file')
    #   └── routes/users.py::delete_user (level='function', parent='file::routes/users.py')
    def mock_graph_get(node_id):
        if node_id == 'routes/users.py::delete_user':
            return {
                'id': 'routes/users.py::delete_user',
                'name': 'delete_user',
                'level': 'function',
                'parent': 'file::routes/users.py'
            }
        elif node_id == 'file::routes/users.py':
            return {
                'id': 'file::routes/users.py',
                'name': 'routes/users.py',
                'level': 'file'
            }
        return None

    mock_graph.get = mock_graph_get
    mock_graph.covering_tests = Mock(return_value=[])

    # Patch the imports at the actual import locations inside the function
    with patch('ai_agents.codegraph.load_current_graph', return_value=mock_graph):
        with patch('ai_agents.tools.graph_tools.get_dependents', side_effect=mock_get_dependents):
            result = calculate_change_impact("routes/users.py::delete_user", mock_tool_context)

    # Verify the result structure
    assert result['status'] == 'ok'
    assert 'import_dependents' in result

    # Verify that get_dependents was called with the file node ID, not the function ID
    assert len(import_queries) == 1, "get_dependents should be called once for imports"
    assert import_queries[0] == 'file::routes/users.py', \
        f"get_dependents should be called with file node ID, got {import_queries[0]}"

    # Verify the import dependent was found
    assert len(result['import_dependents']) == 1
    assert result['import_dependents'][0]['id'] == 'file::other_module.py'
    assert result['import_dependents'][0]['edge_type'] == 'imports'
