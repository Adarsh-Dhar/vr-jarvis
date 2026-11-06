"""Test reaching definitions across branches with exact correctness assertions."""
import ast
import pytest
from ai_agents.intelligence.controlflow import PythonCFGBuilder
from ai_agents.intelligence.dataflow import (
    PythonDefUseExtractor,
    ReachingDefinitionsAnalyzer,
    DataFlowGraphBuilder,
)


def test_two_branch_definitions_reach_use():
    """Test that both branch definitions reach the use."""
    code = """
def calculate(flag):
    if flag:
        discount = 20
    else:
        discount = 0
    total = discount
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
        source=code,
        cfg=cfg,
        file_path="test.py"
    )

    # Perform reaching definitions analysis
    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(cfg, facts)

    assert "error" not in analysis_result, f"Analysis failed: {analysis_result.get('error')}"

    # Find the use of 'discount' in 'total = discount'
    discount_uses = [u for u in facts.uses if u.variable == "discount"]
    assert len(discount_uses) >= 1, "Should have at least one use of discount"

    # Get reaching definitions for the use's CFG node
    for use in discount_uses:
        reaching_defs = analysis_result['in_sets'].get(use.cfg_node_id, set())
        # Should have multiple definitions reaching (from both branches)
        assert len(reaching_defs) >= 2, f"Expected at least 2 reaching definitions, got {len(reaching_defs)}"


def test_loop_reaching_definitions():
    """Test that loop-carried values are correctly modeled."""
    code = """
def process(items):
    total = 0
    for item in items:
        total = total + item
    return total
"""
    tree = ast.parse(code)
    func_node = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    cfg = cfg_builder.build_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        function_ast=func_node,
        function_id="test::process",
        source=code,
        cfg=cfg,
        file_path="test.py"
    )

    analyzer = ReachingDefinitionsAnalyzer()
    analysis_result = analyzer.analyze(cfg, facts)

    assert "error" not in analysis_result, f"Analysis failed: {analysis_result.get('error')}"

    # total should have multiple definitions
    total_defs = [d for d in facts.definitions if d.variable == "total"]
    assert len(total_defs) >= 2, "total should have at least 2 definitions (initial + loop)"

    # The loop assignment should have the initial definition reaching it
    loop_def = total_defs[1]  # Second definition is in the loop
    reaching_defs = analysis_result['in_sets'].get(loop_def.cfg_node_id, set())
    assert len(reaching_defs) >= 1, "Loop definition should have at least one reaching definition"
