"""Control-flow graph models for Python analysis."""
import ast
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from .ast_cfg_index import ASTCFGIndex


@dataclass
class CFGNode:
    """A node in the control-flow graph."""
    id: str
    kind: str
    label: str
    function_id: str
    file: str
    start_line: int
    end_line: int
    ast_kind: Optional[str] = None
    condition: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # M6.4: Evaluation/commit separation metadata
    is_evaluation: bool = False  # True for RHS evaluation nodes
    is_commit: bool = False  # True for assignment commit nodes
    # Source span metadata for VR highlighting
    start_col: int = 0
    end_col: int = 0


@dataclass
class CFGEdge:
    """An edge in the control-flow graph."""
    id: str
    source: str
    target: str
    kind: str
    condition: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlFlowGraph:
    """Complete control-flow graph for a function."""
    function_id: str
    file: str
    nodes: List[CFGNode] = field(default_factory=list)
    edges: List[CFGEdge] = field(default_factory=list)
    entry_node_id: Optional[str] = None
    exit_node_id: Optional[str] = None
    exception_exit_node_id: Optional[str] = None
    ast_node_map: Dict[int, str] = field(default_factory=dict, repr=False)
    ast_index: Optional[ASTCFGIndex] = field(default=None, repr=False)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: CFGNode) -> None:
        """Add a node to the graph."""
        self.nodes.append(node)

    def add_edge(self, edge: CFGEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[CFGNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_edges_from(self, node_id: str) -> List[CFGEdge]:
        """Get all edges originating from a node."""
        return [e for e in self.edges if e.source == node_id]

    def get_edges_to(self, node_id: str) -> List[CFGEdge]:
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
                    'label': n.label,
                    'function_id': n.function_id,
                    'file': n.file,
                    'start_line': n.start_line,
                    'end_line': n.end_line,
                    'ast_kind': n.ast_kind,
                    'condition': n.condition,
                    'metadata': n.metadata,
                    'start_col': n.start_col,
                    'end_col': n.end_col,
                }
                for n in self.nodes
            ],
            'edges': [
                {
                    'id': e.id,
                    'source': e.source,
                    'target': e.target,
                    'kind': e.kind,
                    'condition': e.condition,
                    'evidence': e.evidence,
                }
                for e in self.edges
            ],
            'metadata': self.metadata,
        }


@dataclass
class CFGBuildArtifact:
    """Complete CFG build artifact including graph, AST index, and function AST."""
    graph: ControlFlowGraph
    ast_index: ASTCFGIndex
    function_ast: ast.FunctionDef
