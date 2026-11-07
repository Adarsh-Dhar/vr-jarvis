"""Tests for graph persistence and incremental invalidation."""
import pytest
from ai_agents.intelligence.dataflow.graph_persistence import (
    GraphPersistenceManager,
    GraphCacheEntry
)
from pathlib import Path
import tempfile


def test_graph_persistence_manager():
    """Test that persistence manager can be instantiated."""
    manager = GraphPersistenceManager()
    assert manager is not None


def test_cache_graph():
    """Test that graphs can be cached."""
    manager = GraphPersistenceManager()

    entry = manager.cache_graph(
        'test::f',
        'x = 1',
        {'nodes': [], 'edges': []},
        {'nodes': [], 'edges': []},
        {}
    )

    assert entry is not None
    assert entry.function_id == 'test::f'


def test_invalidate_function():
    """Test that function invalidation works."""
    manager = GraphPersistenceManager()

    entry = manager.cache_graph(
        'test::f',
        'x = 1',
        {'nodes': [], 'edges': []},
        {'nodes': [], 'edges': []},
        {}
    )

    manager.invalidate_function('test::f')
    assert manager.get_cached_graph('test::f') is None


def test_cache_validity_check():
    """Test that cache validity can be checked."""
    manager = GraphPersistenceManager()

    entry = manager.cache_graph(
        'test::f',
        'x = 1',
        {'nodes': [], 'edges': []},
        {'nodes': [], 'edges': []},
        {}
    )

    # Same content should be valid
    is_valid = manager.is_cache_valid(
        'test::f',
        'x = 1',
        {'nodes': [], 'edges': []},
        {'nodes': [], 'edges': []},
        {}
    )
    assert is_valid is True

    # Different content should be invalid
    is_valid = manager.is_cache_valid(
        'test::f',
        'x = 2',  # Changed content
        {'nodes': [], 'edges': []},
        {'nodes': [], 'edges': []},
        {}
    )
    assert is_valid is False
