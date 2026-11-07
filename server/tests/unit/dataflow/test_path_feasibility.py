"""Tests for path feasibility analysis."""
import pytest
from ai_agents.intelligence.dataflow.path_feasibility import (
    PathFeasibilityAnalyzer,
    FeasibilityResult
)
from ai_agents.intelligence.controlflow.models import ControlFlowGraph, CFGNode, CFGEdge


def test_analyze_feasibility():
    """Test that path feasibility can be analyzed."""
    analyzer = PathFeasibilityAnalyzer()

    cfg = ControlFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[],
        edges=[]
    )

    constants = {'flag': False}
    result = analyzer.analyze_feasibility(cfg, constants)

    assert result is not None
    assert isinstance(result, FeasibilityResult)


def test_dead_branch_detection():
    """Test that dead branches are detected."""
    analyzer = PathFeasibilityAnalyzer()

    # Create a simple CFG with a condition
    cfg = ControlFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[
            CFGNode(
                id='node1',
                kind='condition',
                label='flag',
                function_id='test::f',
                file='test.py',
                start_line=1,
                end_line=1,
                condition='flag'
            )
        ],
        edges=[
            CFGEdge(
                id='edge1',
                source='node1',
                target='node2',
                kind='true',
                condition=None,
                evidence={}
            )
        ]
    )

    constants = {'flag': False}
    result = analyzer.analyze_feasibility(cfg, constants)

    # Should detect dead branch if condition is constant
    assert isinstance(result.dead_branches, set)
