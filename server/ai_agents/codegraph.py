"""Central graph access layer with caching and standardized traversal.

DEPRECATED: This module has been moved to intelligence/graph_engine/codegraph.py.
Import from that location instead. This shim will be removed in a future release.
"""
import warnings

warnings.warn(
    "ai_agents.codegraph is deprecated. Import from ai_agents.intelligence.graph_engine.codegraph instead. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export all public classes and functions from the new location
from .intelligence.graph_engine.codegraph import (
    CodeGraph,
    get_graph,
    load_current_graph,
    clear_cache,
)

__all__ = [
    'CodeGraph',
    'get_graph',
    'load_current_graph',
    'clear_cache',
]
