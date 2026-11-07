"""DFG validation utilities - strict validation."""
from typing import List, Dict, Any, Set, Optional
from .models import DataFlowGraph, DataFlowNode, DataFlowEdge, DefUseFacts, Definition, VariableUse, ExpressionFact


def validate_dfg(dfg: DataFlowGraph, facts: DefUseFacts, cfg=None) -> Dict[str, Any]:
    """
    Strict validation of a data-flow graph.
    
    Args:
        dfg: DataFlowGraph object to validate
        facts: DefUseFacts containing definitions, uses, and operations
        cfg: Optional ControlFlowGraph for CFG node reference validation
    
    Returns:
        Dict with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings = []

    # Ensure both DFG and facts are provided
    if dfg is None:
        errors.append("DFG is None")
        return {'valid': False, 'errors': errors, 'warnings': warnings}
    
    if facts is None:
        errors.append("Facts is None")
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    # Handle both DFG object and dict
    if isinstance(dfg, dict):
        nodes = dfg.get('nodes', [])
        edges = dfg.get('edges', [])
        node_ids = [n.get('id') for n in nodes]
        edge_ids = [e.get('id') for e in edges]
        function_id = dfg.get('function_id')
    else:
        nodes = dfg.nodes
        edges = dfg.edges
        node_ids = [n.id for n in nodes]
        edge_ids = [e.id for e in edges]
        function_id = dfg.function_id

    # Check node uniqueness
    if len(node_ids) != len(set(node_ids)):
        duplicates = [nid for nid in node_ids if node_ids.count(nid) > 1]
        errors.append(f"Duplicate DFG node IDs: {set(duplicates)}")

    # Check edge uniqueness
    if len(edge_ids) != len(set(edge_ids)):
        duplicates = [eid for eid in edge_ids if edge_ids.count(eid) > 1]
        errors.append(f"Duplicate DFG edge IDs: {set(duplicates)}")

    # Check edge references
    node_id_set = set(node_ids)
    for edge in edges:
        if edge.source not in node_id_set:
            errors.append(f"DFG edge {edge.id} references non-existent source node: {edge.source}")
        if edge.target not in node_id_set:
            errors.append(f"DFG edge {edge.id} references non-existent target node: {edge.target}")

    # Check that all facts have valid CFG node references
    for definition in facts.definitions:
        if not definition.cfg_node_ids:
            errors.append(f"Definition {definition.id} has no CFG node IDs")
        for cfg_node_id in definition.cfg_node_ids:
            # Can't validate CFG node exists without CFG, but we can check format
            if not isinstance(cfg_node_id, str):
                errors.append(f"Definition {definition.id} has invalid CFG node ID type: {type(cfg_node_id)}")
            elif cfg is not None:
                # Validate that the CFG node actually exists
                cfg_node_ids_set = {node.id for node in cfg.nodes}
                if cfg_node_id not in cfg_node_ids_set:
                    errors.append(f"Definition {definition.id} references non-existent CFG node: {cfg_node_id}")

    for use in facts.uses:
        if not use.cfg_node_ids:
            errors.append(f"Use {use.id} has no CFG node IDs")
        for cfg_node_id in use.cfg_node_ids:
            if not isinstance(cfg_node_id, str):
                errors.append(f"Use {use.id} has invalid CFG node ID type: {type(cfg_node_id)}")
            elif cfg is not None:
                cfg_node_ids_set = {node.id for node in cfg.nodes}
                if cfg_node_id not in cfg_node_ids_set:
                    errors.append(f"Use {use.id} references non-existent CFG node: {cfg_node_id}")

    for operation in facts.operations:
        if not operation.cfg_node_ids:
            errors.append(f"Operation {operation.id} has no CFG node IDs")
        for cfg_node_id in operation.cfg_node_ids:
            if not isinstance(cfg_node_id, str):
                errors.append(f"Operation {operation.id} has invalid CFG node ID type: {type(cfg_node_id)}")
            elif cfg is not None:
                cfg_node_ids_set = {node.id for node in cfg.nodes}
                if cfg_node_id not in cfg_node_ids_set:
                    errors.append(f"Operation {operation.id} references non-existent CFG node: {cfg_node_id}")

    # Check binding key consistency
    binding_keys = set()
    for definition in facts.definitions:
        if not definition.binding_key:
            errors.append(f"Definition {definition.id} has no binding_key")
        else:
            if not isinstance(definition.binding_key, str):
                errors.append(f"Definition {definition.id} has non-string binding_key: {type(definition.binding_key)}")
            binding_keys.add(definition.binding_key)

    for use in facts.uses:
        if not use.binding_key:
            errors.append(f"Use {use.id} has no binding_key")
        else:
            if not isinstance(use.binding_key, str):
                errors.append(f"Use {use.id} has non-string binding_key: {type(use.binding_key)}")
            # Check that use references a valid binding
            if use.binding_key not in binding_keys:
                warnings.append(f"Use {use.id} references binding_key with no definition: {use.binding_key}")

    # Check operation input/output references
    operation_ids = {op.id for op in facts.operations}
    definition_ids = {defn.id for defn in facts.definitions}
    use_ids = {use.id for use in facts.uses}

    for operation in facts.operations:
        for input_use_id in operation.input_use_ids:
            if input_use_id not in use_ids:
                errors.append(f"Operation {operation.id} references non-existent use: {input_use_id}")
        for output_def_id in operation.output_definition_ids:
            if output_def_id not in definition_ids:
                errors.append(f"Operation {operation.id} references non-existent definition: {output_def_id}")

    # Check that every definition has at least one reaching use (unless it's a parameter or global)
    for definition in facts.definitions:
        if definition.kind not in ('parameter', 'global', 'nonlocal', 'exception_handler'):
            # Check if this definition is used
            uses_of_binding = [u for u in facts.uses if u.binding_key == definition.binding_key]
            if not uses_of_binding:
                warnings.append(f"Definition {definition.id} (kind={definition.kind}) may be unused")

    # Check for duplicate definitions at same location
    location_defs = {}
    for definition in facts.definitions:
        loc_key = (definition.line, definition.column, definition.binding_key)
        if loc_key not in location_defs:
            location_defs[loc_key] = []
        location_defs[loc_key].append(definition)

    for loc_key, defs in location_defs.items():
        if len(defs) > 1:
            warnings.append(f"Multiple definitions at same location {loc_key}: {[d.id for d in defs]}")

    # Validate operation input/output direction
    for operation in facts.operations:
        # Check that input_operation_ids are valid
        for input_op_id in operation.input_operation_ids:
            if input_op_id not in [op.id for op in facts.operations]:
                errors.append(f"Operation {operation.id} references non-existent operation: {input_op_id}")

        # Check that output definitions are genuinely produced by this operation
        for output_def_id in operation.output_definition_ids:
            if output_def_id not in [d.id for d in facts.definitions]:
                errors.append(f"Operation {operation.id} references non-existent definition: {output_def_id}")

    # Check for single source-level definition identity across cloned CFG nodes (finally cloning)
    # Track source-level definitions that appear multiple times in CFG
    source_level_defs = {}
    for definition in facts.definitions:
        source_key = (definition.line, definition.column, definition.binding_key)
        if source_key not in source_level_defs:
            source_level_defs[source_key] = []
        source_level_defs[source_key].append(definition)

    for source_key, defs in source_level_defs.items():
        if len(defs) > 1:
            # Multiple CFG nodes for same source-level definition (e.g., cloned finally)
            # This is OK as long as they represent the same logical definition
            # Verify they have the same binding_key
            binding_keys = {d.binding_key for d in defs}
            if len(binding_keys) > 1:
                errors.append(f"Source-level definition at {source_key} has inconsistent binding keys: {binding_keys}")
    
    # M7: Additional DFG validator semantic relationship checks
    # Check for fabricated IDs
    all_ids = set()
    for definition in facts.definitions:
        if definition.id in all_ids:
            errors.append(f"Duplicate definition ID: {definition.id}")
        all_ids.add(definition.id)
    for use in facts.uses:
        if use.id in all_ids:
            errors.append(f"Duplicate use ID: {use.id}")
        all_ids.add(use.id)
    for operation in facts.operations:
        if operation.id in all_ids:
            errors.append(f"Duplicate operation ID: {operation.id}")
        all_ids.add(operation.id)
    
    # Check return-value provenance
    return_operations = [op for op in facts.operations if op.metadata.get('is_return_sink', False)]
    for return_op in return_operations:
        if return_op.metadata.get('root_operation_id'):
            # Check that the referenced operation exists
            if return_op.metadata['root_operation_id'] not in operation_ids:
                errors.append(f"Return operation {return_op.id} references non-existent operation: {return_op.metadata['root_operation_id']}")
    
    # Check copy/literal relationships
    for definition in facts.definitions:
        if definition.metadata.get('is_copy'):
            if not definition.metadata.get('source_use_id') and not definition.metadata.get('source_variable'):
                warnings.append(f"Definition {definition.id} marked as copy but missing source information")
        if definition.metadata.get('is_literal'):
            if not definition.metadata.get('literal_value'):
                warnings.append(f"Definition {definition.id} marked as literal but missing literal value")
    
    # Check mutation relationships
    for operation in facts.operations:
        if operation.metadata.get('side_effect') == 'known_mutation':
            if not operation.metadata.get('mutation_kind'):
                warnings.append(f"Operation {operation.id} has known_mutation side effect but missing mutation_kind")
    
    # Check deletion kill-only behavior
    for definition in facts.definitions:
        if definition.metadata.get('is_kill_only'):
            if definition.kind != 'exception_variable_clear' and definition.kind != 'deletion':
                warnings.append(f"Definition {definition.id} marked as kill_only but kind is {definition.kind}")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
    }
