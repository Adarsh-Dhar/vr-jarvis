"""Graph builder utilities for CFG."""
import json
from .models import ControlFlowGraph
from ..dataflow.confidence_rendering import ConfidenceRenderer


def cfg_to_dict(cfg: ControlFlowGraph) -> dict:
    """Convert CFG to dictionary format for tools."""
    return cfg.to_dict()


def cfg_to_unity_format(cfg: ControlFlowGraph) -> dict:
    """Convert CFG to Unity graph DTO format with confidence rendering."""
    nodes = []
    edges = []

    # Initialize confidence renderer
    renderer = ConfidenceRenderer()

    for node in cfg.nodes:
        node_dict = {
            'id': node.id,
            'name': node.label,
            'file': node.file,
            'start': node.start_line,
            'end': node.end_line,
            'line': node.start_line,
            'level': 'block',
            'kind': node.kind,
            'cluster': 'control_flow',
            'node_kind': node.kind,
            'ast_kind': node.ast_kind,
            'function_id': node.function_id,
            'condition': node.condition,
            'metadata': node.metadata,
            # Source span metadata
            'start_line': node.start_line,
            'start_col': getattr(node, 'start_col', 0),
            'end_line': node.end_line,
            'end_col': getattr(node, 'end_col', 0),
        }
        nodes.append(node_dict)

    for edge in cfg.edges:
        # Determine confidence level from edge condition and kind
        confidence = 'may_reach'
        if edge.condition is not None:
            confidence = 'must_reach'
        elif edge.kind in ['true', 'false']:
            confidence = 'must_reach'
        elif edge.kind == 'exception':
            confidence = 'possible'

        edge_dict = {
            'edge_id': edge.id,
            'src': edge.source,
            'dst': edge.target,
            'type': 'controlflow',
            'kind': confidence,  # Use confidence instead of hardcoded 'confirmed'
            'edge_kind': edge.kind,
            'resolution': 'static',
            'condition': edge.condition,
            'evidence': json.dumps(edge.evidence or {}),
            'subkind': confidence,  # For confidence renderer
        }

        # Apply visual style from confidence renderer
        edge_dict['visual_style'] = renderer.get_style(confidence).__dict__

        edges.append(edge_dict)

    return {
        'graph_type': 'control_flow',
        'function_id': cfg.function_id,
        'nodes': nodes,
        'edges': edges,
        'metadata': cfg.metadata,
    }
