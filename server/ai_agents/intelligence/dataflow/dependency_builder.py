"""Data-flow graph builder from reaching definitions analysis."""
from typing import Dict, List, Set, Any
import json
from ..controlflow.models import ControlFlowGraph
from .models import Definition, VariableUse, DefUseFacts, DataFlowGraph, DataFlowNode, DataFlowEdge, ExpressionFact


class DataFlowGraphBuilder:
    """Build data-flow graphs from CFG and reaching definitions."""

    def __init__(self):
        self._node_counter = 0
        self._edge_counter = 0

    def build(
        self,
        cfg: ControlFlowGraph,
        facts: DefUseFacts,
        analysis_result: Dict[str, Any]
    ) -> DataFlowGraph:
        """Build a data-flow graph from CFG and analysis results."""
        graph = DataFlowGraph(
            function_id=facts.function_id,
            file=facts.file,
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

                # Find all definitions with the same binding that reach this node
                for def_id in reaching_def_ids:
                    def_node = self._find_definition(facts.definitions, def_id)
                    if def_node and def_node.binding_key == use.binding_key:
                        def_graph_node_id = def_nodes.get(def_id)
                        if def_graph_node_id:
                            # Add edge from definition to use
                            edge_id = self._generate_edge_id()
                            edge = DataFlowEdge(
                                id=edge_id,
                                source=def_graph_node_id,
                                target=use_node_id,
                                kind='reaches',
                                resolution='may_reach',
                                condition=None,
                                evidence={
                                    'file': facts.file,
                                    'cfg_node': cfg_node_id,
                                    'binding_key': use.binding_key,
                                },
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
                                resolution='may_reach',
                                condition=None,
                                evidence={
                                    'file': facts.file,
                                    'cfg_node': cfg_node_id,
                                    'binding_key': use.binding_key,
                                },
                            )
                            graph.add_edge(edge)

        graph.metadata = {
            'language': 'python',
            'scope': 'intra_function',
            'definition_count': len(facts.definitions),
            'use_count': len(facts.uses),
            'operation_count': len(facts.operations),
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
    """Convert data-flow graph to Unity graph DTO format."""
    nodes = []
    edges = []

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
        })

    for edge in dfg.edges:
        edges.append({
            'edge_id': edge.id,
            'src': edge.source,
            'dst': edge.target,
            'type': 'dataflow',
            'kind': 'confirmed',
            'edge_kind': edge.kind,
            'resolution': edge.resolution,
            'condition': edge.condition,
            'evidence': json.dumps(edge.evidence or {}),
        })

    return {
        'graph_type': 'data_flow',
        'function_id': dfg.function_id,
        'nodes': nodes,
        'edges': edges,
        'metadata': dfg.metadata,
    }
