"""Call site connection with context sensitivity for interprocedural analysis."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from .models import DefUseFacts, ExpressionFact, Definition, VariableUse
from .interprocedural import FunctionSummary, InterproceduralSummaryBuilder


@dataclass
class CallSite:
    """A call site with context information."""
    call_site_id: str
    caller_function_id: str
    callee_function_id: Optional[str]  # May be None for unresolved calls
    operation_id: str
    line: int
    actual_args: List[str]  # Use IDs of actual arguments
    actual_kwargs: Dict[str, str]  # Keyword argument use IDs
    resolution: str  # 'static_resolved', 'polymorphic', 'dynamic', 'external', 'unresolved'
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InterproceduralEdge:
    """An edge connecting caller and callee."""
    edge_id: str
    call_site_id: str
    source_kind: str  # 'argument', 'return'
    source_id: str  # Use ID or definition ID
    target_kind: str  # 'parameter', 'call_result'
    target_id: str  # Parameter definition ID or use ID
    resolution: str  # 'confirmed', 'possible', 'unknown'
    metadata: Dict[str, Any] = field(default_factory=dict)


class CallSiteConnector:
    """
    Connect call sites with context-sensitive interprocedural edges.

    Creates:
    - Argument edges: actual argument use -> formal parameter definition
    - Return edges: callee return definition -> call result use
    - Tagged with call_site_id for context sensitivity
    """

    def __init__(self, summary_builder: InterproceduralSummaryBuilder):
        self._summary_builder = summary_builder
        self._call_site_counter = 0
        self._edge_counter = 0

    def identify_call_sites(
        self,
        facts: DefUseFacts
    ) -> List[CallSite]:
        """
        Identify all call sites in a function.

        Returns a list of CallSite objects with context information.
        """
        call_sites = []

        for operation in facts.operations:
            if operation.operation == 'Call':
                self._call_site_counter += 1
                call_site_id = f"{facts.function_id}_callsite_{self._call_site_counter}"

                # Extract actual arguments
                actual_args = operation.input_use_ids
                actual_kwargs = {}  # Would need to parse keyword arguments

                # Resolve callee
                callee_id = self._resolve_callee(operation, facts)
                resolution = self._determine_resolution(operation, callee_id)

                call_site = CallSite(
                    call_site_id=call_site_id,
                    caller_function_id=facts.function_id,
                    callee_function_id=callee_id,
                    operation_id=operation.id,
                    line=operation.line,
                    actual_args=actual_args,
                    actual_kwargs=actual_kwargs,
                    resolution=resolution,
                    metadata={
                        'expression': operation.expression,
                        'cfg_node_ids': operation.cfg_node_ids
                    }
                )
                call_sites.append(call_site)

        return call_sites

    def _resolve_callee(
        self,
        operation: ExpressionFact,
        facts: DefUseFacts
    ) -> Optional[str]:
        """
        Resolve the callee function ID for a call operation.

        This is a simplified implementation. A full version would use
        the existing call resolver from the codebase.
        """
        # Try to extract a qualified name from the expression
        expr = operation.expression

        # For now, return None if we can't resolve it
        # This means we'll mark it as 'unresolved' or 'dynamic'
        return None

    def _determine_resolution(
        self,
        operation: ExpressionFact,
        callee_id: Optional[str]
    ) -> str:
        """Determine the resolution confidence of a call."""
        if callee_id:
            return 'static_resolved'
        elif 'self.' in operation.expression or 'cls.' in operation.expression:
            return 'polymorphic'
        elif operation.expression.startswith('super('):
            return 'dynamic'
        else:
            return 'unresolved'

    def connect_call_site(
        self,
        call_site: CallSite,
        caller_facts: DefUseFacts,
        callee_facts: Optional[DefUseFacts],
        callee_summary: Optional[FunctionSummary]
    ) -> List[InterproceduralEdge]:
        """
        Create interprocedural edges for a call site.

        Returns argument edges and return edges.
        """
        edges = []

        if not callee_facts:
            # Unresolved call - no edges
            return edges

        # Create argument edges: actual arg -> formal param
        param_defs = [d for d in callee_facts.definitions if d.kind == 'parameter']

        for i, actual_arg_id in enumerate(call_site.actual_args):
            if i < len(param_defs):
                param_def = param_defs[i]

                self._edge_counter += 1
                edge = InterproceduralEdge(
                    edge_id=f"{call_site.call_site_id}_arg_{self._edge_counter}",
                    call_site_id=call_site.call_site_id,
                    source_kind='argument',
                    source_id=actual_arg_id,
                    target_kind='parameter',
                    target_id=param_def.id,
                    resolution='confirmed' if call_site.resolution == 'static_resolved' else 'possible',
                    metadata={
                        'param_index': i,
                        'param_name': param_def.variable
                    }
                )
                edges.append(edge)

        # Create return edges: callee return -> call result
        if callee_summary:
            # Find the use of the call result in the caller
            # This is simplified - we'd need to find the use that corresponds to this call
            pass

        return edges

    def connect_all_call_sites(
        self,
        all_facts: List[DefUseFacts],
        summaries: Dict[str, FunctionSummary]
    ) -> Dict[str, List[InterproceduralEdge]]:
        """
        Connect all call sites across all functions.

        Returns a mapping from function_id to list of interprocedural edges.
        """
        all_edges: Dict[str, List[InterproceduralEdge]] = {}

        # Build function ID -> facts mapping
        facts_map = {f.function_id: f for f in all_facts}

        for facts in all_facts:
            call_sites = self.identify_call_sites(facts)
            function_edges = []

            for call_site in call_sites:
                callee_facts = facts_map.get(call_site.callee_function_id) if call_site.callee_function_id else None
                callee_summary = summaries.get(call_site.callee_function_id) if call_site.callee_function_id else None

                edges = self.connect_call_site(
                    call_site,
                    facts,
                    callee_facts,
                    callee_summary
                )
                function_edges.extend(edges)

            all_edges[facts.function_id] = function_edges

        return all_edges
