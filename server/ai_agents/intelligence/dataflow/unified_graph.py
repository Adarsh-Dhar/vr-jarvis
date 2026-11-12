"""Unified CFG and DFG view for combined analysis."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from ..controlflow.models import ControlFlowGraph, CFGNode, CFGEdge
from .models import DataFlowGraph, DataFlowNode, DataFlowEdge


@dataclass
class UnifiedGraphNode:
    """A node in the unified graph."""
    id: str
    kind: str  # 'control', 'data', 'call', 'return'
    subkind: Optional[str]  # 'condition', 'definition', 'use', etc.
    function_id: str
    file: str
    line: int
    column: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedGraphEdge:
    """An edge in the unified graph."""
    id: str
    source: str
    target: str
    kind: str  # 'next', 'true', 'false', 'reaches', 'call', 'return', 'exception'
    subkind: Optional[str]  # 'must_reach', 'may_reach', 'possible', 'unknown'
    call_site_id: Optional[str]
    condition: Optional[Dict[str, Any]]
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedGraph:
    """Unified graph combining CFG and DFG."""
    nodes: List[UnifiedGraphNode]
    edges: List[UnifiedGraphEdge]
    function_id: str
    file: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedGraphBuilder:
    """
    Build a unified graph combining CFG and DFG.

    Combines:
    - Control flow edges (next, true, false, exception)
    - Data flow edges (reaches, call, return)
    - Single node set with typed edges
    - Edge confidence labeling (must_reach, may_reach, possible)
    """

    def build_unified(
        self,
        cfg: ControlFlowGraph,
        dfg: DataFlowGraph
    ) -> UnifiedGraph:
        """
        Build a unified graph from CFG and DFG.

        Returns a UnifiedGraph with combined nodes and typed edges.
        """
        nodes = []
        edges = []
        node_id_map: Dict[str, str] = {}  # Original ID -> Unified ID

        # Add CFG nodes
        for cfg_node in cfg.nodes:
            unified_id = f"unified_{cfg_node.id}"
            node_id_map[cfg_node.id] = unified_id

            node = UnifiedGraphNode(
                id=unified_id,
                kind='control',
                subkind=cfg_node.kind,
                function_id=cfg_node.function_id,
                file=cfg_node.file,
                line=cfg_node.start_line,
                column=0,
                metadata={
                    'original_id': cfg_node.id,
                    'label': cfg_node.label,
                    'ast_kind': cfg_node.ast_kind
                }
            )
            nodes.append(node)

        # Add DFG nodes
        for dfg_node in dfg.nodes:
            unified_id = f"unified_{dfg_node.id}"
            node_id_map[dfg_node.id] = unified_id

            node = UnifiedGraphNode(
                id=unified_id,
                kind='data',
                subkind=dfg_node.kind,
                function_id=dfg_node.function_id,
                file=dfg_node.file,
                line=dfg_node.line,
                column=dfg_node.column,
                metadata={
                    'original_id': dfg_node.id,
                    'variable': dfg_node.variable,
                    'expression': dfg_node.expression
                }
            )
            nodes.append(node)

        # Add CFG edges
        for cfg_edge in cfg.edges:
            source_id = node_id_map.get(cfg_edge.source)
            target_id = node_id_map.get(cfg_edge.target)

            if source_id and target_id:
                edge = UnifiedGraphEdge(
                    id=f"unified_edge_{cfg_edge.id}",
                    source=source_id,
                    target=target_id,
                    kind=cfg_edge.kind,
                    subkind=None,
                    call_site_id=None,
                    condition=self._standardize_condition(cfg_edge.condition),
                    evidence=cfg_edge.evidence
                )
                edges.append(edge)

        # Add DFG edges
        for dfg_edge in dfg.edges:
            source_id = node_id_map.get(dfg_edge.source)
            target_id = node_id_map.get(dfg_edge.target)

            if source_id and target_id:
                edge = UnifiedGraphEdge(
                    id=f"unified_edge_{dfg_edge.id}",
                    source=source_id,
                    target=target_id,
                    kind=dfg_edge.kind,
                    subkind=dfg_edge.resolution,  # resolution -> subkind for confidence
                    call_site_id=None,
                    condition=dfg_edge.condition,
                    evidence=dfg_edge.evidence
                )
                edges.append(edge)

        return UnifiedGraph(
            nodes=nodes,
            edges=edges,
            function_id=cfg.function_id,
            file=cfg.file,
            metadata={
                'cfg_node_count': len(cfg.nodes),
                'dfg_node_count': len(dfg.nodes),
                'total_edge_count': len(edges)
            }
        )

    def build_repository_graph(
        self,
        function_graphs: Dict[str, 'UnifiedGraph'],
        interprocedural_edges: Optional[List[Dict[str, Any]]] = None,
        max_nodes: int = 5000,
    ) -> UnifiedGraph:
        """Merge per-function unified graphs into one repository-level graph.

        ``function_graphs`` maps function_id -> UnifiedGraph (built by
        build_unified). Node and edge ids are namespaced per function so they
        cannot collide. ``interprocedural_edges`` are dicts with keys
        source_function, target_function, kind ('call'|'argument'|'return'),
        resolution ('confirmed'|'possible'), call_site_id and evidence; each
        becomes an edge between the functions' entry nodes labelled with its
        resolution. The merge is capped at ``max_nodes``; when the cap is hit
        the result reports ``metadata['truncated'] = True``.
        """
        nodes: List[UnifiedGraphNode] = []
        edges: List[UnifiedGraphEdge] = []
        entry_of: Dict[str, str] = {}
        truncated = False

        for fid in sorted(function_graphs):
            g = function_graphs[fid]
            if len(nodes) >= max_nodes:
                truncated = True
                break
            first = True
            for n in g.nodes:
                if len(nodes) >= max_nodes:
                    truncated = True
                    break
                nid = '%s::%s' % (fid, n.id)
                nodes.append(UnifiedGraphNode(
                    id=nid, kind=n.kind, subkind=n.subkind,
                    function_id=fid, file=n.file, line=n.line,
                    column=n.column, metadata=dict(n.metadata, unified_id=n.id)))
                if first:
                    entry_of[fid] = nid
                    first = False
            for e in g.edges:
                edges.append(UnifiedGraphEdge(
                    id='%s::%s' % (fid, e.id),
                    source='%s::%s' % (fid, e.source),
                    target='%s::%s' % (fid, e.target),
                    kind=e.kind, subkind=e.subkind,
                    call_site_id=e.call_site_id, condition=e.condition,
                    evidence=e.evidence))

        for i, ie in enumerate(interprocedural_edges or []):
            src = ie.get('source_function')
            dst = ie.get('target_function')
            if src not in entry_of or dst not in entry_of:
                continue
            edges.append(UnifiedGraphEdge(
                id='repo_edge_%d' % i,
                source=entry_of[src],
                target=entry_of[dst],
                kind=ie.get('kind', 'call'),
                subkind=ie.get('resolution', 'possible'),
                call_site_id=ie.get('call_site_id'),
                condition=None,
                evidence=ie.get('evidence') or {}))

        fids = sorted(function_graphs)
        return UnifiedGraph(
            nodes=nodes,
            edges=edges,
            function_id='repository',
            file='',
            metadata={
                'scope': 'repository',
                'function_count': len(fids),
                'function_ids': fids,
                'truncated': truncated,
            })

    def _standardize_condition(self, condition: Optional[Any]) -> Optional[Dict[str, Any]]:
        """Standardize condition to dict format."""
        if not condition:
            return None
        if isinstance(condition, dict):
            return condition
        if isinstance(condition, str):
            return {'predicate': condition, 'polarity': True}
        return None
