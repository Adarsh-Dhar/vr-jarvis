"""Tests for cross-tool agreement and graph index consistency."""
import pytest
import json
from pathlib import Path
from ai_agents.tools.navigation_tools import resolve_symbol, resolve_symbol_by_name, _load_graph_index
from ai_agents.tools.relationship_intelligence_tools import build_call_graph, find_callers, find_callees

@pytest.fixture
def graph_index():
    """Load the golden graph fixture."""
    fixture_path = Path(__file__).parent / 'fixtures' / 'golden_graph.json'
    with open(fixture_path) as f:
        return json.load(f)

def test_resolve_symbol_by_id(graph_index, monkeypatch):
    """Test that resolve_symbol finds nodes by ID."""
    # Mock the graph loading
    monkeypatch.setattr('ai_agents.tools.navigation_tools._load_graph_index', lambda: graph_index)
    
    node = resolve_symbol('routes.account.createOrder')
    assert node is not None
    assert node['name'] == 'createOrder'
    assert node['file'] == 'routes/account.ts'

def test_resolve_symbol_by_name(graph_index, monkeypatch):
    """Test that resolve_symbol_by_name finds nodes by name."""
    monkeypatch.setattr('ai_agents.tools.navigation_tools._load_graph_index', lambda: graph_index)
    
    nodes = resolve_symbol_by_name('createOrder')
    assert len(nodes) == 2  # Should find both createOrder functions
    names = {n['id'] for n in nodes}
    assert 'routes.account.createOrder' in names
    assert 'services.order.createOrder' in names

def test_build_call_graph_whole_repo(graph_index, monkeypatch):
    """Test build_call_graph with whole repository scope."""
    monkeypatch.setattr('ai_agents.tools.navigation_tools._load_graph_index', lambda: graph_index)
    
    result = build_call_graph('.', None)
    assert result['status'] == 'ok'
    assert result['node_count'] == 4
    assert result['edge_count'] == 3
    
    # Verify all nodes are present
    node_ids = {n['id'] for n in result['call_graph']['nodes']}
    assert 'routes.account.createOrder' in node_ids
    assert 'services.order.createOrder' in node_ids
    assert 'db.orders.insert' in node_ids
    assert 'auth.requireAuth' in node_ids

def test_build_call_graph_by_folder(graph_index, monkeypatch):
    """Test build_call_graph with folder scope."""
    monkeypatch.setattr('ai_agents.tools.navigation_tools._load_graph_index', lambda: graph_index)
    
    result = build_call_graph('routes', None)
    assert result['status'] == 'ok'
    # Should include the routes node and its direct connections
    assert result['node_count'] >= 1  # At least the routes node
    assert result['edge_count'] >= 2  # Edges from this node to services and auth
    
    # Verify the routes node is present
    node_ids = {n['id'] for n in result['call_graph']['nodes']}
    assert 'routes.account.createOrder' in node_ids

def test_find_callers(graph_index, monkeypatch):
    """Test find_callers returns correct callers."""
    monkeypatch.setattr('ai_agents.tools.navigation_tools._load_graph_index', lambda: graph_index)
    
    result = find_callers('services.order.createOrder', None)
    assert result['status'] == 'ok'
    assert len(result['callers']) == 1
    assert result['callers'][0]['from'] == 'routes.account.createOrder'

def test_find_callees(graph_index, monkeypatch):
    """Test find_callees returns correct callees."""
    monkeypatch.setattr('ai_agents.tools.navigation_tools._load_graph_index', lambda: graph_index)
    
    result = find_callees('routes.account.createOrder', None)
    assert result['status'] == 'ok'
    assert len(result['outgoing_calls']) == 2
    callees = {c['to'] for c in result['outgoing_calls']}
    assert 'services.order.createOrder' in callees
    assert 'auth.requireAuth' in callees

def test_cross_tool_agreement(graph_index, monkeypatch):
    """Test that different tools return consistent results for the same node."""
    monkeypatch.setattr('ai_agents.tools.navigation_tools._load_graph_index', lambda: graph_index)
    
    # Get callers using find_callers
    callers_result = find_callers('services.order.createOrder', None)
    
    # Get call hierarchy using get_call_hierarchy
    from ai_agents.tools.navigation_tools import get_call_hierarchy
    hierarchy_result = get_call_hierarchy('services.order.createOrder', None, direction='incoming')
    
    # Both should return the same callers
    assert callers_result['status'] == 'ok'
    assert hierarchy_result['status'] == 'ok'
    
    callers_from_find = {c['from'] for c in callers_result['callers']}
    callers_from_hierarchy = {c['from'] for c in hierarchy_result['incoming_calls']}
    
    assert callers_from_find == callers_from_hierarchy
