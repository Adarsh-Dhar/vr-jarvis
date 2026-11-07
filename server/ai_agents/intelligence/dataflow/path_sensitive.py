"""Path-sensitive data-flow analysis with phi nodes and must-reaching definitions."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from ..controlflow.models import ControlFlowGraph, CFGNode, CFGEdge
from .models import Definition, VariableUse, DefUseFacts, DataFlowEdge


@dataclass
class PhiNode:
    """A phi node representing a merge point for definitions from different paths."""
    id: str
    binding_key: str
    function_id: str
    file: str
    line: int
    cfg_node_id: str  # The CFG node where this phi is inserted
    incoming: List[Tuple[str, Dict[str, Any]]]  # List of (definition_id, edge_condition) pairs
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PathSensitiveResult:
    """Result of path-sensitive analysis."""
    phi_nodes: List[PhiNode]
    must_in_sets: Dict[str, Set[str]]  # node_id -> must-reaching definition IDs
    must_out_sets: Dict[str, Set[str]]  # node_id -> must-reaching definition IDs
    phi_edges: List[DataFlowEdge]  # Edges from definitions to phi and phi to uses
    diagnostics: List[Dict[str, Any]]


class PathSensitiveAnalyzer:
    """Perform path-sensitive data-flow analysis with phi nodes."""

    def __init__(self):
        self._phi_counter = 0

    def analyze(
        self,
        cfg: ControlFlowGraph,
        facts: DefUseFacts,
        may_in_sets: Dict[str, Set[str]],
        may_out_sets: Dict[str, Set[str]]
    ) -> PathSensitiveResult:
        """
        Perform path-sensitive analysis.

        Steps:
        1. Identify CFG join points where multiple definitions converge
        2. Insert phi nodes at join points
        3. Compute must-reaching definitions using intersection
        4. Create edges with condition labels
        """
        phi_nodes = []
        phi_edges = []
        diagnostics = []

        # Step 1: Find join points (nodes with multiple predecessors where definitions converge)
        join_points = self._find_join_points(cfg, facts.definitions, may_in_sets)

        # Step 2: Create phi nodes at join points
        for join_node_id, binding_defs in join_points.items():
            for binding_key, def_ids in binding_defs.items():
                if len(def_ids) > 1:
                    # Multiple definitions of the same binding converge here
                    phi = self._create_phi_node(
                        binding_key,
                        join_node_id,
                        def_ids,
                        cfg,
                        facts
                    )
                    phi_nodes.append(phi)

        # Step 3: Compute must-reaching definitions
        must_in_sets, must_out_sets = self._compute_must_reaching(
            cfg,
            facts.definitions,
            phi_nodes
        )

        # Step 4: Create phi edges
        phi_edges = self._create_phi_edges(cfg, facts, phi_nodes, may_in_sets)

        return PathSensitiveResult(
            phi_nodes=phi_nodes,
            must_in_sets=must_in_sets,
            must_out_sets=must_out_sets,
            phi_edges=phi_edges,
            diagnostics=diagnostics
        )

    def _find_join_points(
        self,
        cfg: ControlFlowGraph,
        definitions: List[Definition],
        may_in_sets: Dict[str, Set[str]]
    ) -> Dict[str, Dict[str, Set[str]]]:
        """
        Find CFG nodes where multiple definitions of the same binding converge.

        Returns: {cfg_node_id: {binding_key: {definition_ids}}}
        """
        join_points = {}

        for node in cfg.nodes:
            node_id = node.id
            predecessors = self._get_predecessors(cfg, node_id)

            # Only consider nodes with multiple predecessors (join points)
            if len(predecessors) < 2:
                continue

            # Get IN set for this node
            reaching_defs = may_in_sets.get(node_id, set())

            # Group by binding key
            binding_map: Dict[str, Set[str]] = {}
            for def_id in reaching_defs:
                for definition in definitions:
                    if definition.id == def_id:
                        binding_key = definition.binding_key
                        if binding_key not in binding_map:
                            binding_map[binding_key] = set()
                        binding_map[binding_key].add(def_id)
                        break

            # Keep only bindings with multiple reaching definitions
            converging_bindings = {
                key: defs for key, defs in binding_map.items()
                if len(defs) > 1
            }

            if converging_bindings:
                join_points[node_id] = converging_bindings

        return join_points

    def _create_phi_node(
        self,
        binding_key: str,
        cfg_node_id: str,
        definition_ids: Set[str],
        cfg: ControlFlowGraph,
        facts: DefUseFacts
    ) -> PhiNode:
        """Create a phi node for merging definitions."""
        self._phi_counter += 1
        phi_id = f"{facts.function_id}_phi_{self._phi_counter}"

        # Get the CFG node
        cfg_node = cfg.get_node(cfg_node_id)
        if not cfg_node:
            raise ValueError(f"CFG node {cfg_node_id} not found")

        # Collect incoming definitions with their edge conditions
        incoming = []
        predecessors = self._get_predecessors(cfg, cfg_node_id)

        for def_id in definition_ids:
            # Find which predecessor brings this definition
            for pred_id in predecessors:
                # Check if this definition is in the predecessor's OUT set
                # We'll need the may_out_sets, but for now we'll store the def_id
                # The actual edge condition will be resolved later
                incoming.append((def_id, {'source_pred': pred_id}))

        return PhiNode(
            id=phi_id,
            binding_key=binding_key,
            function_id=facts.function_id,
            file=facts.file,
            line=cfg_node.start_line,
            cfg_node_id=cfg_node_id,
            incoming=incoming,
            metadata={
                'binding_key': binding_key,
                'incoming_count': len(incoming)
            }
        )

    def _compute_must_reaching(
        self,
        cfg: ControlFlowGraph,
        definitions: List[Definition],
        phi_nodes: List[PhiNode]
    ) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
        """
        Compute must-reaching definitions using intersection.

        IN[B] = intersection of OUT[P] for all predecessors P
        OUT[B] = GEN[B] union (IN[B] - KILL[B])
        """
        # Build GEN and KILL sets
        gen, kill = self._calculate_gen_kill(cfg, definitions)

        # Initialize sets
        must_in_sets: Dict[str, Set[str]] = {node.id: set() for node in cfg.nodes}
        must_out_sets: Dict[str, Set[str]] = {node.id: set() for node in cfg.nodes}

        # Entry node: no definitions must-reach initially
        if cfg.entry_node_id:
            must_in_sets[cfg.entry_node_id] = set()

        # Worklist algorithm
        worklist = list(node.id for node in cfg.nodes)

        while worklist:
            node_id = worklist.pop(0)

            # Calculate IN[B] = intersection of OUT[P] for all predecessors P
            predecessors = self._get_predecessors(cfg, node_id)
            if predecessors:
                predecessor_outs = [must_out_sets[pred_id] for pred_id in predecessors if pred_id in must_out_sets]
                if predecessor_outs:
                    # Use intersection for must analysis
                    new_in = set.intersection(*predecessor_outs) if len(predecessor_outs) > 1 else predecessor_outs[0]
                else:
                    new_in = set()
            else:
                new_in = set()

            # Calculate OUT[B] = GEN[B] union (IN[B] - KILL[B])
            new_out = gen[node_id].union(new_in - kill[node_id])

            # If changed, add successors to worklist
            if new_out != must_out_sets[node_id]:
                must_out_sets[node_id] = new_out
                must_in_sets[node_id] = new_in
                successors = self._get_successors(cfg, node_id)
                for succ_id in successors:
                    if succ_id not in worklist:
                        worklist.append(succ_id)

        return must_in_sets, must_out_sets

    def _calculate_gen_kill(
        self,
        cfg: ControlFlowGraph,
        definitions: List[Definition]
    ) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
        """Calculate GEN and KILL sets for must analysis."""
        gen: Dict[str, Set[str]] = {}
        kill: Dict[str, Set[str]] = {}

        # Build binding_key to definitions mapping
        binding_defs: Dict[str, Set[str]] = {}
        for definition in definitions:
            key = definition.binding_key
            if key not in binding_defs:
                binding_defs[key] = set()
            binding_defs[key].add(definition.id)

        # Map definitions to CFG nodes
        node_defs: Dict[str, List[Definition]] = {}
        for definition in definitions:
            for cfg_node_id in definition.cfg_node_ids:
                if cfg_node_id not in node_defs:
                    node_defs[cfg_node_id] = []
                node_defs[cfg_node_id].append(definition)

        # Calculate GEN and KILL for each node
        for node in cfg.nodes:
            node_id = node.id

            # GEN: definitions created at this node
            gen[node_id] = set()
            if node_id in node_defs:
                for definition in node_defs[node_id]:
                    if not definition.metadata.get('is_kill_only', False):
                        gen[node_id].add(definition.id)

            # KILL: earlier definitions of the same binding
            kill[node_id] = set()
            if node_id in node_defs:
                for definition in node_defs[node_id]:
                    key = definition.binding_key
                    if key in binding_defs:
                        for def_id in binding_defs[key]:
                            if def_id != definition.id:
                                kill[node_id].add(def_id)

        # Ensure all nodes have gen and kill sets
        for node in cfg.nodes:
            if node.id not in gen:
                gen[node.id] = set()
            if node.id not in kill:
                kill[node.id] = set()

        return gen, kill

    def _create_phi_edges(
        self,
        cfg: ControlFlowGraph,
        facts: DefUseFacts,
        phi_nodes: List[PhiNode],
        may_in_sets: Dict[str, Set[str]]
    ) -> List[DataFlowEdge]:
        """Create data-flow edges for phi nodes."""
        edges = []
        edge_counter = 0

        for phi in phi_nodes:
            # Edges from incoming definitions to phi
            for def_id, condition in phi.incoming:
                edge_counter += 1
                edge = DataFlowEdge(
                    id=f"{facts.function_id}_phi_edge_{edge_counter}",
                    source=def_id,
                    target=phi.id,
                    kind='phi_input',
                    resolution='must_reach',
                    condition=self._standardize_condition(condition),
                    evidence={
                        'rule': 'phi_merge',
                        'source_file': facts.file,
                        'binding_key': phi.binding_key
                    }
                )
                edges.append(edge)

            # Edge from phi to uses
            # Find uses at this CFG node
            for use in facts.uses:
                if phi.cfg_node_id in use.cfg_node_ids and use.binding_key == phi.binding_key:
                    edge_counter += 1
                    edge = DataFlowEdge(
                        id=f"{facts.function_id}_phi_edge_{edge_counter}",
                        source=phi.id,
                        target=use.id,
                        kind='phi_output',
                        resolution='must_reach',
                        condition=None,
                        evidence={
                            'rule': 'phi_to_use',
                            'source_file': facts.file,
                            'binding_key': phi.binding_key
                        }
                    )
                    edges.append(edge)

        return edges

    def _standardize_condition(self, condition: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Standardize edge condition to structured format.

        Convert simple strings to {'predicate': str, 'polarity': bool}
        """
        if not condition:
            return None

        if isinstance(condition, str):
            # Simple string condition - try to parse it
            if condition == 'true':
                return {'predicate': 'condition', 'polarity': True}
            elif condition == 'false':
                return {'predicate': 'condition', 'polarity': False}
            else:
                return {'predicate': condition, 'polarity': True}

        if isinstance(condition, dict):
            # Already structured or partially structured
            if 'predicate' in condition and 'polarity' in condition:
                return condition
            else:
                # Add missing fields
                return {
                    'predicate': condition.get('predicate', 'unknown'),
                    'polarity': condition.get('polarity', True)
                }

        return None

    def _get_predecessors(self, cfg: ControlFlowGraph, node_id: str) -> List[str]:
        """Get predecessor node IDs for a given node."""
        predecessors = []
        for edge in cfg.edges:
            if edge.target == node_id:
                predecessors.append(edge.source)
        return predecessors

    def _get_successors(self, cfg: ControlFlowGraph, node_id: str) -> List[str]:
        """Get successor node IDs for a given node."""
        successors = []
        for edge in cfg.edges:
            if edge.source == node_id:
                successors.append(edge.target)
        return successors
