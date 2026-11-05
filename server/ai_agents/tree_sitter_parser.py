"""Tree-sitter parser for multiple languages.

DEPRECATED: This module has been moved to intelligence/parsers/tree_sitter_parser.py.
Import from that location instead. This shim will be removed in a future release.
"""
import warnings

warnings.warn(
    "ai_agents.tree_sitter_parser is deprecated. Import from ai_agents.intelligence.parsers.tree_sitter_parser instead. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export all public functions from the new location
from .intelligence.parsers.tree_sitter_parser import (
    parse_file,
    extract_symbols_with_tree_sitter,
    extract_calls_with_tree_sitter,
    EXT_TO_LANG,
)

__all__ = [
    'parse_file',
    'extract_symbols_with_tree_sitter',
    'extract_calls_with_tree_sitter',
    'EXT_TO_LANG',
]
