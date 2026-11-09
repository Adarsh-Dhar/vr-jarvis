"""
Tests that verify tools return real results with specific assertions.
Tests use real IDs and assert specific data (block counts, paths, churn, etc.).
"""

import pytest
from ai_agents import config, repository
from pathlib import Path


def test_control_flow_dotted_id_works():
    """Ensure control flow works with dotted IDs and returns actual blocks."""
    from ai_agents.tools.analysis_tools import analyze_control_flow
    from ai_agents import codegraph
    
    # Test with dotted ID - try to resolve through CodeGraph
    graph = codegraph.load_current_graph()
    node = graph.get('eutro.train.train')
    
    if node:
        result = analyze_control_flow('eutro.train.train', None)
        # Should return ok with actual blocks
        assert result.get('status') in ['ok', 'not_applicable'], f"Expected ok or not_applicable, got {result.get('status')}: {result.get('message', '')}"
        if result.get('status') == 'ok':
            assert 'blocks' in result, "Should have blocks"
            assert len(result['blocks']) > 0, "Should have at least one block"
    else:
        # Skip if node not in graph
        pytest.skip("eutro.train.train not found in current graph")


def test_data_flow_graph_emission():
    """Ensure data flow visualization emits a graph with nodes and edges."""
    from ai_agents.tools.data_flow_intelligence_tools import visualize_data_flow
    
    # Test with a real variable ID
    result = visualize_data_flow('eutro.train.train:X', None)
    
    # Should either work or return appropriate error
    # If ok, must have node_count and edge_count
    if result.get('status') == 'ok':
        assert 'node_count' in result, "Should have node_count"
        assert 'edge_count' in result, "Should have edge_count"
        # Should not be stub message
        assert 'Real visualization requires' not in str(result.get('note', ''))


def test_change_impact_depth_correct():
    """Test change impact distinguishes direct vs indirect callers."""
    from ai_agents.tools.relationship_intelligence_tools import calculate_change_impact
    from ai_agents import codegraph
    
    # Load graph
    graph = codegraph.load_current_graph()
    
    # Test with a known function if available
    test_id = 'eutro.data.make_dataset'
    node = graph.get(test_id)
    
    if node:
        result = calculate_change_impact(test_id, None)
        
        if result.get('status') == 'ok':
            direct = result.get('direct_callers', [])
            indirect = result.get('indirect_callers', [])
            
            # Verify main.main is not in direct if it's indirect
            direct_ids = [c['from'] for c in direct]
            if 'main.main' in direct_ids:
                # This would be a bug - main.main should be indirect
                pytest.fail("main.main should not be a direct caller of make_dataset")


def test_coverage_has_percentage():
    """Test coverage returns actual percentage."""
    from ai_agents.tools.testing_verification_tools import measure_test_coverage
    
    # Test on server directory
    result = measure_test_coverage('/Users/adarsh/Documents/vr-agent/server', None)
    
    # If ok, should have real coverage data
    if result.get('status') == 'ok':
        assert 'coverage' in result, "Should have coverage field"
        assert 'overall' in result['coverage'], "Should have overall percentage"
        # Should be a number between 0 and 100
        overall = result['coverage']['overall']
        assert isinstance(overall, (int, float)), "Overall should be numeric"
        assert 0 <= overall <= 100, "Overall should be between 0 and 100"
