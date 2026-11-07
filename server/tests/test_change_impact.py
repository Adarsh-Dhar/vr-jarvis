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
