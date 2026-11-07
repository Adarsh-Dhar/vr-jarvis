"""Interprocedural function summaries for DFG analysis."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
import hashlib
import ast
from .models import DefUseFacts, Definition
from .summaries import FunctionSummary as LibrarySummary, SummaryRegistry


@dataclass
class FunctionSummary:
    """
    Summary of a user-defined function for interprocedural analysis.

    Computed bottom-up over the call graph and cached for reuse.
    """
    function_id: str
    params: List[str]  # Parameter names
    returns_from: Set[str]  # Which inputs contribute to return (param indices, globals, etc.)
    mutates: Set[str]  # Which parameters are mutated
    raises: Set[str]  # Exception types that may be raised
    sources: List[Dict[str, Any]]  # Taint sources reachable inside
    sinks: List[Dict[str, Any]]  # Taint sinks called inside
    content_hash: str  # Hash of function source
    callee_hashes: Dict[str, str]  # Hashes of callee summaries used in computation
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallGraph:
    """Call graph for a module or program."""
    nodes: Set[str]  # function IDs
    edges: Dict[str, Set[str]]  # caller -> set of callees
    reverse_edges: Dict[str, Set[str]]  # callee -> set of callers
    metadata: Dict[str, Any] = field(default_factory=dict)


class InterproceduralSummaryBuilder:
    """
    Build interprocedural function summaries.

    Computes summaries bottom-up over call graph SCCs and caches them.
    """

    def __init__(self, library_registry: Optional[SummaryRegistry] = None):
        self._library_registry = library_registry or SummaryRegistry()
        self._summaries: Dict[str, FunctionSummary] = {}
        self._call_graph: Optional[CallGraph] = None

    def build_call_graph(
        self,
        functions: List[DefUseFacts]
    ) -> CallGraph:
        """
        Build a call graph from a list of function facts.

        Returns a CallGraph with nodes and edges.
        """
        nodes = {facts.function_id for facts in functions}
        edges: Dict[str, Set[str]] = {node: set() for node in nodes}
        reverse_edges: Dict[str, Set[str]] = {node: set() for node in nodes}

        # Extract call relationships from operations
        for facts in functions:
            for operation in facts.operations:
                if operation.operation == 'Call':
                    # Try to resolve the call target
                    callee_id = self._resolve_call_target(operation, facts)
                    if callee_id and callee_id in nodes:
                        edges[facts.function_id].add(callee_id)
                        reverse_edges[callee_id].add(facts.function_id)

        self._call_graph = CallGraph(
            nodes=nodes,
            edges=edges,
            reverse_edges=reverse_edges
        )

        return self._call_graph

    def _resolve_call_target(
        self,
        operation,
        facts: DefUseFacts
    ) -> Optional[str]:
        """
        Resolve a call operation to a target function ID.

        This is a simplified resolution - a full implementation would use
        the existing call resolver from the codebase.
        """
        # Try to extract a qualified name from the expression
        expr = operation.expression

        # For now, we'll return None if we can't resolve it
        # A full implementation would:
        # 1. Check if it's a direct function call
        # 2. Check if it's a method call on a known type
        # 3. Use the symbol table to resolve names
        return None

    def compute_summaries(
        self,
        functions: List[DefUseFacts],
        max_iterations: int = 100
    ) -> Dict[str, FunctionSummary]:
        """
        Compute summaries for all functions bottom-up over SCCs.

        Iterates to a fixed point to handle recursion.
        """
        # Build call graph
        call_graph = self.build_call_graph(functions)

        # Find SCCs (simplified - use reverse post-order for DAGs)
        sccs = self._find_sccs(call_graph)

        # Process SCCs in reverse topological order
        all_summaries = {}
        iteration = 0

        while iteration < max_iterations:
            changed = False
            iteration += 1

            for scc in sccs:
                for function_id in scc:
                    facts = next((f for f in functions if f.function_id == function_id), None)
                    if not facts:
                        continue

                    # Get callee summaries
                    callee_summaries = {
                        callee: all_summaries.get(callee)
                        for callee in call_graph.edges.get(function_id, set())
                    }

                    # Compute summary
                    summary = self._compute_function_summary(
                        facts,
                        callee_summaries,
                        all_summaries
                    )

                    # Check if changed
                    old_summary = all_summaries.get(function_id)
                    if old_summary:
                        if (summary.content_hash != old_summary.content_hash or
                            summary.callee_hashes != old_summary.callee_hashes):
                            changed = True
                            all_summaries[function_id] = summary
                    else:
                        changed = True
                        all_summaries[function_id] = summary

            if not changed:
                break

        self._summaries = all_summaries
        return all_summaries

    def _find_sccs(self, call_graph: CallGraph) -> List[Set[str]]:
        """
        Find strongly connected components in the call graph.

        Simplified implementation - assumes mostly DAG structure.
        """
        # For now, treat each node as its own SCC
        # A full implementation would use Tarjan's algorithm
        return [{node} for node in call_graph.nodes]

    def _compute_function_summary(
        self,
        facts: DefUseFacts,
        callee_summaries: Dict[str, Optional[FunctionSummary]],
        existing_summaries: Dict[str, FunctionSummary]
    ) -> FunctionSummary:
        """
        Compute a summary for a single function.

        Combines local analysis with callee summaries.
        """
        # Compute content hash
        content_hash = self._compute_content_hash(facts)

        # Get parameter names
        params = [d.variable for d in facts.definitions if d.kind == 'parameter']

        # Initialize summary
        returns_from = set()
        mutates = set()
        raises = set()
        sources = []
        sinks = []

        # Analyze local definitions and operations
        for operation in facts.operations:
            if operation.operation == 'Call':
                # Check library summaries
                from .summaries import infer_call_summary
                lib_summary = infer_call_summary(operation, facts, self._library_registry)

                returns_from.update(lib_summary.returns_from)
                raises.update(lib_summary.raises)
                if lib_summary.sinks:
                    sinks.extend([{'kind': s} for s in lib_summary.sinks])

                # Check user-defined function summaries
                callee_id = self._resolve_call_target(operation, facts)
                if callee_id and callee_id in callee_summaries:
                    callee_summary = callee_summaries[callee_id]
                    if callee_summary:
                        returns_from.update(callee_summary.returns_from)
                        mutates.update(callee_summary.mutates)
                        raises.update(callee_summary.raises)
                        sources.extend(callee_summary.sources)
                        sinks.extend(callee_summary.sinks)

        # Compute callee hashes
        callee_hashes = {}
        for callee_id, summary in callee_summaries.items():
            if summary:
                callee_hashes[callee_id] = summary.content_hash

        return FunctionSummary(
            function_id=facts.function_id,
            params=params,
            returns_from=returns_from,
            mutates=mutates,
            raises=raises,
            sources=sources,
            sinks=sinks,
            content_hash=content_hash,
            callee_hashes=callee_hashes,
            metadata={}
        )

    def _compute_content_hash(self, facts: DefUseFacts) -> str:
        """Compute a hash of the function's content."""
        # Hash the AST or source
        # For now, use a simple hash of the function ID and definition count
        data = f"{facts.function_id}:{len(facts.definitions)}:{len(facts.operations)}"
        return hashlib.md5(data.encode()).hexdigest()

    def get_summary(self, function_id: str) -> Optional[FunctionSummary]:
        """Get a computed summary for a function."""
        return self._summaries.get(function_id)

    def invalidate_function(self, function_id: str):
        """Invalidate a function's summary (e.g., after edit)."""
        if function_id in self._summaries:
            del self._summaries[function_id]

        # Recompute affected functions (callers)
        if self._call_graph:
            callers = self._call_graph.reverse_edges.get(function_id, set())
            for caller in callers:
                self.invalidate_function(caller)
