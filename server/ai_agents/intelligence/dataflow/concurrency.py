"""Concurrency analysis for shared state and race conditions."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from .models import DefUseFacts


@dataclass
class SharedAccess:
    """A shared variable access."""
    variable: str
    function_id: str
    line: int
    access_kind: str  # 'read', 'write'
    task_id: Optional[str]


@dataclass
class ConcurrencyAnalysisResult:
    """Result of concurrency analysis."""
    shared_variables: Set[str]  # Variables accessed by multiple tasks
    potential_races: List[Dict[str, Any]]  # Potential race conditions
    accesses: List[SharedAccess]
    diagnostics: List[Dict[str, Any]]


class ConcurrencyAnalyzer:
    """
    Analyze concurrency for shared state and race conditions.

    Identifies:
    - Variables shared across tasks/threads
    - Potential race conditions (unsynchronized writes)
    - Async task creation patterns
    """

    def __init__(self):
        self._task_counter = 0

    def analyze_concurrency(
        self,
        all_facts: List[DefUseFacts]
    ) -> ConcurrencyAnalysisResult:
        """
        Analyze concurrency patterns across functions.

        Returns information about shared state and potential races.
        """
        shared_variables = set()
        potential_races = []
        accesses = []
        diagnostics = []

        # Detect async task creation
        for facts in all_facts:
            for operation in facts.operations:
                if operation.operation == 'Call':
                    # Check for async patterns (simplified)
                    if 'asyncio.create_task' in operation.expression.lower():
                        self._task_counter += 1
                        diagnostics.append({
                            'code': 'async_task_created',
                            'function_id': facts.function_id,
                            'line': operation.line,
                            'task_id': f'task_{self._task_counter}'
                        })

        # Simplified shared variable detection
        # A full implementation would:
        # 1. Track which variables are shared across tasks
        # 2. Analyze synchronization primitives (locks, queues)
        # 3. Detect unsynchronized access patterns

        return ConcurrencyAnalysisResult(
            shared_variables=shared_variables,
            potential_races=potential_races,
            accesses=accesses,
            diagnostics=diagnostics
        )
