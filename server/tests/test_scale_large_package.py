"""
Scale test on a large Python package.
Tests that indexing produces a real graph: nodes and edges must be present,
not silently empty.
"""

import time
from pathlib import Path

import pytest

from ai_agents import config, repository


@pytest.fixture
def repo_dir():
    """Point REPOSITORY_DIR at the real repository tree for this test only.

    The original test left ``REPOSITORY_DIR`` aimed at ``server/repository``
    (which does not exist) and later tests depend on that state, so restore
    exactly that value afterwards.
    """
    old = config.REPOSITORY_DIR
    broken = Path(__file__).parent.parent / 'repository'
    config.REPOSITORY_DIR = Path(__file__).parent.parent.parent / 'repository'
    try:
        yield config.REPOSITORY_DIR
    finally:
        config.REPOSITORY_DIR = broken


def test_large_package_indexing_performance(repo_dir):
    """The rp repository must index to a non-empty graph within the time budget."""
    start = time.time()
    graph = repository.index_repo('rp')
    elapsed = time.time() - start

    assert elapsed < 15, f"Indexing took {elapsed}s, expected < 15s"

    nodes = graph.get('nodes', [])
    edges = graph.get('edges', [])
    assert len(nodes) > 0, "graph has no nodes - indexing produced an empty graph"
    module_nodes = [n for n in nodes if n.get('level') == 'module']
    file_nodes = [n for n in nodes if n.get('level') == 'file']
    assert module_nodes, "graph has no module nodes"
    assert file_nodes, "graph has no file nodes"

    print(f"Indexed {len(nodes)} nodes, {len(edges)} edges in {elapsed:.2f}s")
    print(f"Modules: {len(module_nodes)}, Files: {len(file_nodes)}")


def test_top_level_view_size_cap(repo_dir):
    """The module overview of a graph stays smaller than the full node set."""
    from graph_view import graph_view

    graph = repository.index_repo('rp')
    nodes = graph.get('nodes', [])
    assert nodes, "graph has no nodes - indexing produced an empty graph"

    # Force the overview path the same way /graph does for large repos.
    out = graph_view(graph, level='module')
    assert out['level'] == 'module'
    assert all(n.get('level') == 'module' for n in out['nodes'])
    assert len(out['nodes']) <= len(nodes)
    assert out['truncated'] == (len(nodes) > len(out['nodes']))
