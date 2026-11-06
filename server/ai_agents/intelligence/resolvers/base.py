"""Base resolver interface and resolution-result contract for call graphs."""
from typing import Dict, List, Optional
from dataclasses import dataclass, field

# Resolution statuses. Only ``static_resolved`` may produce a confirmed
# ``calls`` edge; ``polymorphic``/``ambiguous`` produce ``may_call`` edges;
# ``unresolved``/``dynamic``/``external`` produce no internal edge at all.
STATUS_STATIC_RESOLVED = 'static_resolved'
STATUS_POLYMORPHIC = 'polymorphic'
STATUS_AMBIGUOUS = 'ambiguous'
STATUS_UNRESOLVED = 'unresolved'
STATUS_EXTERNAL = 'external'
STATUS_DYNAMIC = 'dynamic'

# Confidence policy (documented, deterministic — not model-guessed):
#   static_resolved -> 1.0   (exact target proven from AST + bindings)
#   polymorphic     -> 0.7   (target set proven, dispatch target not)
#   ambiguous       -> 0.4   (candidates exist, cannot be distinguished)
#   unresolved/dynamic/external -> None (no edge)
CONFIDENCE = {
    STATUS_STATIC_RESOLVED: 1.0,
    STATUS_POLYMORPHIC: 0.7,
    STATUS_AMBIGUOUS: 0.4,
}

# Edge kinds derived from status.
STATUS_TO_EDGE_KIND = {
    STATUS_STATIC_RESOLVED: ('calls', 'confirmed'),
    STATUS_POLYMORPHIC: ('may_call', 'possible'),
    STATUS_AMBIGUOUS: ('may_call', 'ambiguous'),
}


@dataclass
class FileContext:
    """Context information for a file being resolved."""
    file_path: str
    imports: List[Dict]            # structured imports (module, name, alias, kind, line, level)
    classes: Dict[str, Dict]       # class qualname -> metadata (bases, methods, span)
    functions: Dict[str, Dict]     # function qualname -> metadata
    type_assignments: Dict[str, str] = field(default_factory=dict)
    analysis: Optional[Dict] = None  # full python_ast.analyze_python_source result
    language: str = 'python'


@dataclass
class ResolutionResult:
    """Result of resolving a call site, preserving the evidence for the decision."""
    status: str                    # see STATUS_* constants
    targets: List[str] = field(default_factory=list)      # confirmed target node ids
    candidates: List[str] = field(default_factory=list)   # all possible target node ids
    reason: str = ''
    confidence: Optional[float] = None
    resolution_method: str = ''    # e.g. 'import_binding', 'self_method', 'mro_super', 'type_inference'
    evidence: List[Dict] = field(default_factory=list)
    dispatch_kind: str = 'static'  # 'static' | 'virtual' | 'dynamic' | 'external' | 'unknown'
    diagnostics: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.confidence is None:
            self.confidence = CONFIDENCE.get(self.status)


class ResolverAdapter:
    """Interface for language-specific call resolution."""

    language: str = 'unknown'

    def build_context(self, file_path: str, text: str, graph_nodes: List[Dict],
                      analysis: Optional[Dict] = None) -> FileContext:
        """Build context for a file.

        Args:
            file_path: repo-relative path of the file
            text: file contents
            graph_nodes: all symbol nodes in the graph (cross-reference)
            analysis: optional pre-computed parser analysis for this file

        Returns:
            FileContext with imports, classes, functions and analysis
        """
        raise NotImplementedError

    def resolve(self, call: Dict, file_ctx: FileContext, graph_ctx: Dict) -> ResolutionResult:
        """Resolve one call site to its target(s).

        Args:
            call: call-site dict (name, receiver, receiver_root, call_type,
                  caller_id, line, column, callsite_id, ...)
            file_ctx: context for the file containing the call
            graph_ctx: repository-wide context (nodes, module map, class index,
                       analyses, file symbols)

        Returns:
            ResolutionResult with status, targets, candidates and evidence
        """
        raise NotImplementedError
