"""Interprocedural CFG with call and return edges."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from ..controlflow.models import ControlFlowGraph, CFGNode, CFGEdge, CFGBuildArtifact
from .models import DefUseFacts
from .interprocedural import FunctionSummary
from .call_site_connector import CallSite, CallSiteConnector


@dataclass
class InterproceduralCFGNode:
    """A node in the interprocedural CFG."""
    id: str
    kind: str  # 'function_entry', 'function_exit', 'call', 'return'
    function_id: str
    file: str
    line: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InterproceduralCFGEdge:
    """An edge in the interprocedural CFG."""
    id: str
    source: str
    target: str
    kind: str  # 'call', 'return', 'exception_propagation'
    call_site_id: Optional[str]  # Links call and return edges
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InterproceduralCFG:
    """Interprocedural control-flow graph across multiple functions."""
    function_cfgs: Dict[str, ControlFlowGraph]  # function_id -> CFG
    inter_edges: List[InterproceduralCFGEdge]  # Call and return edges
    entry_points: Set[str]  # Functions that are entry points
    metadata: Dict[str, Any] = field(default_factory=dict)


class InterproceduralCFGBuilder:
    """
    Build an interprocedural CFG with call and return edges.

    Creates a supergraph with:
    - Individual function CFGs
    - Call edges from call nodes to callee entries
    - Return edges from callee exits to call return sites
    - Exception propagation edges between functions
    - All edges tagged with call_site_id for context sensitivity
    """

    def __init__(self):
        self._inter_edge_counter = 0
        self._function_cfgs: Dict[str, ControlFlowGraph] = {}

    def build_interprocedural_cfg(
        self,
        function_artifacts: Dict[str, CFGBuildArtifact],
        call_sites: Dict[str, List[CallSite]]
    ) -> InterproceduralCFG:
        """
        Build an interprocedural CFG from function artifacts and call sites.

        Args:
            function_artifacts: Mapping from function_id to CFGBuildArtifact
            call_sites: Mapping from function_id to list of CallSite objects

        Returns:
            InterproceduralCFG with intra and inter function edges
        """
        inter_edges = []
        entry_points = set()

        # Store individual function CFGs
        for function_id, artifact in function_artifacts.items():
            self._function_cfgs[function_id] = artifact.graph

            # Consider top-level functions as entry points
            # (A full implementation would use main/__main__ detection)
            if not function_id.startswith('builtins.'):
                entry_points.add(function_id)

        # Create call edges
        for caller_id, sites in call_sites.items():
            caller_cfg = self._function_cfgs.get(caller_id)
            if not caller_cfg:
                continue

            for call_site in sites:
                if call_site.callee_function_id:
                    callee_cfg = self._function_cfgs.get(call_site.callee_function_id)
                    if callee_cfg and callee_cfg.entry_node_id:
                        # Create call edge
                        self._inter_edge_counter += 1
                        call_edge = InterproceduralCFGEdge(
                            id=f"inter_call_{self._inter_edge_counter}",
                            source=call_site.caller_function_id,
                            target=call_site.callee_function_id,
                            kind='call',
                            call_site_id=call_site.call_site_id,
                            metadata={
                                'line': call_site.line,
                                'operation_id': call_site.operation_id
                            }
                        )
                        inter_edges.append(call_edge)

                        # Create return edge
                        if callee_cfg.exit_node_id:
                            self._inter_edge_counter += 1
                            return_edge = InterproceduralCFGEdge(
                                id=f"inter_return_{self._inter_edge_counter}",
                                source=call_site.callee_function_id,
                                target=call_site.caller_function_id,
                                kind='return',
                                call_site_id=call_site.call_site_id,
                                metadata={
                                    'line': call_site.line,
                                    'operation_id': call_site.operation_id
                                }
                            )
                            inter_edges.append(return_edge)

                        # Create exception propagation edge
                        if callee_cfg.exception_exit_node_id:
                            self._inter_edge_counter += 1
                            exc_edge = InterproceduralCFGEdge(
                                id=f"inter_exception_{self._inter_edge_counter}",
                                source=call_site.callee_function_id,
                                target=call_site.caller_function_id,
                                kind='exception_propagation',
                                call_site_id=call_site.call_site_id,
                                metadata={
                                    'line': call_site.line,
                                    'operation_id': call_site.operation_id
                                }
                            )
                            inter_edges.append(exc_edge)

        return InterproceduralCFG(
            function_cfgs=self._function_cfgs,
            inter_edges=inter_edges,
            entry_points=entry_points,
            metadata={}
        )

    def get_function_cfg(self, function_id: str) -> Optional[ControlFlowGraph]:
        """Get the CFG for a specific function."""
        return self._function_cfgs.get(function_id)

    def get_call_graph(self) -> Dict[str, Set[str]]:
        """
        Extract the call graph from interprocedural edges.

        Returns: caller -> set of callees
        """
        call_graph: Dict[str, Set[str]] = {}

        for edge in self._inter_edges if hasattr(self, '_inter_edges') else []:
            if edge.kind == 'call':
                if edge.source not in call_graph:
                    call_graph[edge.source] = set()
                call_graph[edge.source].add(edge.target)

        return call_graph
