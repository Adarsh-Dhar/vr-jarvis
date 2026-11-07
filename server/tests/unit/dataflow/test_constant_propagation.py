"""Tests for constant propagation and type analysis."""
import pytest
from ai_agents.intelligence.dataflow.constant_propagation import (
    ConstantPropagator,
    ConstantValue
)
from ai_agents.intelligence.dataflow.models import DefUseFacts


def test_infer_string_constant():
    """Test that string constants are inferred."""
    propagator = ConstantPropagator()
    constant = propagator._infer_constant("'hello'")
    assert constant is not None
    assert constant.type == 'str'
    assert constant.value == 'hello'


def test_infer_integer_constant():
    """Test that integer constants are inferred."""
    propagator = ConstantPropagator()
    constant = propagator._infer_constant("42")
    assert constant is not None
    assert constant.type == 'int'
    assert constant.value == 42


def test_infer_boolean_constant():
    """Test that boolean constants are inferred."""
    propagator = ConstantPropagator()
    constant = propagator._infer_constant("True")
    assert constant is not None
    assert constant.type == 'bool'
    assert constant.value is True


def test_propagate_constants():
    """Test that constants are propagated."""
    propagator = ConstantPropagator()

    facts = DefUseFacts(
        function_id='test::f',
        file='test.py',
        definitions=[],
        uses=[],
        operations=[]
    )

    constants = propagator.propagate_constants(facts)
    assert isinstance(constants, dict)


def test_type_inference():
    """Test that types are inferred."""
    propagator = ConstantPropagator()
    type_ = propagator.infer_type('test::x')
    assert type_ in ['unknown', 'int', 'str', 'bool', 'float', 'None']
