"""Tests for path highlighting and queries."""
import pytest
from ai_agents.intelligence.dataflow.path_queries import (
    PathQueryEngine,
    PathResult
)


def test_path_query_engine():
    """Test that path query engine can be instantiated."""
    engine = PathQueryEngine()
    assert engine is not None


def test_find_shortest_path():
    """Test that shortest path can be found."""
    engine = PathQueryEngine()

    graph = {
        'nodes': {
            'node1': {'id': 'node1'},
            'node2': {'id': 'node2'},
            'node3': {'id': 'node3'}
        },
        'edges': [
            {'id': 'edge1', 'source': 'node1', 'target': 'node2', 'kind': 'next'},
            {'id': 'edge2', 'source': 'node2', 'target': 'node3', 'kind': 'next'}
        ]
    }

    path = engine.find_shortest_path(graph, 'node1', 'node3')
    assert path is not None
    assert path == ['node1', 'node2', 'node3']


def test_find_all_paths():
    """Test that all paths can be found."""
    engine = PathQueryEngine()

    graph = {
        'nodes': {
            'node1': {'id': 'node1'},
            'node2': {'id': 'node2'},
            'node3': {'id': 'node3'}
        },
        'edges': [
            {'id': 'edge1', 'source': 'node1', 'target': 'node2', 'kind': 'next'},
            {'id': 'edge2', 'source': 'node2', 'target': 'node3', 'kind': 'next'}
        ]
    }

    result = engine.find_all_paths(graph, 'node1', 'node3', max_paths=10, max_depth=10)
    assert result is not None
    assert isinstance(result, PathResult)
    assert result.shortest_path is not None