"""Tests for source span annotation."""
import pytest
from ai_agents.intelligence.dataflow.source_spans import (
    SourceSpanAnnotator,
    SourceSpan
)


def test_annotate_spans():
    """Test that source spans can be annotated."""
    annotator = SourceSpanAnnotator()

    nodes = [
        {'id': 'node1', 'start_line': 1},
        {'id': 'node2', 'start_line': 2}
    ]

    source = "line1\nline2\nline3"
    annotated = annotator.annotate_spans(nodes, source)

    assert len(annotated) == 2
    assert annotated[0].span.start_line == 1


def test_calculate_span():
    """Test that spans are calculated correctly."""
    annotator = SourceSpanAnnotator()
    source = "hello world\nfoo bar"

    span = annotator._calculate_span(source, 1)
    assert span.start_line == 1
    assert span.end_line == 1
    assert span.end_col == len("hello world")
