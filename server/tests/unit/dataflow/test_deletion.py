"""Test deletion operations."""

import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_delete_variable():
    """Test variable deletion."""
    source = """
def process():
    x = 10
    del x
    return 0
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should have a deletion definition
    deletion_defs = [d for d in facts.definitions if d.kind == 'deletion']
    assert len(deletion_defs) >= 1


def test_delete_attribute():
    """Test attribute deletion."""
    source = """
def process(obj):
    del obj.attr
    return obj
"""
    tree = ast.parse(source)
    func = tree.body[0]
    
    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py"
    )
    
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )
    
    # Should track the deletion
    assert len(facts.definitions) > 0 or len(facts.operations) > 0


def test_delete_subscript():
    """Test subscript deletion."""
    source = """
def process(items):
    del items[0]
    return items
"""
    tree = ast.parse(source)
    func = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )

    # Should track the deletion
    assert len(facts.definitions) > 0 or len(facts.operations) > 0


def test_deletion_prevents_reaching_definition():
    """Test that deletion prevents reaching definitions from subsequent uses."""
    source = """
def process():
    value = 10
    del value
    return value  # Should not have reaching definition
"""
    tree = ast.parse(source)
    func = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id="test::process",
        source=source,
        file_path="test.py"
    )

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=artifact,
        source=source,
        file_path="test.py"
    )

    from ai_agents.intelligence.dataflow.reaching_definitions import ReachingDefinitionsAnalyzer
    analyzer = ReachingDefinitionsAnalyzer()
    result = analyzer.analyze(artifact.graph, facts)

    # Find the use of 'value' in the return
    value_uses = [u for u in facts.uses if u.variable == 'value']
    assert len(value_uses) >= 1, "Should have use for 'value'"

    # The use should have no reaching definitions because of the deletion
    use = value_uses[0]
    reaching_defs = analyzer.resolve_use(use, result, facts)
    assert len(reaching_defs) == 0, "Deletion should prevent reaching definitions"
