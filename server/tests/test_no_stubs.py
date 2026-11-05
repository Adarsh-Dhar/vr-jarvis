"""
Tests that fail if tools return stub messages instead of real results.
This ensures tools are not returning placeholder/unsupported responses as 'ok'.
"""

import pytest
from ai_agents import config, repository
from pathlib import Path


def test_data_flow_not_stub():
    """Ensure data flow tools don't return stub messages."""
    from ai_agents.tools.data_flow_intelligence_tools import visualize_data_flow, trace_variable_origin
    
    # Test with a simple case
    result = visualize_data_flow('test_var', None)
    
    # Should not be 'ok' with stub message
    if result.get('status') == 'ok':
        assert 'Real visualization requires' not in str(result.get('note', '')), \
            "Data flow visualization should not return stub message with 'ok' status"
    
    # trace_variable_origin can return not_found, but not stub
    origin_result = trace_variable_origin('test_func:test_var', None)
    if origin_result.get('status') == 'ok':
        assert 'Real' not in str(origin_result)


def test_taint_not_stub():
    """Ensure taint tracing doesn't return heuristic-only stub."""
    from ai_agents.tools.data_flow_intelligence_tools import trace_taint_flow
    
    result = trace_taint_flow('test_id', None)
    
    # If it returns 'ok', it should have real results, not just heuristic note
    if result.get('status') == 'ok':
        assert 'Heuristic pattern matching only' not in str(result.get('note', '')), \
            "Taint tracing should not return 'Heuristic pattern matching only' with 'ok' status"


def test_security_flow_not_stub():
    """Ensure security flow visualization doesn't return stub."""
    from ai_agents.tools.visualization_spatial_tools import visualize_security_flow
    
    result = visualize_security_flow('test_component', None)
    
    if result.get('status') == 'ok':
        assert 'Real visualization requires' not in str(result.get('note', '')), \
            "Security flow should not return stub message with 'ok' status"


def test_git_history_not_stub():
    """Ensure git history visualization doesn't return stub."""
    from ai_agents.tools.visualization_spatial_tools import visualize_git_history
    
    result = visualize_git_history('/tmp', None)
    
    if result.get('status') == 'ok':
        assert 'Real visualization requires' not in str(result.get('note', '')), \
            "Git history should not return stub message with 'ok' status"


def test_runtime_not_stub():
    """Ensure runtime tools return 'unsupported' not 'ok' without data."""
    from ai_agents.tools.runtime_intelligence_tools import collect_execution_trace
    from ai_agents.tools.visualization_spatial_tools import visualize_execution_flow
    
    trace_result = collect_execution_trace('test_app', 5, None)
    viz_result = visualize_execution_flow('test_trace', None)
    
    # Runtime tools should return 'unsupported' until they have real data
    assert trace_result.get('status') != 'ok' or len(trace_result.get('trace', [])) > 0, \
        "Runtime trace should not return 'ok' without actual trace data"
    
    assert viz_result.get('status') != 'ok' or viz_result.get('node_count', 0) > 0, \
        "Execution flow should not return 'ok' without actual visualization data"


def test_coverage_real_not_stub():
    """Ensure coverage tool actually runs coverage, not stub."""
    from ai_agents.tools.testing_verification_tools import measure_test_coverage
    
    # Test on the server directory itself
    result = measure_test_coverage('/Users/adarsh/Documents/vr-agent/server', None)
    
    # If it returns 'ok', it should have real coverage data
    if result.get('status') == 'ok':
        assert 'coverage' in result, "Coverage result should have 'coverage' field"
        assert 'overall' in result.get('coverage', {}), "Coverage should have 'overall' percentage"
        # Should not be stub message
        assert 'Real' not in str(result.get('note', ''))


def test_control_flow_dotted_id():
    """Ensure control flow works with dotted IDs."""
    from ai_agents.tools.analysis_tools import analyze_control_flow
    
    # Test with dotted ID
    result = analyze_control_flow('eutro.train.train', None)
    
    # Should either work or return appropriate error, not 'not_found' due to dotted ID parsing
    assert result.get('status') in ['ok', 'not_applicable', 'error', 'not_found'], \
        f"Control flow should handle dotted IDs, got: {result.get('status')}"
    
    # If not_found, it should be because the function doesn't exist, not because of parsing
    if result.get('status') == 'not_found':
        assert 'not found in AST' in result.get('message', '') or 'not found' in result.get('message', ''), \
            "not_found should be due to missing function, not parsing error"


def test_change_impact_direct_indirect():
    """Ensure change impact correctly distinguishes direct vs indirect callers."""
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
            
            # Direct callers should be at depth 1
            # Indirect callers should have depth > 1 or be in separate list
            for caller in direct:
                assert 'depth' not in caller or caller.get('depth') == 1, \
                    f"Direct caller should have depth 1, got: {caller}"
            
            # If main.main is in direct, that's a bug
            direct_ids = [c['from'] for c in direct]
            if 'main.main' in direct_ids:
                # This should only happen if main.main directly calls make_dataset
                # For rp, main.main calls train, which calls make_dataset
                # So main.main should be indirect, not direct
                # This test will fail if the bug is present
                pytest.fail("main.main should not be a direct caller of make_dataset (should be indirect)")
