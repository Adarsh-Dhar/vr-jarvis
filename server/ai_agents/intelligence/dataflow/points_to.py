"""Points-to analysis for tracking object aliases in Python code."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
import ast
from .models import Definition, DefUseFacts, ExpressionFact


@dataclass
class AllocationSite:
    """An abstract object allocation site."""
    id: str
    kind: str  # 'list', 'dict', 'set', 'object', 'unknown'
    line: int
    node_id: str  # CFG node ID where allocation occurs
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PointsToResult:
    """Result of points-to analysis."""
    points_to: Dict[str, Set[str]]  # variable -> set of allocation site IDs
    field_points_to: Dict[str, Dict[str, Set[str]]]  # alloc_id -> field -> set of alloc IDs
    allocation_sites: Dict[str, AllocationSite]  # alloc_id -> AllocationSite
    alias_pairs: Set[tuple[str, str]]  # pairs of variables that may alias
    diagnostics: List[Dict[str, Any]]


class PointsToAnalyzer:
    """
    Flow-insensitive Andersen-style points-to analysis.

    Tracks which abstract objects (allocation sites) each variable may point to,
    and field relationships between objects.
    """

    def __init__(self):
        self._alloc_counter = 0

    def analyze(
        self,
        facts: DefUseFacts,
        function_id: str
    ) -> PointsToResult:
        """
        Perform points-to analysis.

        Returns mapping from variables to allocation sites they may point to.
        """
        points_to: Dict[str, Set[str]] = {}
        field_points_to: Dict[str, Dict[str, Set[str]]] = {}
        allocation_sites: Dict[str, AllocationSite] = {}
        alias_pairs: Set[tuple[str, str]] = set()
        diagnostics = []

        # Step 1: Identify allocation sites
        for definition in facts.definitions:
            # Check if the definition expression contains collection literals
            if definition.expression:
                expr = definition.expression.strip()

                # Extract RHS from assignment (e.g., "a = [1, 2, 3]" -> "[1, 2, 3]")
                if '=' in expr:
                    rhs = expr.split('=', 1)[1].strip()
                else:
                    rhs = expr

                # Check for list literal
                if rhs.startswith('[') and rhs.endswith(']'):
                    alloc_site = self._create_allocation_site(definition, 'list')
                    allocation_sites[alloc_site.id] = alloc_site

                    var_key = definition.binding_key
                    if var_key not in points_to:
                        points_to[var_key] = set()
                    points_to[var_key].add(alloc_site.id)
                # Check for dict literal
                elif rhs.startswith('{') and rhs.endswith('}') and ':' in rhs:
                    alloc_site = self._create_allocation_site(definition, 'dict')
                    allocation_sites[alloc_site.id] = alloc_site

                    var_key = definition.binding_key
                    if var_key not in points_to:
                        points_to[var_key] = set()
                    points_to[var_key].add(alloc_site.id)
                # Check for set literal (has braces but no colon)
                elif rhs.startswith('{') and rhs.endswith('}') and ':' not in rhs:
                    alloc_site = self._create_allocation_site(definition, 'set')
                    allocation_sites[alloc_site.id] = alloc_site

                    var_key = definition.binding_key
                    if var_key not in points_to:
                        points_to[var_key] = set()
                    points_to[var_key].add(alloc_site.id)

        # Step 2: Identify constructor calls (e.g., list(), dict(), set())
        for operation in facts.operations:
            if operation.operation == 'Call':
                alloc_site = self._try_infer_constructor_allocation(operation, facts)
                if alloc_site:
                    allocation_sites[alloc_site.id] = alloc_site

                    # The output definition points to this allocation
                    for def_id in operation.output_definition_ids:
                        for definition in facts.definitions:
                            if definition.id == def_id:
                                var_key = definition.binding_key
                                if var_key not in points_to:
                                    points_to[var_key] = set()
                                points_to[var_key].add(alloc_site.id)
                                break

        # Step 3: Build constraint graph and solve
        # Constraint types:
        # - a = b: pts(a) ⊇ pts(b)
        # - a.f = b: for each x in pts(a), pts(x.f) ⊇ pts(b)
        # - a = b.f: for each x in pts(b), pts(a) ⊇ pts(x.f)

        worklist = []

        # Add simple assignment constraints (a = b)
        for definition in facts.definitions:
            if definition.kind == 'assignment':
                # Find which variables are used in the RHS
                # This is a simplified approach - we'd need the expression tree
                # For now, we'll handle simple name assignments
                pass  # TODO: Parse RHS to find source variables

        # Solve with worklist algorithm
        changed = True
        iteration = 0
        max_iterations = 1000  # Prevent infinite loops

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1

            # Propagate points-to sets through assignments
            # This is a simplified version - full implementation would track constraints

        # Compute alias pairs
        for var1 in points_to:
            for var2 in points_to:
                if var1 < var2:  # Avoid duplicates
                    if points_to[var1] & points_to[var2]:
                        alias_pairs.add((var1, var2))

        return PointsToResult(
            points_to=points_to,
            field_points_to=field_points_to,
            allocation_sites=allocation_sites,
            alias_pairs=alias_pairs,
            diagnostics=diagnostics
        )

    def _create_allocation_site(self, definition: Definition, kind: str = 'object') -> AllocationSite:
        """Create an allocation site from a definition."""
        self._alloc_counter += 1
        alloc_id = f"alloc_{self._alloc_counter}"

        cfg_node_id = definition.cfg_node_ids[0] if definition.cfg_node_ids else 'unknown'

        return AllocationSite(
            id=alloc_id,
            kind=kind,
            line=definition.line,
            node_id=cfg_node_id,
            metadata={
                'definition_id': definition.id,
                'expression': definition.expression,
            }
        )

    def _try_infer_constructor_allocation(
        self,
        operation: ExpressionFact,
        facts: DefUseFacts
    ) -> Optional[AllocationSite]:
        """
        Try to infer if a call is a constructor that creates a new object.

        Returns an AllocationSite if the call is a known constructor.
        """
        # Known constructors
        constructor_kinds = {
            'list': 'list',
            'dict': 'dict',
            'set': 'set',
            'tuple': 'tuple',
            'str': 'object',
            'int': 'object',
            'float': 'object',
        }

        # Check if the call is to a known constructor
        # This is simplified - we'd need to resolve the call target
        # For now, we'll check the expression string
        expr = operation.expression.lower()
        for constructor, kind in constructor_kinds.items():
            if f'{constructor}(' in expr:
                self._alloc_counter += 1
                alloc_id = f"alloc_{self._alloc_counter}"

                cfg_node_id = operation.cfg_node_ids[0] if operation.cfg_node_ids else 'unknown'

                return AllocationSite(
                    id=alloc_id,
                    kind=kind,
                    line=operation.line,
                    node_id=cfg_node_id,
                    metadata={
                        'operation_id': operation.id,
                        'expression': operation.expression,
                        'constructor': constructor,
                    }
                )

        return None

    def get_mutated_variables(
        self,
        receiver_binding: str,
        facts: DefUseFacts,
        points_to_result: PointsToResult
    ) -> Set[str]:
        """
        Find all variables that may alias the receiver and could be affected by a mutation.

        When a method call mutates an object, all variables pointing to that object
        (through aliases) may be affected.
        """
        mutated = set()

        # Get allocation sites the receiver points to
        receiver_allocs = points_to_result.points_to.get(receiver_binding, set())

        # Find all variables that point to any of these allocations
        for var_key, allocs in points_to_result.points_to.items():
            if allocs & receiver_allocs:
                mutated.add(var_key)

        return mutated


def infer_mutation_from_call(
    operation: ExpressionFact,
    facts: DefUseFacts,
    points_to_result: Optional[PointsToResult] = None
) -> Dict[str, Any]:
    """
    Infer whether a call is a mutation and what it mutates.

    Returns a dict with 'is_mutation', 'receiver_binding', and 'mutated_bindings'.
    """
    # Known mutating methods
    mutating_methods = {
        'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'sort', 'reverse',
        'update', 'setdefault', 'popitem', 'clear',
        'add', 'discard', 'remove',
    }

    result = {
        'is_mutation': False,
        'receiver_binding': None,
        'mutated_bindings': set(),
    }

    # Check if operation is a call to a mutating method
    if operation.operation == 'Call':
        expr = operation.expression

        # Check for method call pattern: obj.method(...)
        if '.' in expr and '(' in expr:
            # Extract method name
            method_start = expr.rfind('.')
            method_end = expr.find('(')
            if method_start < method_end:
                method_name = expr[method_start + 1:method_end].strip()

                if method_name in mutating_methods:
                    result['is_mutation'] = True

                    # Find the receiver variable
                    # This is simplified - we'd need to parse the receiver expression
                    # For now, we'll extract the object being called
                    receiver_expr = expr[:method_start].strip()

                    # Try to find the binding for the receiver
                    # This requires resolving the receiver expression to a variable
                    # For simplicity, we'll just check if it's a simple name
                    if receiver_expr and not any(c in receiver_expr for c in '.[]()'):
                        result['receiver_binding'] = receiver_expr

                        # If points-to analysis is available, find all aliases
                        if points_to_result:
                            mutated = points_to_result.get_mutated_variables(
                                receiver_expr,
                                facts,
                                points_to_result
                            )
                            result['mutated_bindings'] = mutated

    return result
