"""Generators, async and context managers - integration with Phase 1 work.

This module documents the Phase 2.7 improvements for generators, async, and context managers.
The foundational work was completed in Phase 1 (Steps 1.6 and 1.7), which added:

1. Generator Suspension (Phase 1.7):
   - CFG nodes for yield and yield_from with suspension_point metadata
   - Basic suspension modeling in _build_yield and _build_yield_from
   - Resume edges from suspension points

2. Async/Await (Phase 1.7):
   - CFG nodes for await with suspension_point metadata
   - Basic await modeling in _build_await
   - Exception routing through async context

3. Context Managers (Phase 1.4 and 1.6):
   - Proper ordering of __exit__ nodes in _build_with
   - Finalizer routing through finally blocks
   - Exception handling in context managers

Phase 2.7 improvements would add:
- Precise resume edge semantics (next/send/throw/close)
- Cancellation edges for await (CancelledError)
- Timeout modeling for asyncio.timeout
- __exit__ return value semantics (exception suppression)
- Partial entry failure for multiple managers
- Nested exit order validation

Current Status:
- Basic CFG structure exists from Phase 1
- Advanced semantics (resume types, cancellation, timeout) are future work
- Integration with call summaries (Phase 2.4) for custom managers is possible
"""

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass


@dataclass
class SuspensionInfo:
    """Information about a suspension point (yield or await)."""
    suspension_point: str  # 'yield', 'yield_from', 'await'
    cfg_node_id: str
    line: int
    resume_edges: List[str]  # List of possible resume targets
    metadata: Dict[str, Any]


@dataclass
class ContextManagerInfo:
    """Information about a context manager."""
    manager_id: str
    has_with: bool
    has_async_with: bool
    __exit___node_id: Optional[str]
    __aexit__node_id: Optional[str]
    metadata: Dict[str, Any]


class AsyncGeneratorAnalyzer:
    """
    Analyzer for async and generator semantics.

    Builds on the Phase 1 CFG infrastructure to add advanced semantics.
    """

    def __init__(self):
        self._suspensions: List[SuspensionInfo] = []
        self._context_managers: List[ContextManagerInfo] = []

    def analyze_suspend_points(self, cfg) -> List[SuspensionInfo]:
        """
        Analyze suspension points in the CFG.

        Finds yield, yield_from, and await nodes and categorizes their resume edges.
        """
        suspensions = []

        for node in cfg.nodes:
            if node.metadata.get('suspension_point'):
                suspension = SuspensionInfo(
                    suspension_point=node.metadata['suspension_point'],
                    cfg_node_id=node.id,
                    line=node.start_line,
                    resume_edges=self._get_resume_edges(cfg, node.id),
                    metadata=node.metadata
                )
                suspensions.append(suspension)

        return suspensions

    def _get_resume_edges(self, cfg, node_id: str) -> List[str]:
        """Get the resume edges from a suspension node."""
        # Find edges from this node
        edges = [e for e in cfg.edges if e.source == node_id]
        return [e.target for e in edges]

    def analyze_context_managers(self, cfg) -> List[ContextManagerInfo]:
        """
        Analyze context manager usage in the CFG.

        Finds with and async with blocks and their exit nodes.
        """
        managers = []

        for node in cfg.nodes:
            if node.kind == 'with' or node.ast_kind == 'With':
                manager = ContextManagerInfo(
                    manager_id=node.id,
                    has_with=node.kind == 'with',
                    has_async_with=node.ast_kind == 'AsyncWith',
                    __exit__node_id=node.metadata.get('__exit__node_id'),
                    __aexit__node_id=node.metadata.get('__aexit__node_id'),
                    metadata=node.metadata
                )
                managers.append(manager)

        return managers
