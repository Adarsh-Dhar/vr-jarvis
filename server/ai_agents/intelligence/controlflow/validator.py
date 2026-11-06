"""CFG validation utilities."""
from typing import List, Dict, Any, Set
from .models import ControlFlowGraph, CFGNode, CFGEdge


class CFGValidationError(Exception):
    """Raised when CFG validation fails."""

    def __init__(self, message: str, details: Dict[str, Any] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


def validate_cfg(cfg: ControlFlowGraph) -> Dict[str, Any]:
    """
    Validate a control-flow graph.

    Returns a dict with:
    - valid: bool
    - errors: list of error messages
    - warnings: list of warnings
    """
    errors = []
    warnings = []

    # Check node uniqueness
    node_ids = [n.id for n in cfg.nodes]
    if len(node_ids) != len(set(node_ids)):
        duplicates = [nid for nid in node_ids if node_ids.count(nid) > 1]
        errors.append(f"Duplicate node IDs: {set(duplicates)}")

    # Check edge uniqueness
    edge_ids = [e.id for e in cfg.edges]
    if len(edge_ids) != len(set(edge_ids)):
        duplicates = [eid for eid in edge_ids if edge_ids.count(eid) > 1]
        errors.append(f"Duplicate edge IDs: {set(duplicates)}")

    # Check edge references
    node_id_set = set(node_ids)
    for edge in cfg.edges:
        if edge.source not in node_id_set:
            errors.append(f"Edge {edge.id} references non-existent source node: {edge.source}")
        if edge.target not in node_id_set:
            errors.append(f"Edge {edge.id} references non-existent target node: {edge.target}")

    # Check for entry and exit nodes
    entry_nodes = [n for n in cfg.nodes if n.kind == 'entry']
    exit_nodes = [n for n in cfg.nodes if n.kind == 'exit']

    if len(entry_nodes) == 0:
        errors.append("CFG has no entry node")
    elif len(entry_nodes) > 1:
        warnings.append(f"CFG has multiple entry nodes: {len(entry_nodes)}")

    if len(exit_nodes) == 0:
        warnings.append("CFG has no explicit exit node")

    # Check return statements have no successors
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    for return_node in return_nodes:
        outgoing = cfg.get_edges_from(return_node.id)
        if outgoing:
            errors.append(f"Return node {return_node.id} has outgoing edges")

    # Check break and continue edges target correct loops
    break_edges = [e for e in cfg.edges if e.kind == 'break']
    continue_edges = [e for e in cfg.edges if e.kind == 'continue']

    for edge in break_edges:
        target = cfg.get_node(edge.target)
        if target and target.kind not in ('join', 'exit'):
            warnings.append(f"Break edge {edge.id} targets non-join node: {target.kind}")

    for edge in continue_edges:
        target = cfg.get_node(edge.target)
        if target and target.kind != 'loop_header':
            warnings.append(f"Continue edge {edge.id} targets non-loop-header node: {target.kind}")

    # Check loop-back edges target their own loop header
    loop_back_edges = [e for e in cfg.edges if e.kind == 'loop_back']
    for edge in loop_back_edges:
        source = cfg.get_node(edge.source)
        target = cfg.get_node(edge.target)
        if source and target:
            if target.kind != 'loop_header':
                warnings.append(f"Loop-back edge {edge.id} targets non-loop-header node")

    # Check for unreachable nodes (optional, expensive for large graphs)
    if entry_nodes:
        entry_id = entry_nodes[0].id
        reachable = _compute_reachable(cfg, entry_id)
        unreachable = [n.id for n in cfg.nodes if n.id not in reachable]
        if unreachable:
            warnings.append(f"Unreachable nodes: {unreachable}")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
    }


def _compute_reachable(cfg: ControlFlowGraph, start_id: str) -> Set[str]:
    """Compute all nodes reachable from start_id using BFS."""
    reachable = set()
    queue = [start_id]

    while queue:
        current = queue.pop(0)
        if current in reachable:
            continue
        reachable.add(current)

        for edge in cfg.get_edges_from(current):
            if edge.target not in reachable:
                queue.append(edge.target)

    return reachable
