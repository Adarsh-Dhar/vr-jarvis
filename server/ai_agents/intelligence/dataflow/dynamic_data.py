"""Dynamic and runtime data collection infrastructure."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any


@dataclass
class RuntimeObservation:
    """A runtime observation (call edge, branch outcome, etc.)."""
    kind: str  # 'call', 'branch', 'exception'
    function_id: str
    line: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DynamicDataResult:
    """Result of dynamic data collection."""
    observations: List[RuntimeObservation]
    call_edges: Dict[str, Set[str]]  # actual call edges observed
    branch_outcomes: Dict[str, bool]  # condition node -> actual outcome
    metadata: Dict[str, Any] = field(default_factory=dict)


class DynamicDataCollector:
    """
    Collect dynamic and runtime data for static analysis enhancement.

    Uses sys.monitoring (Python 3.12+) or sys.settrace for data collection.
    """

    def __init__(self):
        self._observations: List[RuntimeObservation] = []

    def collect_from_trace(
        self,
        code: str,
        function_id: str
    ) -> DynamicDataResult:
        """
        Collect runtime data using trace instrumentation.

        This is a simplified placeholder. A full implementation would:
        1. Set up sys.monitoring or sys.settrace
        2. Execute the code in a sandboxed subprocess
        3. Record call edges, branch outcomes, exceptions
        4. Overlay on static graphs with 'runtime_observed' labels
        """
        # Placeholder - would use sys.monitoring in Python 3.12+
        return DynamicDataResult(
            observations=[],
            call_edges={},
            branch_outcomes={},
            metadata={'note': 'Dynamic collection requires runtime execution'}
        )

    def add_dynamic_label(
        self,
        node_id: str,
        label: str,
        value: Any
    ):
        """Add a dynamic observation label to a node."""
        self._observations.append(RuntimeObservation(
            kind='dynamic',
            function_id='unknown',
            line=0,
            metadata={'node_id': node_id, 'label': label, 'value': value}
        ))


class DynamicDataTracker:
    """Marks dynamically-dispatched constructs in a function's AST/CFG.

    Used by controlflow/service.py when ENABLE_DYNAMIC_DATA_TRACKING is on.
    The full implementation lands with the runtime-tracing workstream; until
    then it reports itself as unsupported and returns no nodes rather than
    guessing."""

    def track_dynamic_constructs(self, tree, cfg) -> List[Dict[str, Any]]:
        """Return dynamic construct nodes (getattr/setattr/eval/exec/import
        and importlib call sites). Currently unsupported: returns an empty
        list labelled accordingly."""
        return [{'status': 'unsupported',
                 'reason': 'dynamic construct tracking is not implemented'}]
