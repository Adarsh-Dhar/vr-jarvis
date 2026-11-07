"""Tests for unified CFG and DFG view."""
import pytest
from ai_agents.intelligence.dataflow.unified_graph import (
    UnifiedGraphBuilder,
    UnifiedGraph
)
from ai_agents.intelligence.controlflow.models import ControlFlowGraph, CFGNode, CFGEdge
from ai_agents.intelligence.dataflow.models import DataFlowGraph, DataFlowNode, DataFlowEdge


def test_build_unified_graph():
    """Test that a unified graph can be built."""
    builder = UnifiedGraphBuilder()

    cfg = ControlFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[
            CFGNode(
                id='node1',
                kind='entry',
                label='entry',
                function_id='test::f',
                file='test.py',
                start_line=1,
                end_line=1
            )
        ],
        edges=[]
    )

    dfg = DataFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[
            DataFlowNode(
                id='dfg_node1',
                kind='definition',
                variable='x',
                function_id='test::f',
                file='test.py',
                line=1,
                column=0
            )
        ],
        edges=[]
    )

    unified = builder.build_unified(cfg, dfg)

    assert unified is not None
    assert isinstance(unified, UnifiedGraph)
    assert len(unified.nodes) == 2
    assert unified.function_id == 'test::f'


def test_edge_kind_translation():
    """Test that edge kinds are correctly translated."""
    builder = UnifiedGraphBuilder()

    cfg = ControlFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[
            CFGNode(
                id='node1',
                kind='entry',
                label='entry',
                function_id='test::f',
                file='test.py',
                start_line=1,
                end_line=1
            ),
            CFGNode(
                id='node2',
                kind='exit',
                label='exit',
                function_id='test::f',
                file='test.py',
                start_line=2,
                end_line=2
            )
        ],
        edges=[
            CFGEdge(
                id='edge1',
                source='node1',
                target='node2',
                kind='next',
                condition=None,
                evidence={}
            )
        ]
    )

    dfg = DataFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[],
        edges=[]
    )

    unified = builder.build_unified(cfg, dfg)

    # Should have the CFG edge
    assert len(unified.edges) == 1
    assert unified.edges[0].kind == 'next'
