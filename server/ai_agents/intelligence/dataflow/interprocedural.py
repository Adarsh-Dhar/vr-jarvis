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

    def __init__(self, library_registry: Optional[SummaryRegistry] = None,
                 graph=None, file_of: Optional[Dict[str, str]] = None):
        self._library_registry = library_registry or SummaryRegistry()
        self._summaries: Dict[str, FunctionSummary] = {}
        self._call_graph: Optional[CallGraph] = None
        # Optional index graph + function_id -> file mapping used to resolve
        # call targets through the shared confirmed-call resolver. Without a
        # graph every call stays unresolved (previous stub behaviour).
        self._graph = graph
        self._file_of = dict(file_of or {})
        self._unresolved: Dict[str, List[Dict[str, Any]]] = {}

    @property
    def unresolved(self) -> Dict[str, List[Dict[str, Any]]]:
        return self._unresolved

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
            reverse_edges=reverse_edges,
            metadata={'unresolved': self._unresolved}
        )

        return self._call_graph

    def _resolve_call_target(
        self,
        operation,
        facts: DefUseFacts
    ) -> Optional[str]:
        """Resolve a call operation to a target function ID via the shared
        confirmed-call resolver. Returns the id only for status 'resolved';
        every other status is recorded in the unresolved map and yields
        None, so a possible edge can never become a confirmed summary link."""
        if self._graph is None:
            return None
        from .call_target import resolve_call_target
        file = self._file_of.get(facts.function_id) or facts.file
        res = resolve_call_target(
            self._graph, facts.function_id, file,
            operation.line, getattr(operation, 'column', None))
        if res['status'] != 'resolved':
            self._unresolved.setdefault(facts.function_id, []).append({
                'line': operation.line,
                'expression': operation.expression,
                'status': res['status'],
                'reason': res.get('reason'),
                'candidates': res.get('candidates'),
            })
            return None
        return res.get('target_id')

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

        # Tarjan emits components in reverse topological order of the
        # condensation (callees first), which is the order summaries need.
        sccs = self._find_sccs(call_graph)

        facts_map = {f.function_id: f for f in functions}
        all_summaries: Dict[str, FunctionSummary] = {}
        converged = True

        for scc in sccs:
            # A singleton SCC without a self-edge needs exactly one pass;
            # recursive components iterate to their own fixed point.
            needs_fixpoint = len(scc) > 1 or any(
                fid in call_graph.edges.get(fid, set()) for fid in scc)
            local: Dict[str, FunctionSummary] = {}
            iteration = 0

            while True:
                iteration += 1
                if needs_fixpoint and iteration > max_iterations:
                    converged = False
                    break
                changed = False

                for function_id in sorted(scc):
                    facts = facts_map.get(function_id)
                    if not facts:
                        continue

                    # Callee summaries: same-SCC members from the current
                    # iteration, earlier SCCs from all_summaries.
                    lookup = dict(all_summaries)
                    lookup.update(local)
                    callee_summaries = {
                        callee: lookup.get(callee)
                        for callee in call_graph.edges.get(function_id, set())
                    }

                    summary = self._compute_function_summary(
                        facts, callee_summaries, lookup)

                    old_summary = local.get(function_id)
                    if old_summary is None or (
                            summary.content_hash != old_summary.content_hash or
                            summary.callee_hashes != old_summary.callee_hashes):
                        changed = True
                        local[function_id] = summary

                if not needs_fixpoint or not changed:
                    break

            all_summaries.update(local)

        self._summaries = all_summaries
        if self._call_graph is not None:
            self._call_graph.metadata['converged'] = converged
        return all_summaries

    def _find_sccs(self, call_graph: CallGraph) -> List[Set[str]]:
        """Strongly connected components via iterative Tarjan. Components are
        emitted in reverse topological order of the condensation graph
        (callees before callers), the order summaries need."""
        g = call_graph
        index, low, on_stack = {}, {}, set()
        stack, out = [], []
        idx = [0]
        for root in sorted(g.nodes):
            if root in index:
                continue
            work = [(root, iter(sorted(g.edges.get(root, ()) or ())))]
            index[root] = low[root] = idx[0]
            idx[0] += 1
            stack.append(root)
            on_stack.add(root)
            while work:
                v, it = work[-1]
                for w in it:
                    if w not in index:
                        index[w] = low[w] = idx[0]
                        idx[0] += 1
                        stack.append(w)
                        on_stack.add(w)
                        work.append((w, iter(sorted(g.edges.get(w, ()) or ()))))
                        break
                    elif w in on_stack:
                        low[v] = min(low[v], index[w])
                else:
                    work.pop()
                    if work:
                        low[work[-1][0]] = min(low[work[-1][0]], low[v])
                    if low[v] == index[v]:
                        comp = set()
                        while True:
                            w = stack.pop()
                            on_stack.discard(w)
                            comp.add(w)
                            if w == v:
                                break
                        out.append(comp)
        return out

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

        # Local facts: parameters that reach a return-value sink contribute
        # to returns_from; parameter receivers mutated through attribute or
        # subscript writes contribute to mutates; raise operations contribute
        # to raises.
        param_names = set(params)
        uses_by_id = {u.id: u for u in facts.uses}
        for operation in facts.operations:
            if operation.operation == 'return_value':
                for uid in operation.input_use_ids or []:
                    use = uses_by_id.get(uid)
                    if use and use.variable in param_names:
                        returns_from.add(use.variable)
                meta = operation.metadata or {}
                rv = meta.get('return_variable')
                if rv in param_names:
                    returns_from.add(rv)
            elif operation.operation and 'raise' in operation.operation.lower():
                meta = operation.metadata or {}
                exc = meta.get('exception') or meta.get('type')
                if exc:
                    raises.add(str(exc))

        for d in facts.definitions:
            meta = d.metadata or {}
            if not meta.get('is_mutation'):
                continue
            base = meta.get('receiver') or meta.get('collection')
            if base in param_names:
                mutates.add(base)

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
