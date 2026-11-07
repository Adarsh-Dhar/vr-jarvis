"""Reaching definitions analysis for data-flow graphs."""
from typing import Dict, List, Set, Optional, Any
from ..controlflow.models import ControlFlowGraph, CFGNode
from .models import Definition, VariableUse, DefUseFacts


class ReachingDefinitionsAnalyzer:
    """Perform reaching definitions analysis over a CFG."""

    def analyze(
        self,
        cfg: ControlFlowGraph,
        facts: DefUseFacts
    ) -> Dict[str, Any]:
        """
        Perform reaching definitions analysis.

        Returns a dict with in_sets, out_sets, gen, kill, node_defs, node_uses, and diagnostics.
        """
        # Validate CFG references
        cfg_node_ids = {node.id for node in cfg.nodes}
        for definition in facts.definitions:
            if not definition.cfg_node_ids:
                return {
                    'error': f"Definition {definition.id} has no CFG node IDs",
                    'in_sets': {},
                    'out_sets': {},
                    'gen': {},
                    'kill': {},
                    'node_defs': {},
                    'node_uses': {},
                    'diagnostics': [{'code': 'no_cfg_reference', 'definition_id': definition.id}],
                }
            for cfg_node_id in definition.cfg_node_ids:
                if cfg_node_id not in cfg_node_ids:
                    return {
                        'error': f"Definition {definition.id} has invalid CFG node {cfg_node_id}",
                        'in_sets': {},
                        'out_sets': {},
                        'gen': {},
                        'kill': {},
                        'node_defs': {},
                        'node_uses': {},
                        'diagnostics': [{'code': 'invalid_cfg_reference', 'definition_id': definition.id}],
                    }
        for use in facts.uses:
            if not use.cfg_node_ids:
                return {
                    'error': f"Use {use.id} has no CFG node IDs",
                    'in_sets': {},
                    'out_sets': {},
                    'gen': {},
                    'kill': {},
                    'node_defs': {},
                    'node_uses': {},
                    'diagnostics': [{'code': 'no_cfg_reference', 'use_id': use.id}],
                }
            for cfg_node_id in use.cfg_node_ids:
                if cfg_node_id not in cfg_node_ids:
                    return {
                        'error': f"Use {use.id} has invalid CFG node {cfg_node_id}",
                        'in_sets': {},
                        'out_sets': {},
                        'gen': {},
                        'kill': {},
                        'node_defs': {},
                        'node_uses': {},
                        'diagnostics': [{'code': 'invalid_cfg_reference', 'use_id': use.id}],
                    }

        # Build node to definitions mapping
        node_defs = self._build_node_definitions(cfg, facts.definitions)

        # Build node to uses mapping
        node_uses = self._build_node_uses(cfg, facts.uses)

        # Calculate GEN and KILL sets for each node (using binding_key)
        gen, kill = self._calculate_gen_kill(cfg, facts.definitions, node_defs)

        # Solve fixed-point
        in_sets, out_sets = self._solve_fixed_point(cfg, gen, kill)

        return {
            'in_sets': in_sets,
            'out_sets': out_sets,
            'gen': gen,
            'kill': kill,
            'node_defs': node_defs,
            'node_uses': node_uses,
            'diagnostics': [],
        }

    def _build_node_definitions(
        self,
        cfg: ControlFlowGraph,
        definitions: List[Definition]
    ) -> Dict[str, List[Definition]]:
        """Map each CFG node to the definitions it creates."""
        node_defs: Dict[str, List[Definition]] = {}

        for definition in definitions:
            # Use ALL cfg_node_ids, not just the first one
            for cfg_node_id in definition.cfg_node_ids:
                if cfg_node_id not in node_defs:
                    node_defs[cfg_node_id] = []
                node_defs[cfg_node_id].append(definition)

        return node_defs

    def _build_node_uses(
        self,
        cfg: ControlFlowGraph,
        uses: List[VariableUse]
    ) -> Dict[str, List[VariableUse]]:
        """Map each CFG node to the uses it contains."""
        node_uses: Dict[str, List[VariableUse]] = {}

        for use in uses:
            # Use ALL cfg_node_ids, not just the first one
            for cfg_node_id in use.cfg_node_ids:
                if cfg_node_id not in node_uses:
                    node_uses[cfg_node_id] = []
                node_uses[cfg_node_id].append(use)

        return node_uses

    def _calculate_gen_kill(
        self,
        cfg: ControlFlowGraph,
        definitions: List[Definition],
        node_defs: Dict[str, List[Definition]]
    ) -> tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
        """
        Calculate GEN and KILL sets for each CFG node.

        GEN[B]: definitions created by node B
        KILL[B]: earlier definitions of the same variable invalidated by B
        """
        gen: Dict[str, Set[str]] = {}
        kill: Dict[str, Set[str]] = {}

        # Build binding_key to definitions mapping (key for lexical identity)
        binding_defs: Dict[str, Set[str]] = {}
        for definition in definitions:
            key = definition.binding_key
            if key not in binding_defs:
                binding_defs[key] = set()
            binding_defs[key].add(definition.id)

        # Calculate GEN and KILL for each node
        for node in cfg.nodes:
            node_id = node.id

            # GEN: definitions created at this node (excluding deletions)
            gen[node_id] = set()
            if node_id in node_defs:
                for definition in node_defs[node_id]:
                    # Exclude deletion events from GEN - they are kill-only
                    if definition.metadata.get('is_kill_only', False):
                        continue
                    gen[node_id].add(definition.id)

            # KILL: earlier definitions of the same binding identity
            # Deletions also kill definitions of the same binding
            kill[node_id] = set()
            if node_id in node_defs:
                for definition in node_defs[node_id]:
                    key = definition.binding_key
                    if key in binding_defs:
                        # Kill all other definitions of this binding
                        for def_id in binding_defs[key]:
                            if def_id != definition.id:
                                kill[node_id].add(def_id)

        return gen, kill
    
    def resolve_return_provenance(
        self,
        cfg: ControlFlowGraph,
        facts: DefUseFacts
    ) -> Dict[str, Any]:
        """
        M6.5: Resolve return value provenance using binding-key-based matching.
        
        For each return expression, resolve its actual reaching definitions
        using binding keys rather than connecting all definitions with same variable name.
        
        Returns a dict mapping return operation IDs to their reaching definition IDs.
        """
        return_provenance = {}
        
        # Find all return-value sink operations
        return_operations = [op for op in facts.operations if op.metadata.get('is_return_sink', False)]
        
        for return_op in return_operations:
            op_id = return_op.id
            
            # Get CFG node for this return operation
            cfg_node_ids = return_op.cfg_node_ids
            if not cfg_node_ids:
                continue
            
            # Get reaching definitions at this CFG node
            # Find the node in our analysis results
            in_sets, out_sets = self.analyze(cfg, facts)
            
            # Get IN set for the first CFG node of the return
            cfg_node_id = cfg_node_ids[0]
            reaching_defs = in_sets.get(cfg_node_id, set())
            
            # Filter by binding key if return has a specific variable
            if return_op.metadata.get('return_variable'):
                variable = return_op.metadata['return_variable']
                # Filter to only definitions with matching binding key
                binding_key = f"{facts.function_id}::{variable}"
                matching_defs = []
                for def_id in reaching_defs:
                    for definition in facts.definitions:
                        if definition.id == def_id and definition.binding_key == binding_key:
                            matching_defs.append(def_id)
                return_provenance[op_id] = matching_defs
            else:
                # For literal or complex return expressions, include all reaching defs
                return_provenance[op_id] = list(reaching_defs)
        
        return return_provenance

    def _solve_fixed_point(
        self,
        cfg: ControlFlowGraph,
        gen: Dict[str, Set[str]],
        kill: Dict[str, Set[str]]
    ) -> tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
        """
        Solve the reaching definitions data-flow equations using worklist algorithm.

        IN[B] = union of OUT[P] for all predecessors P of B
        OUT[B] = GEN[B] union (IN[B] - KILL[B])

        Edge-specific transfer: For exceptional edges, filter out definitions
        that shouldn't propagate (e.g., assignment RHS evaluation vs commit).
        """
        # Initialize all sets to empty (must-analysis is deferred due to complexity)
        # For must-analysis, we would initialize IN with all definitions and use intersection
        # This is deferred to avoid incorrect results
        in_sets: Dict[str, Set[str]] = {node.id: set() for node in cfg.nodes}
        out_sets: Dict[str, Set[str]] = {node.id: set() for node in cfg.nodes}

        # Build edge-specific transfer info: map (source, target) -> list of edge kinds
        # Changed to list to handle multiple edge types between same nodes
        edge_kinds = {}
        for edge in cfg.edges:
            key = (edge.source, edge.target)
            if key not in edge_kinds:
                edge_kinds[key] = []
            edge_kinds[key].append(edge.kind)

        # Worklist of nodes to process
        worklist = list(node.id for node in cfg.nodes)

        while worklist:
            node_id = worklist.pop(0)

            # Calculate IN[B] = union of OUT[P] for all predecessors P
            predecessors = self._get_predecessors(cfg, node_id)
            new_in = set()
            for pred_id in predecessors:
                # Process individual edges separately (do not merge edge kinds)
                # Get individual edges from pred to current
                pred_edges = [e for e in cfg.edges if e.source == pred_id and e.target == node_id]
                for edge in pred_edges:
                    if edge.kind in ('exception', 'raise', 'may_raise'):
                        # M6.4: Evaluation/commit separation for exceptional edges
                        # On exceptional edges, we must preserve prior definitions before evaluation
                        # Filter out definitions that were generated on the evaluation path
                        # but not yet committed
                        pred_out = out_sets[pred_id]
                        # Check if predecessor has evaluation metadata
                        pred_node = next((n for n in cfg.nodes if n.id == pred_id), None)
                        if pred_node and pred_node.metadata.get('is_evaluation', False):
                            # This is an evaluation node - filter out its GEN definitions on exception paths
                            pred_gen = gen.get(pred_id, set())
                            # Don't propagate definitions that were generated during evaluation
                            filtered_out = pred_out - pred_gen
                            new_in.update(filtered_out)
                        else:
                            # Normal propagation for non-evaluation nodes
                            new_in.update(pred_out)
                    else:
                        # Normal transfer: include all
                        new_in.update(out_sets[pred_id])

            # Calculate OUT[B] = GEN[B] union (IN[B] - KILL[B])
            new_out = gen[node_id].union(new_in - kill[node_id])

            # Check if sets changed
            if new_in != in_sets[node_id] or new_out != out_sets[node_id]:
                in_sets[node_id] = new_in
                out_sets[node_id] = new_out

                # Add successors to worklist
                successors = self._get_successors(cfg, node_id)
                for succ_id in successors:
                    if succ_id not in worklist:
                        worklist.append(succ_id)

        # Filter out unreachable subgraphs before returning
        # Calculate reachability from entry node
        reachable = self._calculate_reachability(cfg)
        for node_id in list(in_sets.keys()):
            if node_id not in reachable:
                in_sets[node_id] = set()
                out_sets[node_id] = set()

        return in_sets, out_sets

    def analyze_must_reach(
        self,
        cfg: ControlFlowGraph,
        facts: DefUseFacts
    ) -> Dict[str, Any]:
        """
        Perform must-reaching definitions analysis.
        
        NOTE: This method is marked as FUTURE WORK for v1.
        The JARVIS Python CFG/DFG v1 frozen scope implements only may-reaching definitions.
        Must-reaching analysis requires additional infrastructure and is deferred to future work.
        
        Unlike may-reaching (union of predecessor OUT sets),
        must-reaching uses intersection of predecessor OUT sets.
        A definition must-reach a use only if it reaches on ALL paths.
        """
        # Build node_defs and node_uses
        node_defs = self._build_node_definitions(cfg, facts.definitions)
        node_uses = self._build_node_uses(cfg, facts.uses)
        
        # Build binding_defs map
        binding_defs = {}
        for definition in facts.definitions:
            key = definition.binding_key
            if key not in binding_defs:
                binding_defs[key] = []
            binding_defs[key].append(definition.id)
        
        # Initialize sets
        must_in_sets: Dict[str, Set[str]] = {node.id: set() for node in cfg.nodes}
        must_out_sets: Dict[str, Set[str]] = {node.id: set() for node in cfg.nodes}
        
        # Calculate GEN for must analysis (definitions that must occur)
        gen = {}
        for node_id in node_defs:
            gen[node_id] = set(d.id for d in node_defs[node_id])
        
        # Calculate KILL (same as may analysis)
        kill = {}
        for node_id in node_defs:
            kill[node_id] = set()
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
        
        # Worklist algorithm with intersection instead of union
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
        
        return {
            'must_in_sets': must_in_sets,
            'must_out_sets': must_out_sets,
            'diagnostics': []
        }

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

    def _calculate_reachability(self, cfg: ControlFlowGraph) -> Set[str]:
        """Calculate which nodes are reachable from the entry node."""
        if not cfg.entry_node_id:
            return set()

        reachable = set()
        worklist = [cfg.entry_node_id]
        visited = set()

        while worklist:
            node_id = worklist.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            reachable.add(node_id)

            # Add successors
            successors = self._get_successors(cfg, node_id)
            for succ_id in successors:
                if succ_id not in visited:
                    worklist.append(succ_id)

        return reachable

    def resolve_use(
        self,
        use: VariableUse,
        analysis_result: Dict[str, Set[str]],
        facts: DefUseFacts
    ) -> List[Definition]:
        """
        Resolve which definitions reach a given use.

        Returns a list of reaching definitions (may be multiple due to branches).
        Uses binding identity instead of variable-name matching.
        """
        # Use ALL cfg_node_ids for the use
        in_sets = analysis_result['in_sets']
        reaching_def_ids = set()

        # Collect reaching definitions from all CFG nodes associated with this use
        for node_id in use.cfg_node_ids:
            if node_id in in_sets:
                reaching_def_ids.update(in_sets[node_id])

        # Filter to definitions with the same binding identity
        reaching_defs = []
        for def_id in reaching_def_ids:
            for definition in facts.definitions:
                if definition.id == def_id and definition.binding_key == use.binding_key:
                    reaching_defs.append(definition)
                    break

        return reaching_defs
