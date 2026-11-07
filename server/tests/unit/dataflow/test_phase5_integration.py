"""End-to-end integration tests for Phase 5 VR integration."""
import pytest
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
from ai_agents.intelligence.controlflow.graph_builder import cfg_to_unity_format
from ai_agents.intelligence.dataflow.python_extractor import PythonDefUseExtractor
from ai_agents.intelligence.dataflow.dependency_builder import dfg_to_unity_format
from ai_agents.intelligence.dataflow.unified_graph import UnifiedGraphBuilder
from ai_agents.intelligence.dataflow.confidence_rendering import ConfidenceRenderer
from ai_agents.intelligence.dataflow.source_spans import SourceSpanAnnotator
from ai_agents.intelligence.dataflow.edge_explainer import EdgeExplainer
from ai_agents.intelligence.dataflow.path_queries import PathQueryEngine
from ai_agents.intelligence.dataflow.graph_persistence import GraphPersistenceManager
from ai_agents.intelligence.dataflow.graph_summarizer import GraphSummarizer


def test_confidence_rendering_integration():
    """Test that confidence rendering is applied to Unity graphs."""
    source = """
def f(x):
    if x > 0:
        return x + 1
    else:
        return x - 1
"""
    builder = PythonCFGBuilder()
    import ast
    tree = ast.parse(source)
    func_node = tree.body[0]

    artifact = builder.build_function(
        function_ast=func_node,
        function_id='test::f',
        source=source,
        file_path='test.py'
    )

    unity_graph = cfg_to_unity_format(artifact.graph)

    # Check that edges have visual_style
    assert len(unity_graph['edges']) > 0
    for edge in unity_graph['edges']:
        assert 'visual_style' in edge
        assert 'line_style' in edge['visual_style']
        assert 'line_width' in edge['visual_style']
        assert 'color' in edge['visual_style']

    # Check that source spans are present
    for node in unity_graph['nodes']:
        assert 'start_line' in node
        assert 'start_col' in node
        assert 'end_line' in node
        assert 'end_col' in node


def test_dfg_confidence_rendering():
    """Test that DFG edges have confidence rendering."""
    # Create a simple DFG for testing
    from ai_agents.intelligence.dataflow.models import DataFlowGraph, DataFlowNode, DataFlowEdge

    dfg = DataFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[
            DataFlowNode(id='n1', kind='definition', function_id='test::f', file='test.py', line=1, variable='x'),
            DataFlowNode(id='n2', kind='use', function_id='test::f', file='test.py', line=2, variable='x')
        ],
        edges=[
            DataFlowEdge(id='e1', source='n1', target='n2', kind='reaches', resolution='must')
        ]
    )

    unity_graph = dfg_to_unity_format(dfg)

    # Check that edges have visual_style
    assert len(unity_graph['edges']) > 0
    for edge in unity_graph['edges']:
        assert 'visual_style' in edge
        assert 'subkind' in edge  # Confidence level


def test_unified_graph_builder():
    """Test that unified graph combines CFG and DFG."""
    # Create simple CFG and DFG for testing
    from ai_agents.intelligence.controlflow.models import ControlFlowGraph, CFGNode, CFGEdge
    from ai_agents.intelligence.dataflow.models import DataFlowGraph, DataFlowNode, DataFlowEdge

    cfg = ControlFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[
            CFGNode(id='cfg1', kind='entry', label='entry', function_id='test::f', file='test.py', start_line=1, end_line=1)
        ],
        edges=[
            CFGEdge(id='ce1', source='cfg1', target='cfg1', kind='next')
        ]
    )

    dfg = DataFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[
            DataFlowNode(id='dfg1', kind='definition', function_id='test::f', file='test.py', line=1, variable='x')
        ],
        edges=[
            DataFlowEdge(id='de1', source='dfg1', target='dfg1', kind='reaches', resolution='must')
        ]
    )

    unified_builder = UnifiedGraphBuilder()
    unified_graph = unified_builder.build_unified(
        cfg,
        dfg
    )

    assert unified_graph is not None
    assert len(unified_graph.nodes) > 0
    assert len(unified_graph.edges) > 0


