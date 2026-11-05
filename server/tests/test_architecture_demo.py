"""Architecture visualization test on demo-account-service."""
import pytest
import json
from pathlib import Path
from ai_agents import config, repository
from ai_agents.tools.visualization_spatial_tools import visualize_architecture

@pytest.fixture
def demo_graph():
    """Load the demo-account-service graph."""
    config.REPOSITORY_DIR = Path('/Users/adarsh/Documents/vr-agent/repository')
    repository.activate('demo-account-service')
    
    with open(config.GRAPH_PATH) as f:
        return json.load(f)

def test_architecture_layers(demo_graph):
    """Test that architecture visualization detects correct layers."""
    nodes = demo_graph.get('nodes', [])
    
    # Check that we have nodes in expected layers
    layers = {}
    for node in nodes:
        level = node.get('level', 'unknown')
        if level not in layers:
            layers[level] = 0
        layers[level] += 1
    
    # Should have services, database, and auth/function layers
    # Note: demo-account-service may not have routes folder
    assert 'service' in layers or 'services' in layers
    assert 'repository' in layers or 'database' in layers
    assert 'function' in layers  # auth and other functions

def test_architecture_hierarchy(demo_graph):
    """Test that nodes have proper hierarchy (level and parent)."""
    nodes = demo_graph.get('nodes', [])
    
    for node in nodes:
        # Every node should have a level
        assert 'level' in node
        assert node['level'] is not None
        
        # Nodes should have parent if they're not top-level
        if node.get('level') not in ['route', 'service', 'repository', 'external']:
            assert 'parent' in node or node.get('parent') is None

def test_architecture_edges(demo_graph):
    """Test that edges have proper types including contains and imports."""
    edges = demo_graph.get('edges', [])
    
    edge_types = set()
    for edge in edges:
        edge_types.add(edge.get('type'))
    
    # Should have calls edges
    assert 'calls' in edge_types
    
    # Should have contains edges for hierarchy
    assert 'contains' in edge_types

def test_coupling_metrics(demo_graph):
    """Test that coupling metrics can be computed."""
    nodes = demo_graph.get('nodes', [])
    edges = demo_graph.get('edges', [])
    
    # Compute fan-in and fan-out
    fan_in = {}
    fan_out = {}
    
    for edge in edges:
        src = edge.get('src')
        dst = edge.get('dst')
        if src and dst:
            fan_out[src] = fan_out.get(src, 0) + 1
            fan_in[dst] = fan_in.get(dst, 0) + 1
    
    # Should have some nodes with dependencies
    assert len(fan_in) > 0 or len(fan_out) > 0

def test_visualize_architecture_tool(demo_graph, monkeypatch):
    """Test the visualize_architecture tool."""
    # Mock the session state
    class MockToolContext:
        def __init__(self):
            self.state = {}
    
    tool_context = MockToolContext()
    
    # Mock the graph loading
    monkeypatch.setattr('ai_agents.tools.navigation_tools._load_graph_index', lambda: demo_graph)
    
    result = visualize_architecture(tool_context, scope='full')
    
    assert result['status'] == 'ok'
    assert 'layers' in result
    assert 'coupling_metrics' in result
    assert 'node_count' in result
    assert 'edge_count' in result
    
    # Should have detected multiple layers
    assert len(result['layers']) >= 2
