"""Data-flow graph models for Python analysis."""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
import ast


@dataclass
class BindingResolution:
    """Result of binding resolution for a name reference."""
    binding_key: str
    binding_category: str  # 'local', 'global', 'nonlocal', 'free', 'parameter'
    defining_scope: str
    is_external_boundary: bool
    resolution_confidence: float
    diagnostic: Optional[Dict[str, Any]] = None


@dataclass
class ExpressionResult:
    """Result of expression evaluation with direct and transitive operation relationships."""
    root_operation_id: Optional[str]
    direct_input_use_ids: List[str]
    direct_input_operation_ids: List[str]
    descendant_operation_ids: List[str]
    diagnostics: List[Dict[str, Any]]


class BindingResolver:
    """Unified binding resolution for Python variables across lexical scopes."""
    
    def __init__(self, function_id: str, file: str, local_vars: Set[str], free_vars: Set[str], global_vars: Set[str], nonlocal_vars: Set[str], symbol_table=None):
        self.function_id = function_id
        self.file = file
        self.local_vars = local_vars
        self.free_vars = free_vars or set()
        self.global_vars = global_vars or set()
        self.nonlocal_vars = nonlocal_vars or set()
        self.symbol_table = symbol_table
        # M4.6: Scope counter for unique comprehension and lambda scope IDs
        self._scope_counter = 0
    
    def _generate_scope_id(self) -> str:
        """Generate a unique scope ID for nested scopes (lambdas, comprehensions)."""
        self._scope_counter += 1
        return f"scope_{self._scope_counter}"
    
    def resolve_name(self, name: str, lexical_scope: str, ast_node: ast.AST) -> BindingResolution:
        """Resolve a name to its binding key and category."""
        # Check local scope first
        if name in self.local_vars:
            binding_key = f"{self.function_id}::{name}"
            return BindingResolution(
                binding_key=binding_key,
                binding_category='local',
                defining_scope=self.function_id,
                is_external_boundary=False,
                resolution_confidence=1.0,
                diagnostic=None
            )
        
        # Check global scope
        if name in self.global_vars:
            binding_key = f"{self.file}::{name}"
            return BindingResolution(
                binding_key=binding_key,
                binding_category='global',
                defining_scope=self.file,
                is_external_boundary=True,
                resolution_confidence=1.0,
                diagnostic=None
            )
        
        # Check nonlocal scope
        if name in self.nonlocal_vars:
            # For nonlocal, the defining scope is the enclosing function
            # We don't have the exact enclosing function ID, so use a conservative approach
            binding_key = f"{self.function_id}::nonlocal::{name}"
            return BindingResolution(
                binding_key=binding_key,
                binding_category='nonlocal',
                defining_scope=f"{self.function_id}::outer",
                is_external_boundary=False,
                resolution_confidence=0.8,
                diagnostic=None
            )
    
    def resolve_name(self, name: str, lexical_scope: str, ast_node: ast.AST) -> BindingResolution:
        """Resolve a name to its binding key and category."""
        # Check local scope first
        if name in self.local_vars:
            binding_key = f"{self.function_id}::{name}"
            return BindingResolution(
                binding_key=binding_key,
                binding_category='local',
                defining_scope=self.function_id,
                is_external_boundary=False,
                resolution_confidence=1.0,
                diagnostic=None
            )
        
        # Check global scope
        if name in self.global_vars:
            binding_key = f"{self.file}::{name}"
            return BindingResolution(
                binding_key=binding_key,
                binding_category='global',
                defining_scope=self.file,
                is_external_boundary=True,
                resolution_confidence=1.0,
                diagnostic=None
            )
        
        # Check nonlocal scope
        if name in self.nonlocal_vars:
            # For nonlocal, the defining scope is the enclosing function
            # We don't have the exact enclosing function ID, so use a conservative approach
            binding_key = f"{self.function_id}::nonlocal::{name}"
            return BindingResolution(
                binding_key=binding_key,
                binding_category='nonlocal',
                defining_scope=f"{self.function_id}::outer",
                is_external_boundary=False,
                resolution_confidence=0.8,
                diagnostic=None
            )
        
        # Check free variables (closure capture)
        if name in self.free_vars:
            # M4.4: Closure handling - inner use must reference outer binding
            # For nonlocal writes, we need to read previous outer definition
            # The binding key represents the outer defining scope
            binding_key = f"{self.function_id}::free::{name}"
            return BindingResolution(
                binding_key=binding_key,
                binding_category='free',
                defining_scope=f"{self.function_id}::outer",
                is_external_boundary=True,
                resolution_confidence=0.7,
                diagnostic=None
            )
        
        # Default to local if unknown
        binding_key = f"{self.function_id}::{name}"
        return BindingResolution(
            binding_key=binding_key,
            binding_category='local',
            defining_scope=self.function_id,
            is_external_boundary=False,
            resolution_confidence=0.5,
            diagnostic={'code': 'unknown_binding', 'message': f'Could not determine binding for {name}'}
        )
    
    def resolve_comprehension_binding(self, name: str, comprehension_id: str) -> BindingResolution:
        """Resolve a name within a comprehension scope with unique scope ID."""
        # M4.6: Comprehensions have their own scope with unique ID
        binding_key = f"{self.function_id}::comprehension:{comprehension_id}::{name}"
        return BindingResolution(
            binding_key=binding_key,
            binding_category='comprehension',
            defining_scope=f"{self.function_id}::comprehension:{comprehension_id}",
            is_external_boundary=False,
            resolution_confidence=1.0,
            diagnostic=None
        )
    
    def resolve_lambda_binding(self, name: str, lambda_id: str) -> BindingResolution:
        """Resolve a name within a lambda scope with unique scope ID."""
        # M4.6: Lambdas have their own scope with unique ID
        binding_key = f"{self.function_id}::lambda:{lambda_id}::{name}"
        return BindingResolution(
            binding_key=binding_key,
            binding_category='lambda',
            defining_scope=f"{self.function_id}::lambda:{lambda_id}",
            is_external_boundary=False,
            resolution_confidence=1.0,
            diagnostic=None
        )
    
    def resolve_nonlocal_write(self, name: str) -> BindingResolution:
        """M4.4: Resolve a nonlocal write - must preserve outer binding identity."""
        # For nonlocal writes, we preserve the outer binding identity
        # The key still references the outer scope, not the inner function
        binding_key = f"{self.function_id}::nonlocal::{name}"
        return BindingResolution(
            binding_key=binding_key,
            binding_category='nonlocal',
            defining_scope=f"{self.function_id}::outer",
            is_external_boundary=False,
            resolution_confidence=0.9,
            diagnostic=None
        )


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
    cfg_node_ids: List[str]
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
    cfg_node_ids: List[str]
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
    cfg_node_ids: List[str]
    expression: str
    operation: str
    input_use_ids: List[str] = field(default_factory=list)
    input_operation_ids: List[str] = field(default_factory=list)
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
    cfg_node_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Source span metadata for VR highlighting
    start_col: int = 0
    end_col: int = 0


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
                    'cfg_node_ids': n.cfg_node_ids,
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
