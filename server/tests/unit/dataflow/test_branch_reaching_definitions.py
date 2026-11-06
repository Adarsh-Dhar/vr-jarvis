"""Test reaching definitions across branches."""
import ast
import pytest
from ai_agents.intelligence.dataflow import (
    PythonDefUseExtractor,
    ReachingDefinitionsAnalyzer,
    DataFlowGraphBuilder,
)
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_branch_reaching_definitions():
    """Test that reaching definitions handle branches correctly."""
    code = """
def calculate(price, discount_enabled):
    if discount_enabled:
        discount = 20
    else:
        discount = 0
    total = price - discount
    return total
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    # Build CFG
    cfg_builder = PythonCFGBuilder()
    cfg = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::calculate",
        source=code,
        file_path="test.py"
    )

    # Extract definition/use facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        function_ast=func_node,
        function_id="test::calculate",
        source=code
    )

    # Perform reaching definitions analysis
    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(cfg, facts)

    # Check that discount has multiple definitions
    discount_defs = [d for d in facts.definitions if d.variable == 'discount']
    assert len(discount_defs) >= 2, "discount should have at least 2 definitions (one per branch)"

    # Check that reaching definitions are computed
    assert 'in_sets' in analysis_result, "Should have in_sets"
    assert 'out_sets' in analysis_result, "Should have out_sets"


def test_loop_reaching_definitions():
    """Test that reaching definitions handle loops correctly."""
    code = """
def process(items):
    total = 0
    for item in items:
        total = total + item
    return total
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    # Build CFG
    cfg_builder = PythonCFGBuilder()
    cfg = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )

    # Extract definition/use facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        function_ast=func_node,
        function_id="test::process",
        source=code
    )

    # Perform reaching definitions analysis
    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(cfg, facts)

    # total should have multiple definitions (initial + loop body)
    total_defs = [d for d in facts.definitions if d.variable == 'total']
    assert len(total_defs) >= 2, "total should have at least 2 definitions"

    # Check that analysis completed
    assert 'in_sets' in analysis_result, "Should have in_sets"
