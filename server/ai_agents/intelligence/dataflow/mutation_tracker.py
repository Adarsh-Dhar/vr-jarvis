"""Mutation and deletion tracking for data-flow analysis."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
import ast
from .models import Definition, DefUseFacts, ExpressionFact
from .points_to import PointsToResult, infer_mutation_from_call


@dataclass
class MutationEvent:
    """A mutation event that affects a variable or object."""
    id: str
    kind: str  # 'delete', 'attribute_delete', 'subscript_delete', 'method_mutation'
    target_binding: str  # The variable or object being mutated
    line: int
    cfg_node_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MutationTrackingResult:
    """Result of mutation tracking analysis."""
    mutations: List[MutationEvent]
    affected_bindings: Set[str]  # Bindings affected by mutations
    deletion_events: List[MutationEvent]  # Subset of mutations that are deletions
    diagnostics: List[Dict[str, Any]]


class MutationRegistry:
    """
    Registry of known mutating methods and functions.

    This replaces the hard-coded known_mutations list with a more extensible system.
    """

    def __init__(self):
        # Built-in mutating methods
        self._method_mutations = {
            # List methods
            'append': {'receiver_affected': True, 'mutates_receiver': True},
            'extend': {'receiver_affected': True, 'mutates_receiver': True},
            'insert': {'receiver_affected': True, 'mutates_receiver': True},
            'remove': {'receiver_affected': True, 'mutates_receiver': True},
            'pop': {'receiver_affected': True, 'mutates_receiver': True},
            'clear': {'receiver_affected': True, 'mutates_receiver': True},
            'sort': {'receiver_affected': True, 'mutates_receiver': True},
            'reverse': {'receiver_affected': True, 'mutates_receiver': True},
            # Dict methods
            'update': {'receiver_affected': True, 'mutates_receiver': True},
            'setdefault': {'receiver_affected': True, 'mutates_receiver': True},
            'popitem': {'receiver_affected': True, 'mutates_receiver': True},
            'clear': {'receiver_affected': True, 'mutates_receiver': True},
            # Set methods
            'add': {'receiver_affected': True, 'mutates_receiver': True},
            'discard': {'receiver_affected': True, 'mutates_receiver': True},
            'remove': {'receiver_affected': True, 'mutates_receiver': True},
            'pop': {'receiver_affected': True, 'mutates_receiver': True},
            'clear': {'receiver_affected': True, 'mutates_receiver': True},
        }

        # Built-in mutating functions
        self._function_mutations = {
            # Functions that mutate their arguments
            # (Most built-in functions are pure, but we can add custom ones here)
        }

        # User-defined mutations (can be added dynamically)
        self._user_mutations: Dict[str, Dict[str, Any]] = {}

    def is_mutating_method(self, method_name: str) -> bool:
        """Check if a method is known to be mutating."""
        return method_name in self._method_mutations

    def is_mutating_function(self, function_name: str) -> bool:
        """Check if a function is known to be mutating."""
        return function_name in self._function_mutations

    def get_mutation_info(self, method_name: str) -> Optional[Dict[str, Any]]:
        """Get mutation information for a method."""
        return self._method_mutations.get(method_name)

    def add_user_mutation(self, qualified_name: str, info: Dict[str, Any]):
        """Add a user-defined mutating function/method."""
        self._user_mutations[qualified_name] = info

    def get_all_mutating_methods(self) -> Set[str]:
        """Get all known mutating method names."""
        return set(self._method_mutations.keys()) | set(self._user_mutations.keys())


class MutationTracker:
    """Track mutations and deletions in code."""

    def __init__(self, registry: Optional[MutationRegistry] = None):
        self._registry = registry or MutationRegistry()
        self._mutation_counter = 0

    def track_mutations(
        self,
        facts: DefUseFacts,
        points_to_result: Optional[PointsToResult] = None
    ) -> MutationTrackingResult:
        """
        Track all mutation events in the code.

        Returns:
            MutationTrackingResult with all detected mutations
        """
        mutations = []
        deletion_events = []
        affected_bindings = set()
        diagnostics = []

        # Track method call mutations
        for operation in facts.operations:
            if operation.operation == 'Call':
                mutation_info = infer_mutation_from_call(operation, facts, points_to_result)

                if mutation_info['is_mutation']:
                    self._mutation_counter += 1
                    mutation_id = f"mutation_{self._mutation_counter}"

                    receiver_binding = mutation_info.get('receiver_binding')
                    if receiver_binding:
                        affected_bindings.add(receiver_binding)

                        # Add all aliased bindings if points-to analysis is available
                        for binding in mutation_info.get('mutated_bindings', []):
                            affected_bindings.add(binding)

                    mutation = MutationEvent(
                        id=mutation_id,
                        kind='method_mutation',
                        target_binding=receiver_binding or 'unknown',
                        line=operation.line,
                        cfg_node_id=operation.cfg_node_ids[0] if operation.cfg_node_ids else 'unknown',
                        metadata={
                            'operation_id': operation.id,
                            'expression': operation.expression,
                            'mutated_bindings': list(mutation_info.get('mutated_bindings', [])),
                        }
                    )
                    mutations.append(mutation)

        # Track deletion events (from definition kind)
        for definition in facts.definitions:
            if definition.kind in ('delete', 'deletion'):
                self._mutation_counter += 1
                mutation_id = f"mutation_{self._mutation_counter}"

                deletion = MutationEvent(
                    id=mutation_id,
                    kind='delete',
                    target_binding=definition.binding_key,
                    line=definition.line,
                    cfg_node_id=definition.cfg_node_ids[0] if definition.cfg_node_ids else 'unknown',
                    metadata={
                        'definition_id': definition.id,
                        'variable': definition.variable,
                    }
                )
                mutations.append(deletion)
                deletion_events.append(deletion)
                affected_bindings.add(definition.binding_key)

        return MutationTrackingResult(
            mutations=mutations,
            affected_bindings=affected_bindings,
            deletion_events=deletion_events,
            diagnostics=diagnostics
        )

    def get_mutation_metadata_for_call(
        self,
        operation: ExpressionFact,
        receiver_binding: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get mutation metadata for a call operation.

        This replaces the hard-coded known_mutations check in the evaluator.
        """
        if operation.operation != 'Call':
            return {
                'side_effect': 'unknown',
                'confidence': 'low',
                'arg_count': 0,
            }

        # Try to extract method name from expression
        expr = operation.expression
        if '.' in expr and '(' in expr:
            method_start = expr.rfind('.')
            method_end = expr.find('(')
            if method_start < method_end:
                method_name = expr[method_start + 1:method_end].strip()

                if self._registry.is_mutating_method(method_name):
                    mutation_info = self._registry.get_mutation_info(method_name)
                    return {
                        'side_effect': 'known_mutation',
                        'confidence': 'high',
                        'mutation_kind': method_name,
                        'receiver': receiver_binding or 'unknown',
                        'mutates_receiver': mutation_info.get('mutates_receiver', True),
                        'arg_count': len(operation.input_use_ids) + len(operation.input_operation_ids),
                    }

        # Default: unknown side effect
        return {
            'side_effect': 'unknown',
            'confidence': 'low',
            'arg_count': len(operation.input_use_ids) + len(operation.input_operation_ids),
        }
