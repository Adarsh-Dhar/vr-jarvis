"""Path feasibility analysis for detecting infeasible paths."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from ..controlflow.models import ControlFlowGraph, CFGNode


@dataclass
class PathCondition:
    """A condition along a path."""
    predicate: str
    polarity: bool  # True for true branch, False for false
    line: int


@dataclass
class FeasibilityResult:
    """Result of path feasibility analysis."""
    infeasible_paths: List[List[str]]  # Lists of node IDs representing infeasible paths
    path_conditions: Dict[str, List[PathCondition]]  # node_id -> conditions to reach it
    dead_branches: Set[str]  # Node IDs that are never reached
    diagnostics: List[Dict[str, Any]]


class PathFeasibilityAnalyzer:
    """
    Analyze path feasibility using constant propagation.

    Identifies:
    - Infeasible paths (e.g., if False: ...)
    - Dead branches (never executed)
    - Conditions that can be proven true or false
    """

    def __init__(self):
        self._path_conditions: Dict[str, List[PathCondition]] = {}

    def analyze_feasibility(
        self,
        cfg: ControlFlowGraph,
        constants: Dict[str, Any]
    ) -> FeasibilityResult:
        """
        Analyze path feasibility using constant values.

        Returns information about infeasible paths and dead branches.
        """
        infeasible_paths = []
        dead_branches = set()
        diagnostics = []

        # Analyze each condition node
        for node in cfg.nodes:
            if node.kind == 'condition':
                # Check if the condition is constant
                condition_expr = node.condition or node.label
                if condition_expr in constants:
                    value = constants[condition_expr]
                    if isinstance(value, bool):
                        # If condition is always false, the true branch is dead
                        if not value:
                            # Find the true branch target
                            true_edges = [e for e in cfg.edges if e.source == node.id and e.kind == 'true']
                            for edge in true_edges:
                                dead_branches.add(edge.target)
                                diagnostics.append({
                                    'code': 'dead_branch',
                                    'node_id': node.id,
                                    'reason': f'Condition {condition_expr} is always False',
                                    'line': node.start_line
                                })
                        # If condition is always true, the false branch is dead
                        if value:
                            false_edges = [e for e in cfg.edges if e.source == node.id and e.kind == 'false']
                            for edge in false_edges:
                                dead_branches.add(edge.target)
                                diagnostics.append({
                                    'code': 'dead_branch',
                                    'node_id': node.id,
                                    'reason': f'Condition {condition_expr} is always True',
                                    'line': node.start_line
                                })

        return FeasibilityResult(
            infeasible_paths=infeasible_paths,
            path_conditions=self._path_conditions,
            dead_branches=dead_branches,
            diagnostics=diagnostics
        )
