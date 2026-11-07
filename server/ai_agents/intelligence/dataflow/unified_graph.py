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

    def _standardize_condition(self, condition: Optional[Any]) -> Optional[Dict[str, Any]]:
        """Standardize condition to dict format."""
        if not condition:
            return None
        if isinstance(condition, dict):
            return condition
        if isinstance(condition, str):
            return {'predicate': condition, 'polarity': True}
        return None
