"""Central source-language detection shared by the indexer, store and parsers.

Every consumer must use :func:`language_for_path` so a file is never labelled
with the wrong language (the old indexer labelled every non-Python file
``typescript``, including plain JavaScript).
"""
from __future__ import annotations

from pathlib import PurePosixPath

# Extension -> canonical language id. The id matches the keys used by the
# resolver registry and the ``language`` field on graph nodes.
EXT_LANGUAGE = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.go': 'go',
    '.rs': 'rust',
    '.java': 'java',
    '.cs': 'csharp',
    '.c': 'cpp',
    '.h': 'cpp',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.cxx': 'cpp',
    '.hpp': 'cpp',
}

# Language families used by the tree-sitter extraction helpers.
LANGUAGE_FAMILY = {
    'python': 'python',
    'javascript': 'js',
    'typescript': 'js',
    'go': 'go',
    'rust': 'rust',
    'java': 'java',
    'csharp': 'csharp',
    'cpp': 'cpp',
}

SOURCE_EXTS = frozenset(EXT_LANGUAGE)


def language_for_path(path: str) -> str:
    """Return the canonical language id for a file path.

    Unknown extensions return ``'unknown'`` rather than guessing.
    """
    suffix = PurePosixPath(path.replace('\\', '/')).suffix.lower()
    return EXT_LANGUAGE.get(suffix, 'unknown')


def language_family(path_or_language: str) -> str:
    """Return the parser family ('python', 'js', 'go', ...) for a path or language id."""
    if path_or_language in LANGUAGE_FAMILY:
        return LANGUAGE_FAMILY[path_or_language]
    return LANGUAGE_FAMILY.get(language_for_path(path_or_language), 'unknown')
