"""Interprocedural function summaries for DFG analysis."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
import hashlib
import ast
from .models import DefUseFacts, Definition
from .summaries import FunctionSummary as LibrarySummary, SummaryRegistry


def _digest(s: 'FunctionSummary') -> str:
    """Digest of a summary's computed result — content hash plus the sets
    that callers actually consume. Used for fixed-point comparison and for
    callee_hashes so a change anywhere in a callee's own callees propagates."""
    return hashlib.sha256(repr((
        s.content_hash,
        sorted(s.returns_from),
        sorted(s.mutates),
        sorted(s.raises),
    )).encode()).hexdigest()


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
                 graph=None, file_of: Optional[Dict[str, str]] = None,
                 source_hash_of: Optional[Dict[str, str]] = None,
                 ast_of: Optional[Dict[Any, Any]] = None):
        self._library_registry = library_registry or SummaryRegistry()
        self._summaries: Dict[str, FunctionSummary] = {}
        self._call_graph: Optional[CallGraph] = None
        # Optional index graph + function_id -> file mapping used to resolve
        # call targets through the shared confirmed-call resolver. Without a
        # graph every call stays unresolved (previous stub behaviour).
        self._graph = graph
        self._file_of = dict(file_of or {})
        # function_id -> sha256 of the function's source, and
        # function_id -> ast.FunctionDef. Both feed content hashing and
        # argument binding; without them summaries fall back to fact counts.
        self._source_hash_of = dict(source_hash_of or {})
        self._ast_of = dict(ast_of or {})
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
                    if old_summary is None or _digest(summary) != _digest(old_summary) \
                            or summary.callee_hashes != old_summary.callee_hashes:
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
                        # Callee returns_from/mutates name the callee's
                        # parameters — a different namespace. Map them back
                        # to the caller's argument variables through the
                        # recorded call_shape binding.
                        self._merge_callee_effects(
                            operation, callee_id, callee_summary,
                            facts, uses_by_id, returns_from, mutates)
                        raises.update(callee_summary.raises)
                        sources.extend(callee_summary.sources)
                        sinks.extend(callee_summary.sinks)

        # Compute callee hashes: digest the callee's computed result so a
        # change anywhere inside the callee's own callees is visible here.
        callee_hashes = {}
        for callee_id, summary in callee_summaries.items():
            if summary:
                callee_hashes[callee_id] = _digest(summary)

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

    def _merge_callee_effects(
        self,
        operation,
        callee_id: str,
        callee_summary: FunctionSummary,
        facts: DefUseFacts,
        uses_by_id: Dict[str, Any],
        returns_from: Set[str],
        mutates: Set[str],
    ) -> None:
        """Map a callee summary's parameter-level effects onto the caller's
        argument variables via call_binding.bind_call. Unbound or aggregate
        arguments contribute nothing — never a guessed flow."""
        from .call_binding import bind_call
        call_shape = (operation.metadata or {}).get('call_shape')
        callee_ast = self._ast_of.get(callee_id)
        is_method = False
        if isinstance(callee_ast, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and callee_ast.args.args \
                and callee_ast.args.args[0].arg in ('self', 'cls'):
            is_method = True
        binding = bind_call(call_shape, callee_ast, is_method=is_method)
        param_names = {d.variable for d in facts.definitions
                       if d.kind == 'parameter'}
        for b in binding.get('bindings') or []:
            if b.get('status') != 'bound':
                continue
            for uid in b.get('use_ids') or []:
                u = uses_by_id.get(uid)
                if not u or u.variable not in param_names:
                    continue
                if b.get('param') in callee_summary.returns_from:
                    returns_from.add(u.variable)
                if b.get('param') in callee_summary.mutates:
                    mutates.add(u.variable)

    def _compute_content_hash(self, facts: DefUseFacts) -> str:
        """Compute a hash of the function's real content.

        Prefers the caller-supplied source hash (sha256 of the function
        source); otherwise hashes every definition and operation so an edit
        that changes neither count still changes the hash."""
        h = self._source_hash_of.get(facts.function_id)
        if h:
            return h
        parts = [facts.function_id]
        parts += ['%s:%s:%s' % (d.id, d.variable, d.line)
                  for d in facts.definitions]
        parts += ['%s:%s:%s:%s' % (o.id, o.operation, o.line, o.expression)
                  for o in facts.operations]
        return hashlib.sha256('\n'.join(parts).encode()).hexdigest()

    def get_summary(self, function_id: str) -> Optional[FunctionSummary]:
        """Get a computed summary for a function."""
        return self._summaries.get(function_id)

    def invalidate_function(self, function_id: str, _seen=None):
        """Invalidate a function's summary (e.g., after edit).

        Recurses into callers with a visited set so call-graph cycles
        terminate instead of raising RecursionError."""
        seen = _seen if _seen is not None else set()
        if function_id in seen:
            return
        seen.add(function_id)
        self._summaries.pop(function_id, None)

        # Recompute affected functions (callers)
        if self._call_graph:
            callers = self._call_graph.reverse_edges.get(function_id, set())
            for caller in callers:
                self.invalidate_function(caller, seen)
