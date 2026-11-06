"""Data-flow graph models for Python analysis."""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class Definition:
    """A variable definition point."""
    id: str
    variable: str
    function_id: str
    file: str
    line: int
    column: int
    kind: str
    cfg_node_id: str
    binding_key: str
    expression: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VariableUse:
    """A variable use point."""
    id: str
    variable: str
    function_id: str
    file: str
    line: int
    column: int
    cfg_node_id: str
    binding_key: str
    expression: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpressionFact:
    """An expression operation fact."""
    id: str
    function_id: str
    file: str
    line: int
    column: int
    cfg_node_id: str
    expression: str
    operation: str
    input_use_ids: List[str] = field(default_factory=list)
    output_definition_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DefUseFacts:
    """Collected definition-use facts for a function."""
    function_id: str
    file: str
    definitions: List[Definition] = field(default_factory=list)
    uses: List[VariableUse] = field(default_factory=list)
    operations: List[ExpressionFact] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataFlowNode:
    """A node in the data-flow graph."""
    id: str
    kind: str
    function_id: str
    file: str
    line: int
    variable: Optional[str] = None
    expression: Optional[str] = None
    column: int = 0
    cfg_node_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataFlowEdge:
    """An edge in the data-flow graph."""
    id: str
    source: str
    target: str
    kind: str
    resolution: str
    condition: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataFlowGraph:
    """Complete data-flow graph for a function."""
    function_id: str
    file: str
    nodes: List[DataFlowNode] = field(default_factory=list)
    edges: List[DataFlowEdge] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: DataFlowNode) -> None:
        """Add a node to the graph."""
        self.nodes.append(node)

    def add_edge(self, edge: DataFlowEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[DataFlowNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_edges_from(self, node_id: str) -> List[DataFlowEdge]:
        """Get all edges originating from a node."""
        return [e for e in self.edges if e.source == node_id]

    def get_edges_to(self, node_id: str) -> List[DataFlowEdge]:
        """Get all edges pointing to a node."""
        return [e for e in self.edges if e.target == node_id]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'function_id': self.function_id,
            'file': self.file,
            'nodes': [
                {
                    'id': n.id,
                    'kind': n.kind,
                    'variable': n.variable,
                    'expression': n.expression,
                    'function_id': n.function_id,
                    'file': n.file,
                    'line': n.line,
                    'column': n.column,
                    'cfg_node_id': n.cfg_node_id,
                    'metadata': n.metadata,
                }
                for n in self.nodes
            ],
            'edges': [
                {
                    'id': e.id,
                    'source': e.source,
                    'target': e.target,
                    'kind': e.kind,
                    'resolution': e.resolution,
                    'condition': e.condition,
                    'evidence': e.evidence,
                }
                for e in self.edges
            ],
            'metadata': self.metadata,
        }

    def validate(self) -> Dict[str, Any]:
        """Validate the data-flow graph."""
        errors = []
        warnings = []

        # Check node uniqueness
        node_ids = [n.id for n in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            duplicates = [nid for nid in node_ids if node_ids.count(nid) > 1]
            errors.append(f"Duplicate node IDs: {set(duplicates)}")

        # Check edge uniqueness
        edge_ids = [e.id for e in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            duplicates = [eid for eid in edge_ids if edge_ids.count(eid) > 1]
            errors.append(f"Duplicate edge IDs: {set(duplicates)}")

        # Check edge references
        node_id_set = set(node_ids)
        for edge in self.edges:
            if edge.source not in node_id_set:
                errors.append(f"Edge {edge.id} references non-existent source node: {edge.source}")
            if edge.target not in node_id_set:
                errors.append(f"Edge {edge.id} references non-existent target node: {edge.target}")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
        }
