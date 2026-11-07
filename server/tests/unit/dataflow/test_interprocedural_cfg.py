"""Tests for interprocedural CFG with call/return edges."""
import pytest
from ai_agents.intelligence.dataflow.interprocedural_cfg import (
    InterproceduralCFGBuilder,
    InterproceduralCFG,
    InterproceduralCFGEdge
)
from ai_agents.intelligence.controlflow.python_cfg import PythonCFGBuilder
import ast


def test_build_interprocedural_cfg():
    """Test that an interprocedural CFG can be built."""
    code1 = '''
def f():
    return 1
'''

    code2 = '''
def g():
    x = f()
    return x
'''

    # Parse and build CFGs
    tree1 = ast.parse(code1)
    tree2 = ast.parse(code2)

    func1 = tree1.body[0]
    func2 = tree2.body[0]

    cfg_builder = PythonCFGBuilder()

    artifact1 = cfg_builder.build_function(
        function_ast=func1,
        function_id='test::f',
        source=code1,
        file_path='test.py'
    )

    artifact2 = cfg_builder.build_function(
        function_ast=func2,
        function_id='test::g',
        source=code2,
        file_path='test.py'
    )

    # Create mock call sites
    from ai_agents.intelligence.dataflow.call_site_connector import CallSite

    call_sites = {
        'test::g': [
            CallSite(
                call_site_id='test_g_callsite_1',
                caller_function_id='test::g',
                callee_function_id='test::f',
                operation_id='test_op_1',
                line=2,
                actual_args=[],
                actual_kwargs={},
                resolution='static_resolved'
            )
        ]
    }

    builder = InterproceduralCFGBuilder()
    inter_cfg = builder.build_interprocedural_cfg(
        {'test::f': artifact1, 'test::g': artifact2},
        call_sites
    )

    assert 'test::f' in inter_cfg.function_cfgs
    assert 'test::g' in inter_cfg.function_cfgs
    assert len(inter_cfg.inter_edges) >= 2  # call and return edges


def test_get_function_cfg():
    """Test that individual function CFGs can be retrieved."""
    builder = InterproceduralCFGBuilder()

    from ai_agents.intelligence.controlflow.models import ControlFlowGraph

    cfg = ControlFlowGraph(
        function_id='test::f',
        file='test.py',
        nodes=[],
        edges=[]
    )

    builder._function_cfgs['test::f'] = cfg

    retrieved = builder.get_function_cfg('test::f')
    assert retrieved is not None
    assert retrieved.function_id == 'test::f'


def test_entry_points():
    """Test that entry points are identified."""
    code = '''
def main():
    pass
'''

    tree = ast.parse(code)
    func = tree.body[0]

    cfg_builder = PythonCFGBuilder()
    artifact = cfg_builder.build_function(
        function_ast=func,
        function_id='test::main',
        source=code,
        file_path='test.py'
    )

    builder = InterproceduralCFGBuilder()
    inter_cfg = builder.build_interprocedural_cfg(
        {'test::main': artifact},
        {}
    )

    assert 'test::main' in inter_cfg.entry_points
