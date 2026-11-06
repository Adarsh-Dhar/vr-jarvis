"""Graph builder utilities for CFG."""
from .models import ControlFlowGraph


def cfg_to_dict(cfg: ControlFlowGraph) -> dict:
    """Convert CFG to dictionary format for tools."""
    return cfg.to_dict()


def cfg_to_unity_format(cfg: ControlFlowGraph) -> dict:
    """Convert CFG to Unity graph DTO format."""
    nodes = []
    edges = []

    for node in cfg.nodes:
        nodes.append({
            'id': node.id,
            'name': node.label,
            'file': node.file,
            'start': node.start_line,
            'end': node.end_line,
            'level': 'block',
            'kind': node.kind,
            'cluster': 'control_flow',
            'node_kind': node.kind,
            'ast_kind': node.ast_kind,
            'function_id': node.function_id,
            'condition': node.condition,
            'metadata': node.metadata,
        })

    for edge in cfg.edges:
        edges.append({
            'src': edge.source,
            'dst': edge.target,
            'type': 'controlflow',
            'kind': 'confirmed',
            'edge_kind': edge.kind,
            'condition': edge.condition,
            'evidence': edge.evidence,
        })

    return {
        'graph_type': 'control_flow',
        'function_id': cfg.function_id,
        'nodes': nodes,
        'edges': edges,
        'metadata': cfg.metadata,
    }
