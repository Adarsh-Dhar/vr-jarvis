"""Tests for call site connection with context sensitivity."""
import pytest
from ai_agents.intelligence.dataflow.call_site_connector import (
    CallSiteConnector,
    CallSite,
    InterproceduralEdge
)
from ai_agents.intelligence.dataflow.interprocedural import InterproceduralSummaryBuilder
from ai_agents.intelligence.dataflow.python_extractor import PythonDefUseExtractor
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
import ast


def test_identify_call_sites():
    """Test that call sites are identified."""
    code = '''
def f():
    result = foo()
    return result
'''

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

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    summary_builder = InterproceduralSummaryBuilder()
    connector = CallSiteConnector(summary_builder)

    call_sites = connector.identify_call_sites(facts)

    assert len(call_sites) > 0, "Should identify at least one call site"
    assert call_sites[0].caller_function_id == 'test::f'


def test_call_site_resolution():
    """Test that call site resolution is determined."""
    code = '''
def f():
    x = self.method()
    return x
'''

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

    extractor = PythonDefUseExtractor()
    facts = extractor.extract_function(
        artifact=cfg_artifact,
        source=code,
        file_path='test.py'
    )

    summary_builder = InterproceduralSummaryBuilder()
    connector = CallSiteConnector(summary_builder)

    call_sites = connector.identify_call_sites(facts)

    if call_sites:
        # Self.method should be polymorphic
        assert call_sites[0].resolution in ['polymorphic', 'unresolved']


def test_connect_call_site():
    """Test that a call site can be connected to its callee."""
    from ai_agents.intelligence.dataflow.models import DefUseFacts

    summary_builder = InterproceduralSummaryBuilder()
    connector = CallSiteConnector(summary_builder)

    # Create mock call site
    call_site = CallSite(
        call_site_id='test_callsite_1',
        caller_function_id='test::caller',
        callee_function_id='test::callee',
        operation_id='test_op_1',
        line=1,
        actual_args=['use_1'],
        actual_kwargs={},
        resolution='static_resolved'
    )

    # Create mock caller facts with a Call operation carrying a call_shape
    from ai_agents.intelligence.dataflow.models import (
        DefUseFacts, ExpressionFact)

    caller_facts = DefUseFacts(
        function_id='test::caller',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[
            ExpressionFact(
                id='test_op_1',
                function_id='test::caller',
                file='test.py',
                line=1,
                column=0,
                cfg_node_ids=[],
                expression='callee(1)',
                operation='Call',
                input_use_ids=['use_1'],
                metadata={'call_shape': {
                    'callee': 'callee',
                    'positional': [{'use_ids': ['use_1'],
                                    'operation_id': 'op_arg'}],
                    'keywords': []}},
            )
        ]
    )

    # Create mock callee facts with parameter
    from ai_agents.intelligence.dataflow.models import Definition

    callee_facts = DefUseFacts(
        function_id='test::callee',
        file='test.py',
        definitions=[
            Definition(
                id='test::callee_def_param_1',
                variable='x',
                function_id='test::callee',
                file='test.py',
                line=1,
                column=0,
                kind='parameter',
                cfg_node_ids=[],
                binding_key='test::callee::x'
            )
        ],
        uses=[],
        operations=[]
    )

    callee_tree = ast.parse('def callee(x):\n    return x\n')
    edges = connector.connect_call_site(
        call_site, caller_facts, callee_facts, None,
        callee_func_ast=callee_tree.body[0])

    # Should create an argument edge bound by signature, not position
    assert len(edges) > 0
    assert edges[0].source_kind == 'argument'
    assert edges[0].target_kind == 'parameter'
    assert edges[0].target_id == 'test::callee_def_param_1'
    assert edges[0].resolution == 'confirmed'
    assert edges[0].metadata['param_name'] == 'x'


def test_connect_all_call_sites():
    """Test that all call sites can be connected."""
    from ai_agents.intelligence.dataflow.models import DefUseFacts

    summary_builder = InterproceduralSummaryBuilder()
    connector = CallSiteConnector(summary_builder)

    # Create mock facts
    facts1 = DefUseFacts(
        function_id='test::f1',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    facts2 = DefUseFacts(
        function_id='test::f2',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    summaries = {}
    all_edges = connector.connect_all_call_sites([facts1, facts2], summaries)

    assert 'test::f1' in all_edges
    assert 'test::f2' in all_edges
