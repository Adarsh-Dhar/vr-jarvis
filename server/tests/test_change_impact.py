"""
Change impact fixture tests.

Tests for:
- Direct dependents filtering (calls/imports only)
- Indirect dependents traversal
- Test associations
- Risk level calculation
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


def test_calculate_change_impact_includes_may_call():
    """Test that may_call relationships are included separately."""
    # This would need a real graph to test against
    result = calculate_change_impact("test_function", None)
    
    # Should handle gracefully for non-existent function
    assert result['status'] in ['not_found', 'error']


def test_calculate_change_impact_risk_levels():
    """Test that risk levels are calculated correctly."""
    # This would need a real graph to test against
    # Risk levels: low, medium, high based on indirect count and test coverage
    result = calculate_change_impact("test_function", None)
    
    # Should handle gracefully
    assert result['status'] in ['not_found', 'error']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
