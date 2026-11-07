"""Test attribute and subscript mutation relationships."""
import ast
from ai_agents.intelligence.dataflow import PythonDefUseExtractor
from ai_agents.intelligence.controlflow import PythonCFGBuilder


def test_attribute_assignment_with_receiver_use():
    """Test that attribute assignment generates a use for the receiver."""
    source = """
def process(user):
    user.balance = 100
    return user.balance
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

    # Should have a use for 'user' (the receiver)
    user_uses = [u for u in facts.uses if u.variable == 'user']
    assert len(user_uses) >= 1, "Should have at least one use of 'user'"

    # Should have metadata indicating it's an attribute receiver
    receiver_uses = [u for u in user_uses if u.metadata.get('is_attribute_receiver')]
    assert len(receiver_uses) >= 1, "Should have receiver use with metadata"


def test_subscript_assignment_with_collection_use():
    """Test that subscript assignment generates a use for the collection."""
    source = """
def process(items):
    items[0] = 42
    return items[0]
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

    # Should have a use for 'items' (the collection)
    items_uses = [u for u in facts.uses if u.variable == 'items']
    assert len(items_uses) >= 1, "Should have at least one use of 'items'"

    # Should have metadata indicating it's a subscript collection
    collection_uses = [u for u in items_uses if u.metadata.get('is_subscript_collection')]
    assert len(collection_uses) >= 1, "Should have collection use with metadata"


def test_augmented_attribute_assignment():
    """Test that augmented attribute assignment tracks mutation."""
    source = """
def process(counter):
    counter.value += 1
    return counter.value
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

    # Should have attribute definition with mutation metadata
    attr_defs = [d for d in facts.definitions if 'attribute' in d.kind]
    assert len(attr_defs) >= 1, "Should have attribute definition"

    # Check for mutation metadata
    mutation_defs = [d for d in attr_defs if d.metadata.get('is_mutation')]
    assert len(mutation_defs) >= 1, "Attribute definition should have mutation metadata"
