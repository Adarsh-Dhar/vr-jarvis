"""CFG validation utilities - strict validation."""
from typing import List, Dict, Any, Set
from .models import ControlFlowGraph, CFGNode, CFGEdge, CFGBuildArtifact


class CFGValidationError(Exception):
    def __init__(self, message: str, details: Dict[str, Any] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


def validate_cfg(cfg: ControlFlowGraph) -> Dict[str, Any]:
    """
    Strict validation of a control-flow graph.
    """
    errors = []
    warnings = []

    # Handle both CFG object and dict
    # Handle CFGBuildArtifact
    if isinstance(cfg, CFGBuildArtifact):
        cfg = cfg.graph
    if isinstance(cfg, dict):
        nodes = cfg.get('nodes', [])
        edges = cfg.get('edges', [])
        node_ids = [n.get('id') for n in nodes]
        edge_ids = [e.get('id') for e in edges]
        node_map = {n.get('id'): n for n in nodes}
        entry_id = cfg.get('entry_node_id')
        exit_id = cfg.get('exit_node_id')
        exception_exit_id = cfg.get('exception_exit_node_id')
    else:
        nodes = cfg.nodes
        edges = cfg.edges
        node_ids = [n.id for n in nodes]
        edge_ids = [e.id for e in edges]
        node_map = {n.id: n for n in nodes}
        entry_id = cfg.entry_node_id
        exit_id = cfg.exit_node_id
        exception_exit_id = cfg.exception_exit_node_id
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
    if not cfg.entry_node_id:
        errors.append("CFG missing entry_node_id")
    elif cfg.entry_node_id not in node_id_set:
        errors.append(f"CFG entry_node_id references non-existent node: {cfg.entry_node_id}")

    if not cfg.exit_node_id:
        errors.append("CFG missing exit_node_id")
    elif cfg.exit_node_id not in node_id_set:
        errors.append(f"CFG exit_node_id references non-existent node: {cfg.exit_node_id}")

    if not cfg.exception_exit_node_id:
        errors.append("CFG missing exception_exit_node_id")
    elif cfg.exception_exit_node_id not in node_id_set:
        errors.append(f"CFG exception_exit_node_id references non-existent node: {cfg.exception_exit_node_id}")

    # Check return statements - they can connect to exit, finally, or with exit nodes
    return_nodes = [n for n in cfg.nodes if n.kind == 'return']
    for return_node in return_nodes:
        outgoing = cfg.get_edges_from(return_node.id)
        for edge in outgoing:
            target = cfg.get_node(edge.target)
            # Allow return to connect to exit, finally, or with exit node
            if edge.target != cfg.exit_node_id:
                if target and target.kind not in ('finally', 'statement'):
                    errors.append(f"Return node {return_node.id} has outgoing edge to non-exit/non-cleanup: {edge.target} ({target.kind if target else 'unknown'})")
                elif target and target.kind == 'statement' and 'exit' not in target.label.lower():
                    errors.append(f"Return node {return_node.id} has outgoing edge to non-exit/non-cleanup: {edge.target} ({target.kind if target else 'unknown'})")

    # Check break and continue edges target correct loops
    break_edges = [e for e in cfg.edges if e.kind == 'break']
    continue_edges = [e for e in cfg.edges if e.kind == 'continue']

    for edge in break_edges:
        target = cfg.get_node(edge.target)
        if target and target.kind not in ('join', 'exit'):
            errors.append(f"Break edge {edge.id} targets non-join node: {target.kind}")

    for edge in continue_edges:
        target = cfg.get_node(edge.target)
        if target and target.kind != 'loop_header':
            errors.append(f"Continue edge {edge.id} targets non-loop-header node: {target.kind}")

    # Check loop-back edges target their own loop header
    loop_back_edges = [e for e in cfg.edges if e.kind == 'loop_back']
    for edge in loop_back_edges:
        source = cfg.get_node(edge.source)
        target = cfg.get_node(edge.target)
        if source and target:
            if target.kind != 'loop_header':
                errors.append(f"Loop-back edge {edge.id} targets non-loop-header node")
            if source.kind != 'loop_header' and source.kind != 'statement':
                warnings.append(f"Loop-back edge {edge.id} source is not loop-related: {source.kind}")

    # Check condition nodes have true/false edges
    condition_nodes = [n for n in cfg.nodes if n.kind == 'condition']
    for cond_node in condition_nodes:
        outgoing = cfg.get_edges_from(cond_node.id)
        true_edges = [e for e in outgoing if e.kind == 'true']
        false_edges = [e for e in outgoing if e.kind == 'false']
        if not true_edges:
            errors.append(f"Condition node {cond_node.id} missing true edge")
        if not false_edges:
            errors.append(f"Condition node {cond_node.id} missing false edge")

    # Check AST node mapping
    if not cfg.ast_node_map:
        warnings.append("CFG has no AST node mapping")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
    }
