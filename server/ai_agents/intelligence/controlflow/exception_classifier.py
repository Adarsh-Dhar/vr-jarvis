"""Exception effect classifier for implicit may_raise detection."""
import ast
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ExceptionEffect:
    """Represents the exception effect of an operation."""
    may_raise: bool
    exception_types: List[str]  # Known possible exception types
    is_unknown: bool  # True if exact exception type is unknown
    source_metadata: Dict[str, Any]


class ExceptionEffectClassifier:
    """Classify AST nodes for potential exception effects."""

    # Operations that may raise exceptions
    MAY_RAISE_OPERATIONS = {
        'Call',           # Function calls can raise
        'Attribute',      # Attribute access can raise AttributeError
        'Subscript',      # Subscript access can raise IndexError/KeyError
        'BinOp',          # Arithmetic can raise (ZeroDivisionError, etc.)
        'Compare',        # Comparisons can raise
        'Await',          # Await can raise
        'Yield',          # Yield can raise
        'YieldFrom',      # Yield from can raise
        'ListComp',       # Comprehensions can raise
        'SetComp',
        'DictComp',
        'GeneratorExp',
    }

    # Operations that are safe (no exceptions expected)
    SAFE_OPERATIONS = {
        'Constant',       # Literals
        'Name',           # Variable references (unless undefined)
        'Load',           # Load context
    }

    def classify(self, node: ast.AST) -> ExceptionEffect:
        """Classify an AST node for exception effects."""
        if node is None:
            return ExceptionEffect(
                may_raise=False,
                exception_types=[],
                is_unknown=False,
                source_metadata={}
            )

        node_type = type(node).__name__

        # Check if this operation type may raise
        if node_type in self.MAY_RAISE_OPERATIONS:
            # Determine specific exception types where possible
            exception_types = self._get_exception_types(node)
            return ExceptionEffect(
                may_raise=True,
                exception_types=exception_types,
                is_unknown=len(exception_types) == 0,
                source_metadata={
                    'node_type': node_type,
                    'line': getattr(node, 'lineno', 0),
                    'col': getattr(node, 'col_offset', 0)
                }
            )

        # Check if this is a safe operation
        if node_type in self.SAFE_OPERATIONS:
            return ExceptionEffect(
                may_raise=False,
                exception_types=[],
                is_unknown=False,
                source_metadata={'node_type': node_type}
            )

        # For unknown operations, be conservative
        return ExceptionEffect(
            may_raise=True,
            exception_types=[],
            is_unknown=True,
            source_metadata={
                'node_type': node_type,
                'line': getattr(node, 'lineno', 0),
                'col': getattr(node, 'col_offset', 0),
                'conservative': True
            }
        )

    def _get_exception_types(self, node: ast.AST) -> List[str]:
        """Get specific exception types for known operations."""
        node_type = type(node).__name__

        if node_type == 'Subscript':
            # Subscript can raise IndexError (list), KeyError (dict), TypeError
            return ['IndexError', 'KeyError', 'TypeError']
        elif node_type == 'Attribute':
            # Attribute access can raise AttributeError
            return ['AttributeError']
        elif node_type == 'BinOp':
            # Arithmetic can raise various exceptions
            op_type = type(node.op).__name__
            if op_type == 'Div':
                return ['ZeroDivisionError']
            elif op_type in ('Mod', 'FloorDiv'):
                return ['ZeroDivisionError']
            else:
                return ['TypeError', 'ValueError']
        elif node_type == 'Compare':
            # Comparisons can raise TypeError
            return ['TypeError']
        elif node_type == 'Call':
            # Calls can raise anything - unknown
            return []
        elif node_type == 'Await':
            # Await can raise anything from the awaited coroutine
            return []
        else:
            # Unknown operation - return empty list (unknown)
            return []

    def should_create_may_raise_edge(self, node: ast.AST) -> bool:
        """Determine if a may_raise edge should be created for this node."""
        effect = self.classify(node)
        return effect.may_raise

    def get_exception_metadata(self, node: ast.AST) -> Dict[str, Any]:
        """Get exception metadata for edge creation."""
        effect = self.classify(node)
        return {
            'may_raise': effect.may_raise,
            'exception_types': effect.exception_types,
            'is_unknown': effect.is_unknown,
            'source_metadata': effect.source_metadata
        }
