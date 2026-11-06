"""Data-flow graph builder from reaching definitions analysis."""
from typing import Dict, List, Set
from ..controlflow.models import ControlFlowGraph
from .models import Definition, VariableUse, DefUseFacts, DataFlowGraph, DataFlowNode, DataFlowEdge
from .reaching_definitions import ReachingDefinitionsAnalyzer


class DataFlowGraphBuilder:
    """Build data-flow graphs from CFG and reaching definitions."""

    def __init__(self):
        self.analyzer = ReachingDefinitionsAnalyzer()
        self._node_counter = 0
        self._edge_counter = 0

    def build(
        self,
        cfg: ControlFlowGraph,
        facts: DefUseFacts,
        analysis_result: Dict[str, Set[str]]
    ) -> DataFlowGraph:
        """Build a data-flow graph from CFG and analysis results."""
        graph = DataFlowGraph(
            function_id=facts.function_id,
            file=facts.file,
        )

        # Add definition nodes
        def_nodes: Dict[str, str] = {}  # definition ID -> graph node ID
        for definition in facts.definitions:
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
                cfg_node_id=definition.cfg_node_id,
                metadata={
                    'def_id': definition.id,
                    'kind': definition.kind,
                },
            )
            graph.add_node(node)
            def_nodes[definition.id] = node_id

        # Add use nodes
        use_nodes: Dict[str, str] = {}  # use ID -> graph node ID
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
                cfg_node_id=use.cfg_node_id,
                metadata={
                    'use_id': use.id,
                },
            )
            graph.add_node(node)
            use_nodes[use.id] = node_id

        # Build edges from reaching definitions
        in_sets = analysis_result['in_sets']
        node_uses = analysis_result['node_uses']

        for cfg_node_id, reaching_def_ids in in_sets.items():
            # Get uses at this node
            uses_at_node = node_uses.get(cfg_node_id, [])

            for use in uses_at_node:
                use_node_id = use_nodes.get(use.id)
                if not use_node_id:
                    continue

                # Find all definitions of this variable that reach this node
                for def_id in reaching_def_ids:
                    # Check if this definition is for the same variable
                    def_node = self._find_definition(facts.definitions, def_id)
                    if def_node and def_node.variable == use.variable:
                        def_graph_node_id = def_nodes.get(def_id)
                        if def_graph_node_id:
                            # Add edge from definition to use
                            edge_id = self._generate_edge_id()
                            edge = DataFlowEdge(
                                id=edge_id,
                                source=def_graph_node_id,
                                target=use_node_id,
                                kind='feeds',
                                resolution='may_reach',
                                condition=None,
                                evidence={
                                    'file': facts.file,
                                    'cfg_node': cfg_node_id,
                                },
                            )
                            graph.add_edge(edge)

        # Add operation nodes for complex expressions (simplified)
        # In a full implementation, we'd analyze the AST to find operations
        # and create intermediate nodes for them

        graph.metadata = {
            'language': 'python',
            'scope': 'intra_function',
            'definition_count': len(facts.definitions),
            'use_count': len(facts.uses),
        }

        return graph

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
            'src': edge.source,
            'dst': edge.target,
            'type': 'dataflow',
            'kind': 'confirmed',
            'edge_kind': edge.kind,
            'resolution': edge.resolution,
            'condition': edge.condition,
            'evidence': edge.evidence,
        })

    return {
        'graph_type': 'data_flow',
        'function_id': dfg.function_id,
        'nodes': nodes,
        'edges': edges,
        'metadata': dfg.metadata,
    }
