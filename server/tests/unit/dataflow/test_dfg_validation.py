"""Test DFG validation with comprehensive checks."""
import pytest
import ast
from ai_agents.intelligence.controlflow import PythonCFGBuilder
from ai_agents.intelligence.dataflow import (
    PythonDefUseExtractor,
    ReachingDefinitionsAnalyzer,
    DataFlowGraphBuilder,
)
from ai_agents.intelligence.dataflow.validator import validate_dfg


def test_dfg_node_uniqueness():
    """Test that DFG nodes have unique IDs."""
    code = """
def simple():
    x = 1
    return x
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::simple",
        source=code,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(artifact=artifact, source=code, file_path="test.py")

    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(artifact.graph, facts)

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(artifact.graph, facts, analysis_result)

    validation = validate_dfg(dfg, facts)
    assert validation['valid'], f"DFG validation failed: {validation['errors']}"


def test_dfg_edge_uniqueness():
    """Test that DFG edges have unique IDs."""
    code = """
def with_ops():
    x = 1 + 2
    return x
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::with_ops",
        source=code,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(artifact=artifact, source=code, file_path="test.py")

    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(artifact.graph, facts)

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(artifact.graph, facts, analysis_result)

    validation = validate_dfg(dfg, facts)
    assert validation['valid'], f"DFG validation failed: {validation['errors']}"


def test_dfg_binding_key_consistency():
    """Test that all definitions and uses have valid binding keys."""
    code = """
def bindings():
    x = 1
    y = x
    return y
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::bindings",
        source=code,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(artifact=artifact, source=code, file_path="test.py")

    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(artifact.graph, facts)

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(artifact.graph, facts, analysis_result)

    validation = validate_dfg(dfg, facts)
    assert validation['valid'], f"DFG validation failed: {validation['errors']}"


def test_dfg_operation_references():
    """Test that operations reference valid uses and definitions."""
    code = """
def ops():
    x = 1 + 2
    return x
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::ops",
        source=code,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(artifact=artifact, source=code, file_path="test.py")

    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(artifact.graph, facts)

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(artifact.graph, facts, analysis_result)

    validation = validate_dfg(dfg, facts)
    assert validation['valid'], f"DFG validation failed: {validation['errors']}"


def test_dfg_cfg_node_references():
    """Test that all facts have valid CFG node IDs."""
    code = """
def cfg_refs():
    x = 1
    return x
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::cfg_refs",
        source=code,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(artifact=artifact, source=code, file_path="test.py")

    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(artifact.graph, facts)

    dfg_builder = DataFlowGraphBuilder()
    dfg = dfg_builder.build(artifact.graph, facts, analysis_result)

    validation = validate_dfg(dfg, facts)
    assert validation['valid'], f"DFG validation failed: {validation['errors']}"


# ------------------------------------------------- semantic DFG endpoint rules

def _dfg_result(nodes, edges):
    return {'status': 'ok', 'graph': {'nodes': nodes, 'edges': edges}}


def _confirmed_edge(src='n1', dst='n2', evidence=None):
    return {'source': src, 'target': dst, 'kind': 'flows_to',
            'resolution': 'confirmed',
            'evidence': evidence if evidence is not None else {
                'source_file': 'm.py', 'source_line': 1,
                'target_file': 'm.py', 'target_line': 2}}


def test_dfg_empty_nodes_with_confirmed_edge_rejected():
    from ai_agents.registry.semantic_validators import (
        _dfg_endpoints_have_evidence)
    err = _dfg_endpoints_have_evidence(
        _dfg_result([], [_confirmed_edge()]))
    assert err


def test_dfg_duplicate_node_ids_rejected():
    from ai_agents.registry.semantic_validators import (
        _dfg_endpoints_have_evidence)
    err = _dfg_endpoints_have_evidence(
        _dfg_result([{'id': 'n1'}, {'id': 'n1'}], []))
    assert err


def test_dfg_missing_endpoint_rejected():
    from ai_agents.registry.semantic_validators import (
        _dfg_endpoints_have_evidence)
    err = _dfg_endpoints_have_evidence(
        _dfg_result([{'id': 'n1'}], [_confirmed_edge(dst='ghost')]))
    assert err


def test_dfg_missing_evidence_rejected():
    from ai_agents.registry.semantic_validators import (
        _dfg_endpoints_have_evidence)
    err = _dfg_endpoints_have_evidence(
        _dfg_result([{'id': 'n1'}, {'id': 'n2'}],
                    [_confirmed_edge(evidence={})]))
    assert err


def test_dfg_valid_confirmed_edge_passes():
    from ai_agents.registry.semantic_validators import (
        _dfg_endpoints_have_evidence)
    err = _dfg_endpoints_have_evidence(
        _dfg_result([{'id': 'n1'}, {'id': 'n2'}], [_confirmed_edge()]))
    assert err is None


def test_dfg_possible_edges_not_upgraded():
    from ai_agents.registry.semantic_validators import (
        _dfg_endpoints_have_evidence)
    edge = _confirmed_edge()
    edge['resolution'] = 'possible'
    edge['evidence'] = {}
    err = _dfg_endpoints_have_evidence(
        _dfg_result([{'id': 'n1'}], [edge]))
    assert err is None
