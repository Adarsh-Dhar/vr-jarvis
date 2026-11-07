"""Tests for concurrency analysis."""
import pytest
from ai_agents.intelligence.dataflow.concurrency import (
    ConcurrencyAnalyzer,
    ConcurrencyAnalysisResult
)
from ai_agents.intelligence.dataflow.models import DefUseFacts


def test_concurrency_analyzer():
    """Test that concurrency analyzer can be instantiated."""
    analyzer = ConcurrencyAnalyzer()
    assert analyzer is not None


def test_analyze_concurrency():
    """Test that concurrency analysis can be performed."""
    analyzer = ConcurrencyAnalyzer()

    facts = DefUseFacts(
        function_id='test::f',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    result = analyzer.analyze_concurrency([facts])
    assert result is not None
    assert isinstance(result, ConcurrencyAnalysisResult)
