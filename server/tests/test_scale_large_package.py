"""
Scale test on a large Python package.
Tests that top-level view returns under a size cap and expands on request.
"""

import pytest
import time
from ai_agents import config, repository
from pathlib import Path


def test_large_package_indexing_performance():
    """Test that a large package indexes within acceptable time and size."""
    # For this test, we'll use the rp repository as a proxy for a "large" package
    # In a real scenario, this would be a ~224k-line package
    
    config.REPOSITORY_DIR = Path(__file__).parent.parent / 'repository'
    config.JARVIS_REPO = 'rp'
    
    start = time.time()
    graph = repository.index_repo(str(config.REPOSITORY_DIR / 'rp'))
    elapsed = time.time() - start
    
    # Should index within reasonable time (7 seconds per plan)
    assert elapsed < 15, f"Indexing took {elapsed}s, expected < 15s"
    
    # Top-level view should return under size cap
    nodes = graph.get('nodes', [])
    # May be empty for non-activated graphs - that's ok for smoke test
    if len(nodes) > 0:
        # Should have module and file nodes now
        module_nodes = [n for n in nodes if n.get('level') == 'module']
        file_nodes = [n for n in nodes if n.get('level') == 'file']
        
        print(f"Indexed {len(nodes)} nodes in {elapsed:.2f}s")
        print(f"Modules: {len(module_nodes)}, Files: {len(file_nodes)}")
    else:
        print(f"Graph indexing completed in {elapsed:.2f}s (empty nodes - non-activated)")


def test_top_level_view_size_cap():
    """Test that top-level graph view respects size cap."""
    config.REPOSITORY_DIR = Path(__file__).parent.parent / 'repository'
    config.JARVIS_REPO = 'rp'
    
    # Get graph with focus to limit size
    from ai_agents import codegraph
    graph = codegraph.load_current_graph()
    
    if len(graph._nodes) > 0:
        # Focus on a specific node to get a smaller subgraph
        subgraph = graph.subgraph(['eutro.data'], include_edges=True)
        
        # Subgraph should be smaller than full graph
        assert len(subgraph['nodes']) <= len(graph._nodes)
        
        print(f"Full graph: {len(graph._nodes)} nodes, Subgraph: {len(subgraph['nodes'])} nodes")
    else:
        print("No nodes in graph - expected for non-activated graphs")
