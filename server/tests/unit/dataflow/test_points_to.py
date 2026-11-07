"""Tests for points-to analysis."""
import pytest
import ast
from ai_agents.intelligence.dataflow.python_extractor import PythonDefUseExtractor
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
from ai_agents.intelligence.dataflow.points_to import PointsToAnalyzer, infer_mutation_from_call


def test_identifies_allocation_sites():
    """Test that allocation sites are identified for literal collections."""
    code = '''
def f():
    a = [1, 2, 3]
    b = {'x': 1}
    c = {1, 2}
    return a
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

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Run points-to analysis
    analyzer = PointsToAnalyzer()
    result = analyzer.analyze(facts, function_id)

    # Verify allocation sites were created
    assert len(result.allocation_sites) >= 3, "Should identify list, dict, and set allocations"

    # Verify allocation kinds
    kinds = {site.kind for site in result.allocation_sites.values()}
    assert 'list' in kinds, "Should have list allocation"
    assert 'dict' in kinds, "Should have dict allocation"
    assert 'set' in kinds, "Should have set allocation"


def test_variable_points_to_allocation():
    """Test that variables are mapped to their allocation sites."""
    code = '''
def f():
    a = [1, 2, 3]
    return a
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

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Run points-to analysis
    analyzer = PointsToAnalyzer()
    result = analyzer.analyze(facts, function_id)

    # Find the binding for 'a'
    a_bindings = [key for key in result.points_to.keys() if 'a' in key]

    assert len(a_bindings) > 0, "Should have points-to info for variable 'a'"
    assert len(result.points_to[a_bindings[0]]) > 0, "Variable 'a' should point to at least one allocation"


def test_detects_mutating_methods():
    """Test that mutating method calls are detected."""
    code = '''
def f():
    a = [1, 2, 3]
    a.append(4)
    return a
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

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Find the append operation
    append_ops = [op for op in facts.operations if op.operation == 'Call' and 'append' in op.expression.lower()]

    assert len(append_ops) > 0, "Should have append operation"

    # Infer mutation
    mutation_info = infer_mutation_from_call(append_ops[0], facts)

    assert mutation_info['is_mutation'] == True, "append should be detected as mutation"


def test_non_mutating_methods():
    """Test that non-mutating methods are not flagged."""
    code = '''
def f():
    a = [1, 2, 3]
    b = a.copy()
    return b
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

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Find the copy operation
    copy_ops = [op for op in facts.operations if op.operation == 'Call' and 'copy' in op.expression.lower()]

    if copy_ops:
        # Infer mutation
        mutation_info = infer_mutation_from_call(copy_ops[0], facts)

        # copy() is not in our mutating methods list
        assert mutation_info['is_mutation'] == False, "copy should not be detected as mutation"


def test_constructor_allocations():
    """Test that constructor calls create allocation sites."""
    code = '''
def f():
    a = list()
    b = dict()
    c = set()
    return a
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

    # Extract DFG facts
    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    # Run points-to analysis
    analyzer = PointsToAnalyzer()
    result = analyzer.analyze(facts, function_id)

    # Verify allocation sites were created for constructors
    assert len(result.allocation_sites) >= 3, "Should identify constructor allocations"

    # Verify allocation kinds
    kinds = {site.kind for site in result.allocation_sites.values()}
    assert 'list' in kinds, "Should have list() allocation"
    assert 'dict' in kinds, "Should have dict() allocation"
    assert 'set' in kinds, "Should have set() allocation"