def test_edge_explainer():
    """Test that edge explainer generates explanations."""
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
    assert explanation.rule == 'reaches'
    assert explanation.confidence == 0.9
    assert explanation.explanation is not None
    assert 'start_line' in explanation.source_span


def test_path_query_engine():
    """Test that path queries work on graphs."""
    engine = PathQueryEngine()

    graph = {
        'nodes': {
            'node1': {'id': 'node1'},
            'node2': {'id': 'node2'},
            'node3': {'id': 'node3'}
        },
        'edges': [
            {'id': 'edge1', 'source': 'node1', 'target': 'node2', 'kind': 'next'},
            {'id': 'edge2', 'source': 'node2', 'target': 'node3', 'kind': 'next'}
        ]
    }

    path = engine.find_shortest_path(graph, 'node1', 'node3')
    assert path is not None
    assert path == ['node1', 'node2', 'node3']

    highlight = engine.highlight_path(graph, path)
    assert 'highlighted_nodes' in highlight
    assert 'highlighted_edges' in highlight


def test_graph_persistence():
    """Test that graph persistence works."""
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

    # Test cache validity
    is_valid = manager.is_cache_valid(
        'test::f',
        'x = 1',
        {'nodes': [], 'edges': []},
        {'nodes': [], 'edges': []},
        {}
    )
    assert is_valid is True

    # Test invalidation
    manager.invalidate_function('test::f')
    assert manager.get_cached_graph('test::f') is None


def test_graph_summarizer():
    """Test that graph summarization works."""
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
    assert summary.original_node_count == 3
    assert len(summary.summarized_nodes) <= 10


def test_end_to_end_pipeline():
    """Test the full pipeline from source to Unity graph."""
    # Build CFG
    builder = PythonCFGBuilder()
    source = """
def f(x):
    if x > 0:
        y = x + 1
        return y
    else:
        return x - 1
"""
    import ast
    tree = ast.parse(source)
    func_node = tree.body[0]

    cfg_artifact = builder.build_function(
        function_ast=func_node,
        function_id='test::f',
        source=source,
        file_path='test.py'
    )

    # Convert to Unity format
    cfg_unity = cfg_to_unity_format(cfg_artifact.graph)

    # Create simple DFG for testing
    from ai_agents.intelligence.dataflow.models import DataFlowGraph, DataFlowNode, DataFlowEdge
    dfg = DataFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[
            DataFlowNode(id='n1', kind='definition', function_id='test::f', file='test.py', line=1, variable='x'),
            DataFlowNode(id='n2', kind='use', function_id='test::f', file='test.py', line=2, variable='x')
        ],
        edges=[
            DataFlowEdge(id='e1', source='n1', target='n2', kind='reaches', resolution='must')
        ]
    )

    dfg_unity = dfg_to_unity_format(dfg)

    # Build unified graph
    unified_builder = UnifiedGraphBuilder()
    unified_graph = unified_builder.build_unified(
        cfg_artifact.graph,
        dfg
    )

    # Verify all components
    assert len(cfg_unity['nodes']) > 0
    assert len(cfg_unity['edges']) > 0
    assert len(dfg_unity['nodes']) > 0
    assert len(dfg_unity['edges']) > 0
    assert len(unified_graph.nodes) > 0

    # Verify confidence rendering
    for edge in cfg_unity['edges']:
        assert 'visual_style' in edge
    for edge in dfg_unity['edges']:
        assert 'visual_style' in edge

    # Verify source spans
    for node in cfg_unity['nodes']:
        assert 'start_line' in node
        assert 'start_col' in node
    for node in dfg_unity['nodes']:
        assert 'start_line' in node
        assert 'start_col' in node
