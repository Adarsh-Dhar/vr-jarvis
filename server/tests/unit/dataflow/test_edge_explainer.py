"""Tests for edge explanation endpoint."""
import pytest
from ai_agents.intelligence.dataflow.edge_explainer import (
    EdgeExplainer,
    EdgeExplanation
)


def test_edge_explainer():
    """Test that edge explainer can be instantiated."""
    explainer = EdgeExplainer()
    assert explainer is not None


def test_explain_edge():
    """Test that edge explanations can be generated."""
    explainer = EdgeExplainer()

    edge = {
        'id': 'edge1',
        'kind': 'reaches',
        'source': 'source_node',
        'target': 'target_node',
        'subkind': 'must_reach'
    }

    nodes = {
        'source_node': {'label': 'x', 'start_line': 1},
        'target_node': {'label': 'y', 'start_line': 2}
    }

    explanation = explainer.explain_edge('edge1', edge, nodes)

    assert explanation is not None
    assert isinstance(explanation, EdgeExplanation)
    assert explanation.rule == 'reaches'
    assert explanation.confidence == 0.9
