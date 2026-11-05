"""Base resolver interface for call graph resolution."""
from typing import Dict, List, Optional, NamedTuple
from dataclasses import dataclass, field


@dataclass
class FileContext:
    """Context information for a file being resolved."""
    file_path: str
    imports: List[Dict[str, any]]  # From extract_imports_with_tree_sitter
    classes: Dict[str, Dict[str, any]]  # Class name to metadata
    functions: Dict[str, Dict[str, any]]  # Function name to metadata
    type_assignments: Dict[str, str] = field(default_factory=dict)  # Variable to type mappings


@dataclass
class ResolutionResult:
    """Result of resolving a call to its target(s)."""
    status: str  # 'static_resolved', 'ambiguous', 'polymorphic', 'unresolved', 'external'
    targets: List[str]  # List of resolved node IDs (empty for unresolved/external)
    candidates: List[str]  # All possible candidates (for ambiguous cases)
    reason: str  # Explanation of resolution decision


class ResolverAdapter:
    """Interface for language-specific call resolution."""
    
    def build_context(self, file_path: str, text: str, graph_nodes: List[Dict]) -> FileContext:
        """Build context for a file.
        
        Args:
            file_path: Path to the file
            text: File contents
            graph_nodes: All nodes in the graph for cross-reference
            
        Returns:
            FileContext with imports, classes, and functions
        """
        raise NotImplementedError
    
    def resolve(self, call: Dict, file_ctx: FileContext, graph_ctx: Dict) -> ResolutionResult:
        """Resolve a call to its target(s).
        
        Args:
            call: Call information from parser (name, receiver, line, etc.)
            file_ctx: Context for the file containing the call
            graph_ctx: Full graph context (all nodes, edges)
            
        Returns:
            ResolutionResult with status, targets, candidates, and reason
        """
        raise NotImplementedError
