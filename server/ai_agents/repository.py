"""Repository catalogue: lists repos under /repository, indexes one into a graph, makes it the active repo.

DEPRECATED: This module has been split into intelligence/graph_engine/store.py and intelligence/graph_engine/indexer.py.
Import from those modules instead. This shim will be removed in a future release.
"""
import warnings

warnings.warn(
    "ai_agents.repository is deprecated. Import from ai_agents.intelligence.graph_engine.store "
    "and ai_agents.intelligence.graph_engine.indexer instead. This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export all public functions from the new locations
from .intelligence.graph_engine.store import (
    list_repos,
    build_graph,
    info,
    activate,
    list_tree,
    read_browser_file,
    _source_files,
    SKIP_DIRS,
    JS_EXT,
    EXTS,
    MAX_FILE_BYTES,
    MAX_BROWSER_FILE_BYTES,
    BROWSER_SKIP_DIRS,
)

from .intelligence.graph_engine.indexer import (
    index_repo,
    _is_test,
    _dotted,
    _cluster,
    _compute_layer,
    _symbols,
    _imports,
)

# Re-export regex patterns for backward compatibility
import re
_FN = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)')
_ARROW = re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s+)?'
                    r'(?:function\b|\([^)]*\)\s*(?::[^=]+)?=>|[A-Za-z_$][\w$]*\s*=>)')
_CLASS = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)')
_CALL = re.compile(r'\b([A-Za-z_$][\w$]*)\s*\(')
_METHOD_CALL = re.compile(r'\b(?:self|this|[A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\s*\(')
_CONSTRUCTOR = re.compile(r'\bnew\s+([A-Za-z_$][\w$]*)\s*\(')
_IMPORT = re.compile(r'''(?:from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)|^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+)))''', re.M)

__all__ = [
    'list_repos',
    'build_graph',
    'info',
    'activate',
    'list_tree',
    'read_browser_file',
    'index_repo',
    '_source_files',
    '_is_test',
    '_dotted',
    '_cluster',
    '_compute_layer',
    '_symbols',
    '_imports',
    'SKIP_DIRS',
    'JS_EXT',
    'EXTS',
    'MAX_FILE_BYTES',
    'MAX_BROWSER_FILE_BYTES',
    'BROWSER_SKIP_DIRS',
    '_FN',
    '_ARROW',
    '_CLASS',
    '_CALL',
    '_METHOD_CALL',
    '_CONSTRUCTOR',
    '_IMPORT',
]
