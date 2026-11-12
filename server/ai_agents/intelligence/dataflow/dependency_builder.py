"""Data-flow graph builder from reaching definitions analysis."""
from typing import Dict, List, Set, Any, Optional
import json
from ..controlflow.models import ControlFlowGraph
from .models import Definition, VariableUse, DefUseFacts, DataFlowGraph, DataFlowNode, DataFlowEdge, ExpressionFact
from .path_sensitive import PathSensitiveAnalyzer, PathSensitiveResult


class DataFlowGraphBuilder:
    """Build data-flow graphs from CFG and reaching definitions."""

    def __init__(self):
        self._node_counter = 0
        self._edge_counter = 0

    def build(
        self,
        cfg: ControlFlowGraph,
        facts: DefUseFacts,
        analysis_result: Dict[str, Any],
        path_sensitive: bool = False
    ) -> DataFlowGraph:
        """
        Build a data-flow graph from CFG and analysis results.

        Args:
            cfg: Control-flow graph
            facts: Definition-use facts
            analysis_result: Reaching definitions analysis result
            path_sensitive: If True, include phi nodes and must-reaching analysis
        """
        graph = DataFlowGraph(
            function_id=facts.function_id,
            file=facts.file,
        )

        # Optional path-sensitive analysis
        path_sensitive_result: Optional[PathSensitiveResult] = None
        if path_sensitive:
            analyzer = PathSensitiveAnalyzer()
            path_sensitive_result = analyzer.analyze(
                cfg,
                facts,
                analysis_result.get('in_sets', {}),
                analysis_result.get('out_sets', {})
            )

        # Build node mappings
        def_nodes: Dict[str, str] = {}  # definition ID -> graph node ID
        use_nodes: Dict[str, str] = {}  # use ID -> graph node ID
        operation_nodes: Dict[str, str] = {}  # operation ID -> graph node ID

        # Step 1: Add use nodes first (so operation inputs can reference them)
        for use in facts.uses:
            node_id = self._generate_node_id()
            node = DataFlowNode(
                id=node_id,
                kind='use',
                variable=use.variable,
                expression=use.expression,
                function_id=use.function_id,
                file=use.file,
                line=use.line,
                column=use.column,
                cfg_node_ids=use.cfg_node_ids,
                metadata={
                    'use_id': use.id,
                    'binding_key': use.binding_key,
                },
            )
            graph.add_node(node)
            use_nodes[use.id] = node_id

        # Step 2: Add parameter nodes
        param_defs = [d for d in facts.definitions if d.kind == 'parameter']
        for definition in param_defs:
            node_id = self._generate_node_id()
            node = DataFlowNode(
                id=node_id,
                kind='parameter',
                variable=definition.variable,
                expression=definition.expression,
                function_id=definition.function_id,
                file=definition.file,
                line=definition.line,
                column=definition.column,
                cfg_node_ids=definition.cfg_node_ids,
                metadata={
                    'def_id': definition.id,
                    'kind': definition.kind,
                    'binding_key': definition.binding_key,
                },
            )
            graph.add_node(node)
            def_nodes[definition.id] = node_id

        # Step 3: Add definition nodes (non-parameters)
        non_param_defs = [d for d in facts.definitions if d.kind != 'parameter']
        for definition in non_param_defs:
            node_id = self._generate_node_id()
            node = DataFlowNode(
                id=node_id,
                kind='definition',
                variable=definition.variable,
                expression=definition.expression,
                function_id=definition.function_id,
                file=definition.file,
                line=definition.line,
                column=definition.column,
                cfg_node_ids=definition.cfg_node_ids,
                metadata={
                    'def_id': definition.id,
                    'kind': definition.kind,
                    'binding_key': definition.binding_key,
                },
            )
            graph.add_node(node)
            def_nodes[definition.id] = node_id

        # Step 4: Add operation nodes from ExpressionFacts
        for operation in facts.operations:
            node_id = self._generate_node_id()
            node = DataFlowNode(
                id=node_id,
                kind='operation',
                variable=None,
                expression=operation.expression,
                function_id=operation.function_id,
                file=operation.file,
                line=operation.line,
                column=operation.column,
                cfg_node_ids=operation.cfg_node_ids,
                metadata={
                    'operation': operation.operation,
                    'operation_id': operation.id,
                },
            )
            graph.add_node(node)
            operation_nodes[operation.id] = node_id

        # Step 4.5: Add phi nodes if path-sensitive analysis is enabled
        phi_nodes_map: Dict[str, str] = {}  # phi ID -> graph node ID
        if path_sensitive_result:
            for phi in path_sensitive_result.phi_nodes:
                node_id = self._generate_node_id()
                node = DataFlowNode(
                    id=node_id,
                    kind='phi',
                    variable=None,  # Extract from binding_key
                    expression=None,
                    function_id=phi.function_id,
                    file=phi.file,
                    line=phi.line,
                    column=0,
                    cfg_node_ids=[phi.cfg_node_id],
                    metadata={
                        'phi_id': phi.id,
                        'binding_key': phi.binding_key,
                        'incoming_count': len(phi.incoming),
                    },
                )
                graph.add_node(node)
                phi_nodes_map[phi.id] = node_id

            # Connect input uses to operation (use nodes already created)
            for use_id in operation.input_use_ids:
                use_node_id = use_nodes.get(use_id)
                if use_node_id:
                    edge_id = self._generate_edge_id()
                    edge = DataFlowEdge(
                        id=edge_id,
                        source=use_node_id,
                        target=node_id,
                        kind='operand',
                        resolution='static',
                        condition=None,
                        evidence={
                            'file': facts.file,
                            'operation': operation.operation,
                        },
                    )
                    graph.add_edge(edge)

            # Connect input operations to this operation (nested operations)
            for input_op_id in operation.input_operation_ids:
                input_op_node_id = operation_nodes.get(input_op_id)
                if input_op_node_id:
                    edge_id = self._generate_edge_id()
                    edge = DataFlowEdge(
                        id=edge_id,
                        source=input_op_node_id,
                        target=node_id,
                        kind='operand',
                        resolution='static',
                        condition=None,
                        evidence={
                            'file': facts.file,
                            'operation': operation.operation,
                            'nested_operation': True,
                        },
                    )
                    graph.add_edge(edge)

            # Connect operation to output definitions (definition nodes already created)
            for def_id in operation.output_definition_ids:
                def_node_id = def_nodes.get(def_id)
                if def_node_id:
                    edge_id = self._generate_edge_id()
                    edge = DataFlowEdge(
                        id=edge_id,
                        source=node_id,
                        target=def_node_id,
                        kind='produces',
                        resolution='static',
                        condition=None,
                        evidence={
                            'file': facts.file,
                            'operation': operation.operation,
                        },
                    )
                    graph.add_edge(edge)

        # Build edges from reaching definitions
        in_sets = analysis_result.get('in_sets', {})
        node_uses = analysis_result.get('node_uses', {})

        for cfg_node_id, reaching_def_ids in in_sets.items():
            uses_at_node = node_uses.get(cfg_node_id, [])

            for use in uses_at_node:
                use_node_id = use_nodes.get(use.id)
                if not use_node_id:
                    continue

                # Determine if this is a must-reach or may-reach edge
                resolution = 'may_reach'
                condition = None

                if path_sensitive_result:
                    # Check if this definition must-reaches the use
                    must_reaching = path_sensitive_result.must_in_sets.get(cfg_node_id, set())
                    for def_id in reaching_def_ids:
                        if def_id in must_reaching:
                            resolution = 'must_reach'
                            break

                # Find all definitions with the same binding that reach this node
                for def_id in reaching_def_ids:
                    def_node = self._find_definition(facts.definitions, def_id)
                    if def_node and def_node.binding_key == use.binding_key:
                        def_graph_node_id = def_nodes.get(def_id)
                        if def_graph_node_id:
                            # Get edge condition from CFG if available
                            condition = self._get_cfg_edge_condition(cfg, cfg_node_id, use.cfg_node_ids)

                            # Add edge from definition to use
                            edge_id = self._generate_edge_id()
                            edge = DataFlowEdge(
                                id=edge_id,
                                source=def_graph_node_id,
                                target=use_node_id,
                                kind='reaches',
                                resolution=resolution,
                                condition=condition,
                                evidence={
                                    'file': facts.file,
                                    'cfg_node': cfg_node_id,
                                    'binding_key': use.binding_key,
                                },
                            )
                            graph.add_edge(edge)

        # Add phi edges if path-sensitive analysis is enabled
        if path_sensitive_result:
            for phi_edge in path_sensitive_result.phi_edges:
                # Map definition/phi IDs to graph node IDs
                source_id = phi_edge.source
                target_id = phi_edge.target

                # Check if source is a definition or phi node
                source_graph_id = def_nodes.get(source_id) or phi_nodes_map.get(source_id)
                target_graph_id = def_nodes.get(target_id) or use_nodes.get(target_id) or phi_nodes_map.get(target_id)

                if source_graph_id and target_graph_id:
                    edge_id = self._generate_edge_id()
                    edge = DataFlowEdge(
                        id=edge_id,
                        source=source_graph_id,
                        target=target_graph_id,
                        kind=phi_edge.kind,
                        resolution=phi_edge.resolution,
                        condition=phi_edge.condition,
                        evidence=phi_edge.evidence,
                    )
                    graph.add_edge(edge)

        # Add return edges using reaching definitions
        in_sets = analysis_result.get('in_sets', {})
        node_uses = analysis_result.get('node_uses', {})

        for cfg_node_id, reaching_def_ids in in_sets.items():
            # Check if this CFG node is a return node
            cfg_node = cfg.get_node(cfg_node_id)
            if not cfg_node or cfg_node.kind != 'return':
                continue

            uses_at_node = node_uses.get(cfg_node_id, [])

            for use in uses_at_node:
                use_node_id = use_nodes.get(use.id)
                if not use_node_id:
                    continue

                # Determine if this is a must-reach edge
                resolution = 'may_reach'
                if path_sensitive_result:
                    must_reaching = path_sensitive_result.must_in_sets.get(cfg_node_id, set())
                    for def_id in reaching_def_ids:
                        if def_id in must_reaching:
                            resolution = 'must_reach'
                            break

                # Find all definitions with the same binding that reach this return node
                for def_id in reaching_def_ids:
                    def_node = self._find_definition(facts.definitions, def_id)
                    if def_node and def_node.binding_key == use.binding_key:
                        def_graph_node_id = def_nodes.get(def_id)
                        if def_graph_node_id:
                            # Add return edge from definition to use in return
                            edge_id = self._generate_edge_id()
                            edge = DataFlowEdge(
                                id=edge_id,
                                source=def_graph_node_id,
                                target=use_node_id,
                                kind='returns',
                                resolution=resolution,
                                condition=None,
                                evidence={
                                    'file': facts.file,
                                    'cfg_node': cfg_node_id,
                                    'binding_key': use.binding_key,
                                },
                            )
                            graph.add_edge(edge)

        # fact id -> DFG node id, so interprocedural edges can name the
        # graph nodes their use/definition endpoints became.
        fact_to_node = {}
        for use_id, node_id in use_nodes.items():
            fact_to_node[use_id] = node_id
        for def_id, node_id in def_nodes.items():
            fact_to_node[def_id] = node_id
        for op_id, node_id in operation_nodes.items():
            fact_to_node[op_id] = node_id

        graph.metadata = {
            'language': 'python',
            'scope': 'intra_function',
            'definition_count': len(facts.definitions),
            'use_count': len(facts.uses),
            'operation_count': len(facts.operations),
            'path_sensitive': path_sensitive,
            'phi_node_count': len(path_sensitive_result.phi_nodes) if path_sensitive_result else 0,
            'fact_to_node': fact_to_node,
        }

        return graph

    def validate_dataflow_graph(
        self,
        cfg: ControlFlowGraph,
        facts: DefUseFacts,
        graph: DataFlowGraph
    ) -> Dict[str, Any]:
        """Validate the data-flow graph."""
        errors = []
        warnings = []

        # Check node uniqueness
        node_ids = [n.id for n in graph.nodes]
        if len(node_ids) != len(set(node_ids)):
            duplicates = [nid for nid in node_ids if node_ids.count(nid) > 1]
            errors.append(f"Duplicate node IDs: {set(duplicates)}")

        # Check edge uniqueness
        edge_ids = [e.id for e in graph.edges]
        if len(edge_ids) != len(set(edge_ids)):
            duplicates = [eid for eid in edge_ids if edge_ids.count(eid) > 1]
            errors.append(f"Duplicate edge IDs: {set(duplicates)}")

        # Check edge references
        node_id_set = set(node_ids)
        for edge in graph.edges:
            if edge.source not in node_id_set:
                errors.append(f"Edge {edge.id} references non-existent source node: {edge.source}")
            if edge.target not in node_id_set:
                errors.append(f"Edge {edge.id} references non-existent target node: {edge.target}")

        # Check source CFG node IDs exist
        cfg_node_ids = {n.id for n in cfg.nodes}
        for node in graph.nodes:
            if node.cfg_node_ids:
                for cfg_node_id in node.cfg_node_ids:
                    if cfg_node_id not in cfg_node_ids:
                        errors.append(f"Node {node.id} references non-existent CFG node: {cfg_node_id}")

        # Check all definitions and uses are mapped
        def_ids = {d.id for d in facts.definitions}
        use_ids = {u.id for u in facts.uses}

        for node in graph.nodes:
            def_id = node.metadata.get('def_id')
            if def_id and def_id not in def_ids:
                errors.append(f"Node {node.id} references non-existent definition: {def_id}")

            use_id = node.metadata.get('use_id')
            if use_id and use_id not in use_ids:
                errors.append(f"Node {node.id} references non-existent use: {use_id}")

        # Check binding consistency
        for edge in graph.edges:
            source_node = next((n for n in graph.nodes if n.id == edge.source), None)
            target_node = next((n for n in graph.nodes if n.id == edge.target), None)
            if source_node and target_node:
                source_binding = source_node.metadata.get('binding_key')
                target_binding = target_node.metadata.get('binding_key')
                if source_binding and target_binding and source_binding != target_binding:
                    warnings.append(f"Edge {edge.id} connects different bindings: {source_binding} -> {target_binding}")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
        }

    def _get_cfg_edge_condition(
        self,
        cfg: ControlFlowGraph,
        cfg_node_id: str,
        use_cfg_node_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get the condition from CFG edges leading to a use.

        Returns a standardized condition dict with 'predicate' and 'polarity'.
        """
        # Find edges from the definition's CFG node to the use's CFG nodes
        for use_cfg_id in use_cfg_node_ids:
            for edge in cfg.edges:
                if edge.source == cfg_node_id and edge.target == use_cfg_id:
                    if edge.condition:
                        # Standardize the condition
                        if isinstance(edge.condition, str):
                            # Try to parse branch conditions
                            if edge.kind == 'true':
                                return {'predicate': edge.condition or 'condition', 'polarity': True}
                            elif edge.kind == 'false':
                                return {'predicate': edge.condition or 'condition', 'polarity': False}
                            else:
                                return {'predicate': edge.condition, 'polarity': True}
                        elif isinstance(edge.condition, dict):
                            # Already structured
                            if 'predicate' in edge.condition and 'polarity' in edge.condition:
                                return edge.condition
                            else:
                                return {
                                    'predicate': edge.condition.get('predicate', 'unknown'),
                                    'polarity': edge.condition.get('polarity', True)
                                }
        return None

    def _find_definition(self, definitions: List[Definition], def_id: str) -> Definition:
        """Find a definition by ID."""
        for definition in definitions:
            if definition.id == def_id:
                return definition
        raise ValueError(f"Definition not found: {def_id}")

    def _generate_node_id(self) -> str:
        """Generate a unique node ID."""
        self._node_counter += 1
        return f"dfg_N{self._node_counter}"

    def _generate_edge_id(self) -> str:
        """Generate a unique edge ID."""
        self._edge_counter += 1
        return f"dfg_E{self._edge_counter}"


def dfg_to_unity_format(dfg: DataFlowGraph) -> dict:
    """Convert data-flow graph to Unity graph DTO format with confidence rendering."""
    nodes = []
    edges = []

    # Initialize confidence renderer
    from .confidence_rendering import ConfidenceRenderer
    renderer = ConfidenceRenderer()

    for node in dfg.nodes:
        nodes.append({
            'id': node.id,
            'name': node.variable or node.kind,
            'file': node.file,
            'start': node.line,
            'end': node.line,
            'level': 'variable',
            'kind': node.kind,
            'node_kind': node.kind,
            'variable': node.variable,
            'expression': node.expression,
            'function_id': node.function_id,
            'line': node.line,
            'column': node.column,
            'metadata': node.metadata,
            # Source span metadata
            'start_line': node.line,
            'start_col': node.column or 0,
            'end_line': node.line,
            'end_col': node.column or 0,
        })

    for edge in dfg.edges:
        # Determine confidence level from edge resolution
        confidence = 'may_reach'
        if edge.resolution == 'must':
            confidence = 'must_reach'
        elif edge.resolution == 'static':
            confidence = 'may_reach'
        elif edge.resolution == 'dynamic':
            confidence = 'possible'
        elif edge.resolution == 'unknown':
            confidence = 'unknown'

        edge_dict = {
            'edge_id': edge.id,
            'src': edge.source,
            'dst': edge.target,
            'type': 'dataflow',
            'kind': confidence,  # Use confidence instead of hardcoded 'confirmed'
            'edge_kind': edge.kind,
            'resolution': edge.resolution,
            'condition': edge.condition,
            'evidence': json.dumps(edge.evidence or {}),
            'subkind': confidence,  # For confidence renderer
        }

        # Apply visual style from confidence renderer
        edge_dict['visual_style'] = renderer.get_style(confidence).__dict__

        edges.append(edge_dict)

    return {
        'graph_type': 'data_flow',
        'function_id': dfg.function_id,
        'nodes': nodes,
        'edges': edges,
        'metadata': dfg.metadata,
    }
