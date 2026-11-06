"""Reaching definitions analysis for data-flow graphs."""
from typing import Dict, List, Set, Optional
from ..controlflow.models import ControlFlowGraph, CFGNode
from .models import Definition, VariableUse, DefUseFacts


class ReachingDefinitionsAnalyzer:
    """Perform reaching definitions analysis over a CFG."""

    def analyze(
        self,
        cfg: ControlFlowGraph,
        facts: DefUseFacts
    ) -> Dict[str, Set[str]]:
        """
        Perform reaching definitions analysis.

        Returns a dict mapping each CFG node ID to the set of definition IDs
        that reach that node (IN set).
        """
        # Build node to definitions mapping
        node_defs = self._build_node_definitions(cfg, facts.definitions)

        # Build node to uses mapping
        node_uses = self._build_node_uses(cfg, facts.uses)

        # Calculate GEN and KILL sets for each node
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
        }

    def _build_node_definitions(
        self,
        cfg: ControlFlowGraph,
        definitions: List[Definition]
    ) -> Dict[str, List[Definition]]:
        """Map each CFG node to the definitions it creates."""
        node_defs: Dict[str, List[Definition]] = {}

        for definition in definitions:
            cfg_node_id = definition.cfg_node_id
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
            cfg_node_id = use.cfg_node_id
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

        # Build variable to definitions mapping
        var_defs: Dict[str, Set[str]] = {}
        for definition in definitions:
            var = definition.variable
            if var not in var_defs:
                var_defs[var] = set()
            var_defs[var].add(definition.id)

        # Calculate GEN and KILL for each node
        for node in cfg.nodes:
            node_id = node.id

            # GEN: definitions created at this node
            gen[node_id] = set()
            if node_id in node_defs:
                for definition in node_defs[node_id]:
                    gen[node_id].add(definition.id)

            # KILL: earlier definitions of the same variable
            kill[node_id] = set()
            if node_id in node_defs:
                for definition in node_defs[node_id]:
                    var = definition.variable
                    if var in var_defs:
                        # Kill all other definitions of this variable
                        for def_id in var_defs[var]:
                            if def_id != definition.id:
                                kill[node_id].add(def_id)

        return gen, kill

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
        """
        # Initialize all sets to empty
        in_sets: Dict[str, Set[str]] = {node.id: set() for node in cfg.nodes}
        out_sets: Dict[str, Set[str]] = {node.id: set() for node in cfg.nodes}

        # Worklist of nodes to process
        worklist = list(node.id for node in cfg.nodes)

        while worklist:
            node_id = worklist.pop(0)

            # Calculate IN[B] = union of OUT[P] for all predecessors P
            predecessors = self._get_predecessors(cfg, node_id)
            new_in = set()
            for pred_id in predecessors:
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

        return in_sets, out_sets

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

    def resolve_use(
        self,
        use: VariableUse,
        analysis_result: Dict[str, Set[str]],
        facts: DefUseFacts
    ) -> List[Definition]:
        """
        Resolve which definitions reach a given use.

        Returns a list of reaching definitions (may be multiple due to branches).
        """
        node_id = use.cfg_node_id
        in_sets = analysis_result['in_sets']

        if node_id not in in_sets:
            return []

        # Get all definitions that reach this node
        reaching_def_ids = in_sets[node_id]

        # Filter to definitions of the same variable
        reaching_defs = []
        for def_id in reaching_def_ids:
            for definition in facts.definitions:
                if definition.id == def_id and definition.variable == use.variable:
                    reaching_defs.append(definition)
                    break

        return reaching_defs
