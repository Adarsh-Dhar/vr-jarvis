"""Exception-type propagation for data-flow analysis."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
import ast
from .models import DefUseFacts, ExpressionFact
from .summaries import SummaryRegistry


@dataclass(frozen=True, eq=True)
class ExceptionTypeInfo:
    """Information about an exception type that may be raised."""
    exception_type: str  # e.g., 'ValueError', 'KeyError'
    confidence: float  # 0.0 to 1.0
    source_kind: str  # 'raise_statement', 'call_summary', 'implicit'
    cfg_node_id: str
    line: int
    metadata: tuple = field(default_factory=tuple)  # Use tuple for hashability


@dataclass
class ExceptionPropagationResult:
    """Result of exception-type propagation analysis."""
    exception_types: Dict[str, Set[ExceptionTypeInfo]]  # function_id -> set of exception types
    handler_types: Dict[str, Dict[str, List[str]]]  # handler_id -> {exception_type: matching_types}
    diagnostics: List[Dict[str, Any]]


class ExceptionPropagator:
    """
    Propagate exception types through the call graph.

    Computes which exception types each function may raise, based on:
    - Explicit raise statements
    - Call summaries (library functions)
    - Implicit exceptions (attribute access, indexing, etc.)
    """

    def __init__(self, summary_registry: Optional[SummaryRegistry] = None):
        self._registry = summary_registry or SummaryRegistry()

    def propagate(
        self,
        facts: DefUseFacts,
        function_id: str
    ) -> ExceptionPropagationResult:
        """
        Propagate exception types for a function.

        Returns the set of exception types that may be raised.
        """
        exception_types: Set[ExceptionTypeInfo] = set()
        handler_types: Dict[str, List[str]] = {}
        diagnostics = []

        # Step 1: Collect explicit raise statements
        for operation in facts.operations:
            if operation.operation == 'Raise':
                exc_types = self._extract_exception_types_from_raise(operation)
                for exc_type in exc_types:
                    exception_types.add(ExceptionTypeInfo(
                        exception_type=exc_type,
                        confidence=1.0,
                        source_kind='raise_statement',
                        cfg_node_id=operation.cfg_node_ids[0] if operation.cfg_node_ids else 'unknown',
                        line=operation.line,
                        metadata=tuple(sorted({'operation_id': operation.id}.items()))
                    ))

        # Step 2: Add exceptions from call summaries
        for operation in facts.operations:
            if operation.operation == 'Call':
                from .summaries import infer_call_summary
                summary = infer_call_summary(operation, facts, self._registry)

                for exc_type in summary.raises:
                    exception_types.add(ExceptionTypeInfo(
                        exception_type=exc_type,
                        confidence=0.8,
                        source_kind='call_summary',
                        cfg_node_id=operation.cfg_node_ids[0] if operation.cfg_node_ids else 'unknown',
                        line=operation.line,
                        metadata=tuple(sorted({
                            'operation_id': operation.id,
                            'qualified_name': summary.qualified_name
                        }.items()))
                    ))

        # Step 3: Add implicit exceptions from operations
        for operation in facts.operations:
            implicit_exceptions = self._get_implicit_exceptions(operation)
            for exc_type in implicit_exceptions:
                exception_types.add(ExceptionTypeInfo(
                    exception_type=exc_type,
                    confidence=0.5,
                    source_kind='implicit',
                    cfg_node_id=operation.cfg_node_ids[0] if operation.cfg_node_ids else 'unknown',
                    line=operation.line,
                    metadata=tuple(sorted({
                        'operation_id': operation.id,
                        'operation': operation.operation
                    }.items()))
                ))

        # Step 4: Match handlers to exception types
        # This would require parsing the CFG to find except clauses
        # For now, we'll store the handler types from the CFG metadata

        return ExceptionPropagationResult(
            exception_types={function_id: exception_types},
            handler_types=handler_types,
            diagnostics=diagnostics
        )

    def _extract_exception_types_from_raise(self, operation: ExpressionFact) -> List[str]:
        """Extract exception types from a raise statement."""
        exc_types = []

        expr = operation.expression

        # Try to parse the exception type from the expression
        # This is simplified - a full implementation would parse the AST
        if 'raise ' in expr.lower():
            # Extract what's being raised
            parts = expr.split('raise', 1)[1].strip()
            if '(' in parts:
                # Constructor call: ValueError(...)
                exc_type = parts.split('(')[0].strip()
                if exc_type:
                    exc_types.append(exc_type)
            else:
                # Direct instantiation or re-raise
                exc_type = parts.split('(')[0].strip() if '(' in parts else parts.strip()
                if exc_type and exc_type not in ['None', '']:
                    exc_types.append(exc_type)

        return exc_types

    def _get_implicit_exceptions(self, operation: ExpressionFact) -> List[str]:
        """Get implicit exceptions that may be raised by an operation."""
        implicit_exceptions = []

        # Attribute access may raise AttributeError
        if operation.operation == 'Attribute':
            implicit_exceptions.append('AttributeError')

        # Subscript may raise IndexError, KeyError
        if operation.operation == 'Subscript':
            implicit_exceptions.append('IndexError')
            implicit_exceptions.append('KeyError')

        # Call may raise TypeError (wrong arguments)
        if operation.operation == 'Call':
            implicit_exceptions.append('TypeError')

        # Division may raise ZeroDivisionError
        if operation.expression and '/' in operation.expression:
            implicit_exceptions.append('ZeroDivisionError')

        return implicit_exceptions

    def match_handler_to_exceptions(
        self,
        handler_exception_types: List[str],
        raised_exceptions: Set[ExceptionTypeInfo]
    ) -> Dict[str, List[str]]:
        """
        Match exception handlers to raised exception types.

        Uses Python's exception hierarchy (MRO) to determine matches.
        """
        matches = {}

        # Simplified exception hierarchy
        exception_hierarchy = {
            'Exception': ['ValueError', 'TypeError', 'KeyError', 'IndexError', 'AttributeError', 'OSError'],
            'ValueError': [],
            'TypeError': [],
            'KeyError': [],
            'IndexError': [],
            'AttributeError': [],
            'OSError': ['FileNotFoundError', 'PermissionError'],
            'FileNotFoundError': [],
            'PermissionError': [],
        }

        for handler_type in handler_exception_types:
            matching_raised = []

            for exc_info in raised_exceptions:
                raised_type = exc_info.exception_type

                # Direct match
                if raised_type == handler_type:
                    matching_raised.append(raised_type)
                # Check if raised type is a subclass of handler type
                elif raised_type in exception_hierarchy.get(handler_type, []):
                    matching_raised.append(raised_type)
                # Check if handler type is Exception (catches all)
                elif handler_type == 'Exception':
                    matching_raised.append(raised_type)

            matches[handler_type] = matching_raised

        return matches
