"""Tests for large graph summarization."""
import pytest
from ai_agents.intelligence.dataflow.graph_summarizer import (
    GraphSummarizer,
    GraphSummary,
    StreamedNeighborhood
)


def test_graph_summarizer():
    """Test that graph summarizer can be instantiated."""
    summarizer = GraphSummarizer()
    assert summarizer is not None


def test_summarize_graph():
    """Test that graphs can be summarized."""
    summarizer = GraphSummarizer(max_nodes_per_view=10)

    graph = {
        'function_id': 'test::f',
        'nodes': [
            {'id': 'n1', 'function_id': 'func1'},
            {'id': 'n2', 'function_id': 'func1'},
            {'id': 'n3', 'function_id': 'func2'}
        ],
        'edges': [
            {'id': 'e1', 'source': 'n1', 'target': 'n2'},
            {'id': 'e2', 'source': 'n2', 'target': 'n3'}
        ]
    }

    summary = summarizer.summarize_graph(graph)
    assert summary is not None
    assert isinstance(summary, GraphSummary)
    assert summary.original_node_count == 3


def test_stream_neighborhood():
    """Test that neighborhoods can be streamed."""
    summarizer = GraphSummarizer()

    graph = {
        'nodes': [
            {'id': 'n1'},
            {'id': 'n2'},
            {'id': 'n3'}
        ],
        'edges': [
            {'id': 'e1', 'source': 'n1', 'target': 'n2'},
            {'id': 'e2', 'source': 'n2', 'target': 'n3'}
        ]
    }

    neighborhood = summarizer.stream_neighborhood(graph, 'n1', depth=2)
    assert neighborhood is not None
    assert isinstance(neighborhood, StreamedNeighborhood)
    assert neighborhood.focus_node == 'n1'
