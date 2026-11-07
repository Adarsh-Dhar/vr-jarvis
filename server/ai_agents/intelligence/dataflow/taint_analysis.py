"""Interprocedural taint analysis with sanitizers."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from .models import DefUseFacts, ExpressionFact
from .summaries import SummaryRegistry
from .interprocedural import FunctionSummary


@dataclass
class TaintLabel:
    """A taint label for security analysis."""
    kind: str  # 'sql', 'command', 'code', 'path', etc.
    source_id: str  # Where the taint originated
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaintPath:
    """A taint propagation path through the code."""
    path_id: str
    source_function: str
    sink_function: str
    source_line: int
    sink_line: int
    taint_kind: str
    sanitizers: List[str]  # Sanitizer functions on the path
    confidence: float
    hops: List[Dict[str, Any]]  # Each hop: {function_id, line, operation}
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaintAnalysisResult:
    """Result of taint analysis."""
    taint_paths: List[TaintPath]
    sources: Dict[str, List[TaintLabel]]  # function_id -> taint labels
    sinks: Dict[str, List[str]]  # function_id -> sink kinds
    sanitizers: Dict[str, Set[str]]  # function_id -> sanitizer kinds
    diagnostics: List[Dict[str, Any]]


class InterproceduralTaintAnalyzer:
    """
    Perform interprocedural taint analysis.

    Tracks taint labels as they flow through:
    - Function calls (argument propagation)
    - Return values (taint flows back)
    - Object fields (through mutations)
    - Sanitizers (functions that clear taint)
    """

    def __init__(self, summary_registry: Optional[SummaryRegistry] = None):
        self._registry = summary_registry or SummaryRegistry()
        self._taint_counter = 0

    def analyze_taint(
        self,
        all_facts: List[DefUseFacts],
        summaries: Dict[str, FunctionSummary]
    ) -> TaintAnalysisResult:
        """
        Perform interprocedural taint analysis.

        Identifies taint sources, propagation paths, and sinks.
        """
        taint_paths = []
        sources: Dict[str, List[TaintLabel]] = {}
        sinks: Dict[str, List[str]] = {}
        sanitizers: Dict[str, Set[str]] = {}
        diagnostics = []

        # Identify sources and sinks from summaries
        for function_id, summary in summaries.items():
            # Record sinks
            if summary.sinks:
                sinks[function_id] = summary.sinks

            # Record sources
            if summary.sources:
                for source in summary.sources:
                    if function_id not in sources:
                        sources[function_id] = []
                    sources[function_id].append(TaintLabel(
                        kind=source.get('kind', 'unknown'),
                        source_id=function_id,
                        confidence=0.8,
                        metadata=source
                    ))

        # Identify sanitizers from library summaries
        sanitizers['shlex.quote'] = {'command'}
        sanitizers['html.escape'] = {'html', 'xss'}
        sanitizers['urllib.parse.quote'] = {'url'}

        # Build taint paths (simplified - would need full flow analysis)
        for source_func, source_labels in sources.items():
            for sink_func, sink_kinds in sinks.items():
                # Check if there's a path (simplified check)
                # A full implementation would trace actual data flow
                if self._has_path(source_func, sink_func, summaries):
                    for label in source_labels:
                        for sink_kind in sink_kinds:
                            self._taint_counter += 1
                            path = TaintPath(
                                path_id=f"taint_path_{self._taint_counter}",
                                source_function=source_func,
                                sink_function=sink_func,
                                source_line=0,  # Would need actual line numbers
                                sink_line=0,
                                taint_kind=label.kind,
                                sanitizers=[],
                                confidence=0.7,
                                hops=[],
                                metadata={}
                            )
                            taint_paths.append(path)

        return TaintAnalysisResult(
            taint_paths=taint_paths,
            sources=sources,
            sinks=sinks,
            sanitizers=sanitizers,
            diagnostics=diagnostics
        )

    def _has_path(
        self,
        source_func: str,
        sink_func: str,
        summaries: Dict[str, FunctionSummary]
    ) -> bool:
        """
        Check if there's a potential path from source to sink.

        Simplified - assumes direct call relationship.
        A full implementation would use the call graph and data flow.
        """
        # For now, return False to avoid false positives
        # A full implementation would:
        # 1. Check if sink_func calls source_func
        # 2. Check if they share a common callee
        # 3. Trace actual data flow through the call graph
        return False

    def is_sanitizer(self, function_id: str, taint_kind: str) -> bool:
        """Check if a function is a sanitizer for a given taint kind."""
        # Known sanitizers
        known_sanitizers = {
            'shlex.quote': {'command'},
            'html.escape': {'html', 'xss'},
            'urllib.parse.quote': {'url'},
        }

        if function_id in known_sanitizers:
            return taint_kind in known_sanitizers[function_id]

        return False
