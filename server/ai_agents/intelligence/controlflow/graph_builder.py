"""Graph builder utilities for CFG."""
import json
from .models import ControlFlowGraph


def cfg_to_dict(cfg: ControlFlowGraph) -> dict:
    """Convert CFG to dictionary format for tools."""
    return cfg.to_dict()


def cfg_to_unity_format(cfg: ControlFlowGraph) -> dict:
    """Convert CFG to Unity graph DTO format."""
    nodes = []
    edges = []

    for node in cfg.nodes:
        node_dict = {
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
        }
        nodes.append(node_dict)

    for edge in cfg.edges:
        edges.append({
            'edge_id': edge.id,
            'src': edge.source,
            'dst': edge.target,
            'type': 'controlflow',
            'kind': 'confirmed',
            'edge_kind': edge.kind,
            'resolution': 'static',
            'condition': edge.condition,
            'evidence': json.dumps(edge.evidence or {}),
        })

    return {
        'graph_type': 'control_flow',
        'function_id': cfg.function_id,
        'nodes': nodes,
        'edges': edges,
        'metadata': cfg.metadata,
    }
