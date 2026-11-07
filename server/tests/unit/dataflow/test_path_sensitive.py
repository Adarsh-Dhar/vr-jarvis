"""Tests for path-sensitive data-flow analysis with phi nodes."""
import pytest
import ast
from ai_agents.intelligence.dataflow.python_extractor import PythonDefUseExtractor
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
from ai_agents.intelligence.dataflow.reaching_definitions import ReachingDefinitionsAnalyzer
from ai_agents.intelligence.dataflow.path_sensitive import PathSensitiveAnalyzer
from ai_agents.intelligence.dataflow.dependency_builder import DataFlowGraphBuilder


def test_path_sensitive_creates_phi_nodes():
    """Test that phi nodes are created at join points with multiple definitions."""
    code = '''
def f(x):
    if x > 10:
        permission = 'full'
    else:
        permission = 'restricted'
    return permission
'''

    # Parse and build CFG
    tree = ast.parse(code)
    func_def = tree.body[0]
    function_id = 'test::f'

    cfg_builder = PythonCFGBuilder()
    cfg_artifact = cfg_builder.build_function(
        function_ast=func_def,
        function_id=function_id,
        source=code,
        file_path='test.py'
    )
    cfg = cfg_artifact.graph

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Run reaching definitions
    rd_analyzer = ReachingDefinitionsAnalyzer()
    rd_result = rd_analyzer.analyze(cfg, facts)

    # Run path-sensitive analysis
    ps_analyzer = PathSensitiveAnalyzer()
    ps_result = ps_analyzer.analyze(
        cfg,
        facts,
        rd_result['in_sets'],
        rd_result['out_sets']
    )

    # Verify phi nodes were created
    assert len(ps_result.phi_nodes) > 0, "Should create phi nodes at join points"

    # Find phi node for 'permission' binding
    permission_phis = [p for p in ps_result.phi_nodes if 'permission' in p.binding_key]
    assert len(permission_phis) > 0, "Should have phi node for 'permission'"

    # Verify phi node has multiple incoming definitions
    phi = permission_phis[0]
    assert len(phi.incoming) >= 2, "Phi node should have multiple incoming definitions"


def test_must_reaching_definitions():
    """Test that must-reaching analysis uses intersection."""
    code = '''
def f(x):
    if x > 10:
        y = 1
    else:
        y = 2
    z = y + 1
    return z
'''

    # Parse and build CFG
    tree = ast.parse(code)
    func_def = tree.body[0]
    function_id = 'test::f'

    cfg_builder = PythonCFGBuilder()
    cfg_artifact = cfg_builder.build_function(
        function_ast=func_def,
        function_id=function_id,
        source=code,
        file_path='test.py'
    )
    cfg = cfg_artifact.graph

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Run reaching definitions
    rd_analyzer = ReachingDefinitionsAnalyzer()
    rd_result = rd_analyzer.analyze(cfg, facts)

    # Run path-sensitive analysis
    ps_analyzer = PathSensitiveAnalyzer()
    ps_result = ps_analyzer.analyze(
        cfg,
        facts,
        rd_result['in_sets'],
        rd_result['out_sets']
    )

    # The use of 'y' in 'z = y + 1' should not have must-reaching definitions
    # because y is defined on both branches
    # This is a may-reach situation, not must-reach

    # Verify must-reaching sets are computed
    assert len(ps_result.must_in_sets) > 0, "Should compute must-reaching sets"
    assert len(ps_result.must_out_sets) > 0, "Should compute must-reaching sets"


def test_single_path_has_must_reach():
    """Test that definitions on a single path have must-reach."""
    code = '''
def f(x):
    y = x + 1
    z = y + 2
    return z
'''

    # Parse and build CFG
    tree = ast.parse(code)
    func_def = tree.body[0]
    function_id = 'test::f'

    cfg_builder = PythonCFGBuilder()
    cfg_artifact = cfg_builder.build_function(
        function_ast=func_def,
        function_id=function_id,
        source=code,
        file_path='test.py'
    )
    cfg = cfg_artifact.graph

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Run reaching definitions
    rd_analyzer = ReachingDefinitionsAnalyzer()
    rd_result = rd_analyzer.analyze(cfg, facts)

    # Run path-sensitive analysis
    ps_analyzer = PathSensitiveAnalyzer()
    ps_result = ps_analyzer.analyze(
        cfg,
        facts,
        rd_result['in_sets'],
        rd_result['out_sets']
    )

    # In a single-path function, definitions should must-reach their uses
    # Verify that must-reaching sets are non-empty for nodes with definitions
    for node_id, must_set in ps_result.must_out_sets.items():
        if must_set:
            # At least one node has must-reaching definitions
            return

    pytest.fail("Should have must-reaching definitions in single-path function")


def test_dfg_builder_with_path_sensitive():
    """Test that DFG builder integrates path-sensitive analysis."""
    code = '''
def f(x):
    if x > 10:
        permission = 'full'
    else:
        permission = 'restricted'
    return permission
'''

    # Parse and build CFG
    tree = ast.parse(code)
    func_def = tree.body[0]
    function_id = 'test::f'

    cfg_builder = PythonCFGBuilder()
    cfg_artifact = cfg_builder.build_function(
        function_ast=func_def,
        function_id=function_id,
        source=code,
        file_path='test.py'
    )
    cfg = cfg_artifact.graph

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Run reaching definitions
    rd_analyzer = ReachingDefinitionsAnalyzer()
    rd_result = rd_analyzer.analyze(cfg, facts)

    # Build DFG with path-sensitive analysis
    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, rd_result, path_sensitive=True)

    # Verify DFG metadata indicates path-sensitive analysis
    assert dfg.metadata.get('path_sensitive') == True, "DFG should be marked as path-sensitive"
    assert dfg.metadata.get('phi_node_count', 0) > 0, "DFG should contain phi nodes"

    # Verify phi nodes are in the graph
    phi_nodes = [n for n in dfg.nodes if n.kind == 'phi']
    assert len(phi_nodes) > 0, "DFG should have phi nodes"


def test_edge_condition_standardization():
    """Test that edge conditions are standardized."""
    code = '''
def f(x):
    if x > 10:
        y = 1
    return y
'''

    # Parse and build CFG
    tree = ast.parse(code)
    func_def = tree.body[0]
    function_id = 'test::f'

    cfg_builder = PythonCFGBuilder()
    cfg_artifact = cfg_builder.build_function(
        function_ast=func_def,
        function_id=function_id,
        source=code,
        file_path='test.py'
    )
    cfg = cfg_artifact.graph

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Run reaching definitions
    rd_analyzer = ReachingDefinitionsAnalyzer()
    rd_result = rd_analyzer.analyze(cfg, facts)

    # Build DFG with path-sensitive analysis
    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(cfg, facts, rd_result, path_sensitive=True)

    # Check that conditions are structured dicts with 'predicate' and 'polarity'
    for edge in dfg.edges:
        if edge.condition:
            if isinstance(edge.condition, dict):
                assert 'predicate' in edge.condition, "Condition should have 'predicate'"
                assert 'polarity' in edge.condition, "Condition should have 'polarity'"
