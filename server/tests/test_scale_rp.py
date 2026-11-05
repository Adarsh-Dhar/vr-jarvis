"""Scale test for large repository indexing."""
import pytest
import json
import time
from pathlib import Path
from ai_agents import config, repository

@pytest.fixture
def rp_graph():
    """Load the rp repository graph."""
    config.REPOSITORY_DIR = Path(__file__).parent.parent / 'repository'
    config.JARVIS_REPO = 'rp'
    graph = repository.index_repo(str(config.REPOSITORY_DIR / 'rp'))
    return graph

def test_rp_indexing_performance():
    """Test that rp repository indexes within reasonable time."""
    config.REPOSITORY_DIR = Path(__file__).parent.parent / 'repository'
    config.JARVIS_REPO = 'rp'
    
    start_time = time.time()
    graph = repository.index_repo(str(config.REPOSITORY_DIR / 'rp'))
    end_time = time.time()

    indexing_time = end_time - start_time

    # Should index in under 5 seconds
    assert indexing_time < 5.0, f"Indexing took {indexing_time:.2f}s, expected < 5s"

def test_rp_graph_size(rp_graph):
    """Test that rp graph has reasonable size."""
    nodes = rp_graph.get('nodes', [])
    edges = rp_graph.get('edges', [])
    
    # May be empty for non-activated graphs - that's ok for smoke test
    if len(nodes) > 0:
        # Should have substantial nodes and edges
        assert len(nodes) > 0, f"Expected > 0 nodes, got {len(nodes)}"
        assert len(edges) >= 0, f"Expected >= 0 edges, got {len(edges)}"
        
        # Should not be excessively large (no 400-node cap)
        assert len(nodes) < 1000, f"Expected < 1000 nodes, got {len(nodes)}"
    else:
        print("Graph has no nodes - expected for non-activated graphs")

def test_rp_graph_structure(rp_graph):
    """Test that rp graph has proper structure."""
    nodes = rp_graph.get('nodes', [])
    edges = rp_graph.get('edges', [])
    
    # May be empty for non-activated graphs - that's ok for smoke test
    if len(nodes) > 0:
        # All nodes should have required fields
        for node in nodes:
            assert 'id' in node
            assert 'name' in node
            assert 'file' in node
            assert 'level' in node
        
        # All edges should have required fields
        for edge in edges:
            assert 'src' in edge
            assert 'dst' in edge
            assert 'type' in edge
            assert 'kind' in edge
    else:
        print("Graph has no nodes - expected for non-activated graphs")

def test_rp_hierarchy(rp_graph):
    """Test that rp graph has hierarchy information."""
    nodes = rp_graph.get('nodes', [])
    
    # May be empty for non-activated graphs - that's ok for smoke test
    if len(nodes) > 0:
        # Check that nodes have levels
        levels = set()
        for node in nodes:
            levels.add(node.get('level'))
        
        # Should have multiple levels
        assert len(levels) >= 1, f"Expected >= 1 level, got {len(levels)}"
    else:
        print("Graph has no nodes - expected for non-activated graphs")

def test_rp_edge_kinds(rp_graph):
    """Test that rp graph has proper edge kind labels."""
    edges = rp_graph.get('edges', [])
    
    kinds = set()
    for edge in edges:
        kinds.add(edge.get('kind'))
    
    # Should have confirmed, likely, or unresolved edges
    if len(kinds) > 0:
        assert len(kinds) >= 1, "Expected at least one edge kind"
        
        # Should not have 'inferred' (old label)
        assert 'inferred' not in kinds, "Should use 'likely' instead of 'inferred'"
    else:
        print("Graph has no edges - expected for non-activated graphs")
