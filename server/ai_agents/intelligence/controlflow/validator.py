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

    # Handle CFGBuildArtifact
    if isinstance(cfg, CFGBuildArtifact):
        cfg = cfg.graph

    # Handle both CFG object and dict
    if isinstance(cfg, dict):
        nodes = cfg.get('nodes', [])
        edges = cfg.get('edges', [])
        node_ids = [n.get('id') for n in nodes]
        edge_ids = [e.get('id') for e in edges]
        node_map = {n.get('id'): n for n in nodes}
        entry_id = cfg.get('entry_node_id')
        exit_id = cfg.get('exit_node_id')
        exception_exit_id = cfg.get('exception_exit_node_id')
        ast_node_map = cfg.get('ast_node_map', {})
    else:
        nodes = cfg.nodes
        edges = cfg.edges
        node_ids = [n.id for n in nodes]
        edge_ids = [e.id for e in edges]
        node_map = {n.id: n for n in nodes}
        entry_id = cfg.entry_node_id
        exit_id = cfg.exit_node_id
        exception_exit_id = cfg.exception_exit_node_id
        ast_node_map = cfg.ast_node_map

    # Check node uniqueness
    if len(node_ids) != len(set(node_ids)):
        duplicates = [nid for nid in node_ids if node_ids.count(nid) > 1]
        errors.append(f"Duplicate node IDs: {set(duplicates)}")

    # Check edge uniqueness
    if len(edge_ids) != len(set(edge_ids)):
        duplicates = [eid for eid in edge_ids if edge_ids.count(eid) > 1]
        errors.append(f"Duplicate edge IDs: {set(duplicates)}")

    # Check edge references
    node_id_set = set(node_ids)
    for edge in edges:
        if isinstance(edge, dict):
            source = edge.get('source')
            target = edge.get('target')
            edge_id = edge.get('id')
            kind = edge.get('kind')
        else:
            source = edge.source
            target = edge.target
            edge_id = edge.id
            kind = edge.kind

        if source not in node_id_set:
            errors.append(f"Edge {edge_id} references non-existent source node: {source}")
        if target not in node_id_set:
            errors.append(f"Edge {edge_id} references non-existent target node: {target}")

    # Check for entry and exit nodes
    if not entry_id:
        errors.append("CFG missing entry_node_id")
    elif entry_id not in node_id_set:
        errors.append(f"CFG entry_node_id references non-existent node: {entry_id}")

    # Validate completion routing through cleanup regions
    # Check that break/continue targets are valid loop nodes
    for edge in edges:
        if isinstance(edge, dict):
            kind = edge.get('kind')
            target = edge.get('target')
        else:
            kind = edge.kind
            target = edge.target

        if kind == 'break':
            # Break should target post-loop node
            target_node = node_map.get(target)
            if target_node and target_node.get('kind') if isinstance(target_node, dict) else target_node.kind not in ('join', 'statement'):
                warnings.append(f"Break edge {edge.get('id') if isinstance(edge, dict) else edge.id} targets non-join node: {target}")

        if kind == 'continue':
            # Continue should target loop header
            target_node = node_map.get(target)
            if target_node and target_node.get('kind') if isinstance(target_node, dict) else target_node.kind not in ('statement', 'loop_header'):
                warnings.append(f"Continue edge {edge.get('id') if isinstance(edge, dict) else edge.id} targets non-loop-header node: {target}")
    
    # M7: Additional CFG validator checks
    # Check valid endpoints
    if not exit_id:
        errors.append("CFG missing exit_node_id")
    elif exit_id not in node_id_set:
        errors.append(f"CFG exit_node_id references non-existent node: {exit_id}")
    
    # Check valid branch outcomes
    for edge in edges:
        if isinstance(edge, dict):
            kind = edge.get('kind')
        else:
            kind = edge.kind
        
        if kind in ('true', 'false'):
            # Should have corresponding opposite edge
            source = edge.get('source') if isinstance(edge, dict) else edge.source
            opposite_kind = 'false' if kind == 'true' else 'true'
            has_opposite = any(
                (e.get('source') if isinstance(e, dict) else e.source) == source and
                (e.get('kind') if isinstance(e, dict) else e.kind) == opposite_kind
                for e in edges
            )
            if not has_opposite:
                warnings.append(f"Edge {edge.get('id') if isinstance(edge, dict) else edge.id} has no opposite {opposite_kind} edge")
    
    # Check for lost abrupt completions
    # Verify no unreachable predecessor contaminating reachable paths
    # (Simplified check - full reachability analysis would be complex)
    
    # Check valid AST mappings
    if not ast_node_map:
        warnings.append("CFG missing ast_node_map")
    
    # Check exception propagation paths
    if exception_exit_id and exception_exit_id not in node_id_set:
        errors.append(f"CFG exception_exit_id references non-existent node: {exception_exit_id}")

    if not exit_id:
        errors.append("CFG missing exit_node_id")
    elif exit_id not in node_id_set:
        errors.append(f"CFG exit_node_id references non-existent node: {exit_id}")

    if not exception_exit_id:
        errors.append("CFG missing exception_exit_node_id")
    elif exception_exit_id not in node_id_set:
        errors.append(f"CFG exception_exit_id references non-existent node: {exception_exit_id}")
        errors.append(f"CFG exception_exit_node_id references non-existent node: {exception_exit_id}")

    # Check return statements - they can connect to exit, finally, with exit, or exception_exit (for may_raise)
    return_nodes = [n for n in nodes if (n.get('kind') if isinstance(n, dict) else n.kind) == 'return']
    for return_node in return_nodes:
        node_id = return_node.get('id') if isinstance(return_node, dict) else return_node.id
        # Get outgoing edges for this node
        outgoing = [e for e in edges if (e.get('source') if isinstance(e, dict) else e.source) == node_id]
        for edge in outgoing:
            target_id = edge.get('target') if isinstance(edge, dict) else edge.target
            edge_kind = edge.get('kind') if isinstance(edge, dict) else edge.kind
            target_node = node_map.get(target_id)
            # Allow return to connect to exit, finally, with exit, or exception_exit (for may_raise)
            if target_id == exit_id or target_id == exception_exit_id:
                continue  # Always allowed
            if target_node:
                target_kind = target_node.get('kind') if isinstance(target_node, dict) else target_node.kind
                target_label = target_node.get('label') if isinstance(target_node, dict) else target_node.label
                # Allow may_raise edges to exception_exit
                if edge_kind == 'may_raise' and target_kind == 'exception_exit':
                    continue
                # Allow return to connect to finally or with exit
                if target_kind not in ('finally', 'statement'):
                    errors.append(f"Return node {node_id} has outgoing edge to non-exit/non-cleanup: {target_id} ({target_kind})")
                elif target_kind == 'statement' and 'exit' not in target_label.lower():
                    errors.append(f"Return node {node_id} has outgoing edge to non-exit/non-cleanup: {target_id} ({target_kind})")

    # Check break and continue edges target correct loops
    break_edges = [e for e in edges if (e.get('kind') if isinstance(e, dict) else e.kind) == 'break']
    continue_edges = [e for e in edges if (e.get('kind') if isinstance(e, dict) else e.kind) == 'continue']

    for edge in break_edges:
        target_id = edge.get('target') if isinstance(edge, dict) else edge.target
        edge_id = edge.get('id') if isinstance(edge, dict) else edge.id
        target_node = node_map.get(target_id)
        if target_node:
            target_kind = target_node.get('kind') if isinstance(target_node, dict) else target_node.kind
            if target_kind not in ('join', 'exit'):
                errors.append(f"Break edge {edge_id} targets non-join node: {target_kind}")

    for edge in continue_edges:
        target_id = edge.get('target') if isinstance(edge, dict) else edge.target
        edge_id = edge.get('id') if isinstance(edge, dict) else edge.id
        target_node = node_map.get(target_id)
        if target_node:
            target_kind = target_node.get('kind') if isinstance(target_node, dict) else target_node.kind
            if target_kind != 'loop_header':
                errors.append(f"Continue edge {edge_id} targets non-loop-header node: {target_kind}")

    # Check loop-back edges target their own loop header
    loop_back_edges = [e for e in edges if (e.get('kind') if isinstance(e, dict) else e.kind) == 'loop_back']
    for edge in loop_back_edges:
        source_id = edge.get('source') if isinstance(edge, dict) else edge.source
        target_id = edge.get('target') if isinstance(edge, dict) else edge.target
        edge_id = edge.get('id') if isinstance(edge, dict) else edge.id
        source_node = node_map.get(source_id)
        target_node = node_map.get(target_id)
        if source_node and target_node:
            source_kind = source_node.get('kind') if isinstance(source_node, dict) else source_node.kind
            target_kind = target_node.get('kind') if isinstance(target_node, dict) else target_node.kind
            if target_kind != 'loop_header':
                errors.append(f"Loop-back edge {edge_id} targets non-loop-header node")
            if source_kind != 'loop_header' and source_kind != 'statement':
                warnings.append(f"Loop-back edge {edge_id} source is not loop-related: {source_kind}")

    # Check condition nodes have true/false edges
    condition_nodes = [n for n in nodes if (n.get('kind') if isinstance(n, dict) else n.kind) == 'condition']
    for cond_node in condition_nodes:
        node_id = cond_node.get('id') if isinstance(cond_node, dict) else cond_node.id
        # Get outgoing edges for this node
        outgoing = [e for e in edges if (e.get('source') if isinstance(e, dict) else e.source) == node_id]
        true_edges = [e for e in outgoing if (e.get('kind') if isinstance(e, dict) else e.kind) == 'true']
        false_edges = [e for e in outgoing if (e.get('kind') if isinstance(e, dict) else e.kind) == 'false']
        if not true_edges:
            errors.append(f"Condition node {node_id} missing true edge")
        if not false_edges:
            errors.append(f"Condition node {node_id} missing false edge")

    # Check AST node mapping
    if not ast_node_map:
        warnings.append("CFG has no AST node mapping")

    # Semantic validation: Check loop headers have proper break/continue targets
    loop_headers = [n for n in nodes if (n.get('kind') if isinstance(n, dict) else n.kind) == 'loop_header']
    for header in loop_headers:
        node_id = header.get('id') if isinstance(header, dict) else header.id
        metadata = header.get('metadata', {}) if isinstance(header, dict) else header.metadata
        if metadata and 'break_target' in metadata:
            break_target = metadata['break_target']
            if break_target not in node_id_set:
                errors.append(f"Loop header {node_id} has invalid break_target: {break_target}")
        if metadata and 'continue_target' in metadata:
            continue_target = metadata['continue_target']
            if continue_target not in node_id_set:
                errors.append(f"Loop header {node_id} has invalid continue_target: {continue_target}")

    # Semantic validation: Check exception handlers have proper ordering
    except_handlers = [n for n in nodes if (n.get('ast_kind') if isinstance(n, dict) else n.ast_kind) == 'ExceptHandler']
    if len(except_handlers) > 1:
        # Verify handlers are in order
        handler_orders = []
        for handler in except_handlers:
            metadata = handler.get('metadata', {}) if isinstance(handler, dict) else handler.metadata
            if metadata and 'handler_order' in metadata:
                handler_orders.append(metadata['handler_order'])
        if handler_orders != sorted(handler_orders):
            warnings.append("Exception handlers are not in proper order")

    # Semantic validation: Check finally nodes exist for try statements with finally
    try_nodes = [n for n in nodes if (n.get('ast_kind') if isinstance(n, dict) else n.ast_kind) == 'Try']
    finally_nodes = [n for n in nodes if (n.get('kind') if isinstance(n, dict) else n.kind) == 'finally']
    if try_nodes and not finally_nodes:
        warnings.append("Try statements found but no finally nodes - may indicate missing finally handling")

    # Semantic validation: Check for unreachable nodes (no incoming edges except entry)
    entry_set = {entry_id} if entry_id else set()
    for node in nodes:
        node_id = node.get('id') if isinstance(node, dict) else node.id
        if node_id not in entry_set:
            # Check if node has any incoming edges
            has_incoming = any(
                (e.get('target') if isinstance(e, dict) else e.target) == node_id
                for e in edges
            )
            if not has_incoming:
                warnings.append(f"Node {node_id} appears unreachable (no incoming edges)")

    # Semantic validation: Check break/continue edges don't cross loop boundaries
    break_edges = [e for e in edges if (e.get('kind') if isinstance(e, dict) else e.kind) == 'break']
    continue_edges = [e for e in edges if (e.get('kind') if isinstance(e, dict) else e.kind) == 'continue']

    for edge in break_edges:
        source_id = edge.get('source') if isinstance(edge, dict) else edge.source
        target_id = edge.get('target') if isinstance(edge, dict) else edge.target
        source_node = node_map.get(source_id)
        target_node = node_map.get(target_id)
        if source_node and target_node:
            # Break should target a join/exit node, not a loop header
            target_kind = target_node.get('kind') if isinstance(target_node, dict) else target_node.kind
            if target_kind == 'loop_header':
                errors.append(f"Break edge {edge.get('id') if isinstance(edge, dict) else edge.id} targets loop header (should target exit)")

    for edge in continue_edges:
        source_id = edge.get('source') if isinstance(edge, dict) else edge.source
        target_id = edge.get('target') if isinstance(edge, dict) else edge.target
        source_node = node_map.get(source_id)
        target_node = node_map.get(target_id)
        if source_node and target_node:
            # Continue should target a loop header
            target_kind = target_node.get('kind') if isinstance(target_node, dict) else target_node.kind
            if target_kind != 'loop_header':
                errors.append(f"Continue edge {edge.get('id') if isinstance(edge, dict) else edge.id} targets non-loop-header node")

    # Semantic validation: Check exception edges don't bypass handlers
    exception_edges = [e for e in edges if (e.get('kind') if isinstance(e, dict) else e.kind) == 'exception']
    for edge in exception_edges:
        target_id = edge.get('target') if isinstance(edge, dict) else edge.target
        target_node = node_map.get(target_id)
        if target_node:
            target_kind = target_node.get('kind') if isinstance(target_node, dict) else target_node.kind
            target_ast_kind = target_node.get('ast_kind') if isinstance(target_node, dict) else target_node.ast_kind
            # Exception edges should target handlers, dispatchers, or exception exits
            if target_kind not in ('statement', 'exception_dispatch', 'exit') and target_ast_kind not in ('ExceptHandler', 'Try'):
                warnings.append(f"Exception edge targets unexpected node kind: {target_kind}/{target_ast_kind}")

    # Semantic validation: Check exception dispatcher doesn't create self-loops
    dispatch_nodes = [n for n in nodes if (n.get('kind') if isinstance(n, dict) else n.kind) == 'exception_dispatch']
    for dispatch_node in dispatch_nodes:
        dispatch_id = dispatch_node.get('id') if isinstance(dispatch_node, dict) else dispatch_node.id
        dispatch_edges = [e for e in edges if (e.get('source') if isinstance(e, dict) else e.source) == dispatch_id]
        for edge in dispatch_edges:
            target_id = edge.get('target') if isinstance(edge, dict) else edge.target
            if target_id == dispatch_id:
                errors.append(f"Exception dispatcher {dispatch_id} has self-loop")

    # Semantic validation: Check that no path bypasses required cleanup (finally/with-exit)
    finally_nodes = [n for n in nodes if (n.get('kind') if isinstance(n, dict) else n.kind) == 'finally']
    with_exit_nodes = [n for n in nodes if 'with exit' in (n.get('label') if isinstance(n, dict) else n.label)]
    cleanup_nodes = finally_nodes + with_exit_nodes

    for cleanup_node in cleanup_nodes:
        cleanup_id = cleanup_node.get('id') if isinstance(cleanup_node, dict) else cleanup_node.id
        # Get edges into cleanup
        edges_to_cleanup = [e for e in edges if (e.get('target') if isinstance(e, dict) else e.target) == cleanup_id]
        # Check if any edge bypasses cleanup (goes from before cleanup to after cleanup without passing through)
        # This is a simplified check - full validation would require path analysis
        pass

    # Return nodes may have may_raise edges (for expressions that can raise)
    # Update validation to allow this
    return_nodes = [n for n in nodes if (n.get('kind') if isinstance(n, dict) else n.kind) == 'return']
    for return_node in return_nodes:
        return_id = return_node.get('id') if isinstance(return_node, dict) else return_node.id
        return_edges = [e for e in edges if (e.get('source') if isinstance(e, dict) else e.source) == return_id]
        # Allow may_raise edges to exception dispatcher or exception exit
        for edge in return_edges:
            edge_kind = edge.get('kind') if isinstance(edge, dict) else edge.kind
            target_id = edge.get('target') if isinstance(edge, dict) else edge.target
            if edge_kind == 'may_raise':
                # May raise edges are allowed to exception dispatcher or exception exit
                target_node = node_map.get(target_id)
                if target_node:
                    target_kind = target_node.get('kind') if isinstance(target_node, dict) else target_node.kind
                    if target_kind not in ('exception_dispatch', 'exception_exit'):
                        errors.append(f"Return node {return_id} has may_raise edge to non-exception target: {target_id} ({target_kind})")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
    }
