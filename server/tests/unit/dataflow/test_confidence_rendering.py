"""Tests for confidence rendering."""
import pytest
from ai_agents.intelligence.dataflow.confidence_rendering import (
    ConfidenceRenderer,
    EdgeStyle
)


def test_confidence_renderer():
    """Test that confidence renderer can be instantiated."""
    renderer = ConfidenceRenderer()
    assert renderer is not None


def test_get_style():
    """Test that styles can be retrieved."""
    renderer = ConfidenceRenderer()
    style = renderer.get_style('must_reach')
    assert style is not None
    assert style.line_style == 'solid'


def test_render_edges():
    """Test that edges can be styled."""
    renderer = ConfidenceRenderer()

    edges = [
        {'id': 'edge1', 'subkind': 'must_reach'},
        {'id': 'edge2', 'subkind': 'may_reach'}
    ]

    styled = renderer.render_edges(edges)
    assert len(styled) == 2
    assert 'visual_style' in styled[0]
