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
    actual_kwargs: Dict[str, List[str]]  # Keyword argument name -> use IDs
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
    # Endpoint functions: 'argument' edges flow caller -> callee,
    # 'return' edges flow callee -> caller.
    caller_function_id: Optional[str] = None
    callee_function_id: Optional[str] = None
    # Source location of each endpoint, so cross-function edges can be
    # reported (and drawn) without a second lookup.
    source_file: Optional[str] = None
    source_line: int = 0
    target_file: Optional[str] = None
    target_line: int = 0
    # DFG node ids resolved through the per-function fact_to_node map; None
    # when the endpoint id is not a fact id (e.g. 'summary:x' sources).
    source_node_id: Optional[str] = None
    target_node_id: Optional[str] = None
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
                # Deterministic id: same call site -> same id on every run,
                # so cached summaries and tests stay stable.
                call_site_id = '%s@%s:%s' % (
                    facts.function_id, operation.line,
                    getattr(operation, 'column', 0) or 0)

                # Extract actual arguments; keywords come from the recorded
                # call_shape ({name, use_ids, starred, ...} per keyword arg).
                actual_args = list(operation.input_use_ids or [])
                shape = (operation.metadata or {}).get('call_shape') or {}
                actual_kwargs = {
                    k['name']: list(k.get('use_ids') or [])
                    for k in shape.get('keywords') or []
                    if k.get('name') is not None
                }

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
        """Resolve the callee through the shared confirmed-call resolver
        (call_target.resolve_call_target) using the builder's index graph.
        Returns the target id only for status 'resolved'; every other status
        maps to an unresolved/polymorphic CallSite resolution."""
        builder = self._summary_builder
        graph = getattr(builder, '_graph', None)
        if graph is None:
            return None
        from .call_target import resolve_call_target
        file_of = getattr(builder, '_file_of', {}) or {}
        file = file_of.get(facts.function_id) or facts.file
        res = resolve_call_target(graph, facts.function_id, file,
                                  operation.line,
                                  getattr(operation, 'column', None))
        # Stash the full result so _determine_resolution/callers can see it.
        operation.metadata = dict(operation.metadata or {})
        operation.metadata['call_target'] = res
        if res['status'] == 'resolved':
            return res.get('target_id')
        return None

    def _determine_resolution(
        self,
        operation: ExpressionFact,
        callee_id: Optional[str]
    ) -> str:
        """Determine the resolution confidence of a call."""
        target = (operation.metadata or {}).get('call_target') or {}
        status = target.get('status')
        if callee_id and status == 'resolved':
            return 'static_resolved'
        if status == 'possible':
            return 'polymorphic'
        if status in ('ambiguous', 'unresolved'):
            return 'unresolved'
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
        callee_summary: Optional[FunctionSummary],
        callee_func_ast=None,
        is_method: bool = False
    ) -> List[InterproceduralEdge]:
        """
        Create interprocedural edges for a call site.

        Argument binding uses call_binding.bind_call against the callee's
        real signature (keywords, defaults, self/cls, *args/**kwargs and
        positional-only rules) — never a positional index guess. Only
        bindings with status 'bound' produce edges; aggregate bindings
        (vararg/kwarg) produce 'possible' edges, never per-element edges.
        A 'confirmed' edge additionally requires the call site itself to be
        'static_resolved'.
        """
        edges = []

        if not callee_facts:
            # Unresolved call - no edges
            return edges

        from .call_binding import bind_call

        call_op = next((o for o in caller_facts.operations
                        if o.id == call_site.operation_id), None)
        call_shape = ((call_op.metadata or {}).get('call_shape')
                      if call_op else None)
        binding = bind_call(call_shape, callee_func_ast, is_method=is_method)

        param_defs = {d.variable: d for d in callee_facts.definitions
                      if d.kind == 'parameter'}
        uses_by_id = {u.id: u for u in caller_facts.uses}
        site_confirmed = call_site.resolution == 'static_resolved'

        for b in binding.get('bindings') or []:
            param_def = param_defs.get(b.get('param')) if b.get('param') else None
            aggregate = b.get('precision') == 'aggregate' \
                or b.get('param_kind') in ('vararg', 'kwarg')
            confirmed = site_confirmed and b.get('status') == 'bound' \
                and not aggregate
            resolution = 'confirmed' if confirmed else 'possible'
            use_ids = b.get('use_ids') or [call_site.operation_id]
            for i, use_id in enumerate(use_ids):
                use = uses_by_id.get(use_id)
                edges.append(InterproceduralEdge(
                    edge_id='%s_arg_%s_%s' % (
                        call_site.call_site_id,
                        b.get('param') or 'arg', i),
                    call_site_id=call_site.call_site_id,
                    source_kind='argument',
                    source_id=use_id,
                    target_kind='parameter',
                    target_id=param_def.id if param_def else
                              'unbound:%s' % (b.get('param') or 'arg'),
                    resolution=resolution,
                    caller_function_id=caller_facts.function_id,
                    callee_function_id=callee_facts.function_id,
                    source_file=caller_facts.file,
                    source_line=use.line if use else call_site.line,
                    target_file=callee_facts.file,
                    target_line=param_def.line if param_def else call_site.line,
                    metadata={
                        'param_name': b.get('param'),
                        'param_kind': b.get('param_kind'),
                        'arg_index': b.get('arg_index'),
                        'keyword': b.get('keyword'),
                        'aggregate': aggregate,
                    }
                ))

        # Return edges: each callee return feeds the caller's use (or the
        # definition) that consumes the call result.
        return_sources = [o.id for o in callee_facts.operations
                          if o.operation == 'return_value']
        if callee_summary and callee_summary.returns_from:
            return_sources += ['summary:%s' % r
                               for r in sorted(callee_summary.returns_from)]
        result_def_ids = set((call_op.output_definition_ids
                              if call_op else []) or [])
        result_defs = [d for d in caller_facts.definitions
                       if d.id in result_def_ids]
        callee_op_by_id = {o.id: o for o in callee_facts.operations}
        if return_sources and result_defs:
            for rdef in result_defs:
                consumers = [u for u in caller_facts.uses
                             if u.binding_key == rdef.binding_key
                             and u.line >= call_site.line]
                targets = [u.id for u in consumers] or [rdef.id]
                target_uses = {u.id: u for u in caller_facts.uses}
                for si, src in enumerate(return_sources):
                    src_op = callee_op_by_id.get(src)
                    for ti, tgt in enumerate(targets):
                        tgt_use = target_uses.get(tgt)
                        edges.append(InterproceduralEdge(
                            edge_id='%s_ret_%s_%s' % (
                                call_site.call_site_id, si, ti),
                            call_site_id=call_site.call_site_id,
                            source_kind='return',
                            source_id=src,
                            target_kind='call_result',
                            target_id=tgt,
                            resolution='confirmed' if site_confirmed else 'possible',
                            caller_function_id=caller_facts.function_id,
                            callee_function_id=callee_facts.function_id,
                            source_file=callee_facts.file,
                            source_line=src_op.line if src_op else call_site.line,
                            target_file=caller_facts.file,
                            target_line=tgt_use.line if tgt_use else rdef.line,
                            metadata={'result_definition': rdef.id,
                                      'param_name': rdef.variable}
                        ))

        return edges

    def connect_all_call_sites(
        self,
        all_facts: List[DefUseFacts],
        summaries: Dict[str, FunctionSummary],
        ast_of: Optional[Dict[str, Any]] = None,
        method_ids=frozenset()
    ) -> Dict[str, List[InterproceduralEdge]]:
        """
        Connect all call sites across all functions.

        ``ast_of`` maps function_id -> ast.FunctionDef so bind_call can see
        the callee signature; ``method_ids`` names callees whose leading
        self/cls parameter binds to the receiver, not to an argument.
        Without the AST every binding comes back unresolved and no argument
        edge is ever created.

        Returns a mapping from function_id to list of interprocedural edges.
        """
        ast_of = ast_of or {}
        all_edges: Dict[str, List[InterproceduralEdge]] = {}

        # Build function ID -> facts mapping
        facts_map = {f.function_id: f for f in all_facts}

        for facts in all_facts:
            call_sites = self.identify_call_sites(facts)
            function_edges = []

            for call_site in call_sites:
                cid = call_site.callee_function_id
                callee_facts = facts_map.get(cid) if cid else None
                callee_summary = summaries.get(cid) if cid else None

                edges = self.connect_call_site(
                    call_site,
                    facts,
                    callee_facts,
                    callee_summary,
                    callee_func_ast=ast_of.get(cid),
                    is_method=cid in method_ids
                )
                function_edges.extend(edges)

            all_edges[facts.function_id] = function_edges

        return all_edges
