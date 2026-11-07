"""Constant propagation and type analysis."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Union
from .models import DefUseFacts, Definition


@dataclass
class ConstantValue:
    """A constant value with type information."""
    value: Any
    type: str  # 'int', 'str', 'bool', 'float', 'None', 'unknown'
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TypeLattice:
    """Type lattice for constant propagation."""
    types: Set[str]  # Possible types at a point
    is_constant: bool
    constant_value: Optional[ConstantValue]


class ConstantPropagator:
    """
    Perform constant propagation and type inference.

    Uses a forward lattice over definitions to determine:
    - Which variables have constant values
    - The type of each variable
    - Which branches are dead (constant condition false)
    """

    def __init__(self):
        self._constants: Dict[str, ConstantValue] = {}  # binding_key -> ConstantValue

    def propagate_constants(
        self,
        facts: DefUseFacts
    ) -> Dict[str, ConstantValue]:
        """
        Propagate constant values through the function.

        Returns: binding_key -> ConstantValue
        """
        constants = {}

        for definition in facts.definitions:
            # Try to infer constant value from expression
            if definition.expression:
                constant = self._infer_constant(definition.expression)
                if constant:
                    constants[definition.binding_key] = constant

        self._constants = constants
        return constants

    def _infer_constant(self, expression: str) -> Optional[ConstantValue]:
        """Infer a constant value from an expression."""
        expr = expression.strip()

        # String literals
        if expr.startswith('\'') and expr.endswith('\''):
            return ConstantValue(
                value=expr[1:-1],
                type='str',
                confidence=1.0
            )
        if expr.startswith('"') and expr.endswith('"'):
            return ConstantValue(
                value=expr[1:-1],
                type='str',
                confidence=1.0
            )

        # Integer literals
        if expr.lstrip('-').isdigit():
            return ConstantValue(
                value=int(expr),
                type='int',
                confidence=1.0
            )

        # Float literals
        try:
            float_val = float(expr)
            return ConstantValue(
                value=float_val,
                type='float',
                confidence=1.0
            )
        except ValueError:
            pass

        # Boolean literals
        if expr == 'True':
            return ConstantValue(
                value=True,
                type='bool',
                confidence=1.0
            )
        if expr == 'False':
            return ConstantValue(
                value=False,
                type='bool',
                confidence=1.0
            )
        if expr == 'None':
            return ConstantValue(
                value=None,
                type='None',
                confidence=1.0
            )

        return None

    def infer_type(self, binding_key: str) -> str:
        """Infer the type of a binding."""
        constant = self._constants.get(binding_key)
        if constant:
            return constant.type
        return 'unknown'
