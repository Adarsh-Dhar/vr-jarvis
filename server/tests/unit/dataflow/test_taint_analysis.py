"""Tests for interprocedural taint analysis."""
import pytest
from ai_agents.intelligence.dataflow.taint_analysis import (
    InterproceduralTaintAnalyzer,
    TaintAnalysisResult,
    TaintLabel
)
from ai_agents.intelligence.dataflow.interprocedural import FunctionSummary
from ai_agents.intelligence.dataflow.models import DefUseFacts


def test_taint_analysis_infrastructure():
    """Test that taint analysis infrastructure works."""
    analyzer = InterproceduralTaintAnalyzer()
    assert analyzer is not None
    assert analyzer._registry is not None


def test_identify_sources_and_sinks():
    """Test that sources and sinks are identified."""
    analyzer = InterproceduralTaintAnalyzer()

    # Create mock summaries with sources and sinks
    summary1 = FunctionSummary(
        function_id='test::source_func',
        params=[],
        returns_from=set(),
        mutates=set(),
        raises=set(),
        sources=[{'kind': 'sql', 'line': 1}],
        sinks=[],
        content_hash='hash1',
        callee_hashes={}
    )

    summary2 = FunctionSummary(
        function_id='test::sink_func',
        params=[],
        returns_from=set(),
        mutates=set(),
        raises=set(),
        sources=[],
        sinks=['sql'],
        content_hash='hash2',
        callee_hashes={}
    )

    summaries = {
        'test::source_func': summary1,
        'test::sink_func': summary2
    }

    facts = DefUseFacts(
        function_id='test::dummy',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    result = analyzer.analyze_taint([facts], summaries)

    assert 'test::source_func' in result.sources
    assert 'test::sink_func' in result.sinks
    assert 'sql' in result.sinks['test::sink_func']


def test_sanitizer_detection():
    """Test that sanitizers are recognized."""
    analyzer = InterproceduralTaintAnalyzer()

    # Check known sanitizers
    assert analyzer.is_sanitizer('shlex.quote', 'command')
    assert analyzer.is_sanitizer('html.escape', 'html')


def test_taint_path_creation():
    """Test that taint paths can be created."""
    analyzer = InterproceduralTaintAnalyzer()

    summary1 = FunctionSummary(
        function_id='test::source',
        params=[],
        returns_from=set(),
        mutates=set(),
        raises=set(),
        sources=[{'kind': 'command', 'line': 1}],
        sinks=[],
        content_hash='hash1',
        callee_hashes={}
    )

    summary2 = FunctionSummary(
        function_id='test::sink',
        params=[],
        returns_from=set(),
        mutates=set(),
        raises=set(),
        sources=[],
        sinks=['command'],
        content_hash='hash2',
        callee_hashes={}
    )

    summaries = {
        'test::source': summary1,
        'test::sink': summary2
    }

    facts = DefUseFacts(
        function_id='test::dummy',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    result = analyzer.analyze_taint([facts], summaries)

    # Should create taint analysis result
    assert result is not None
    assert isinstance(result, TaintAnalysisResult)
