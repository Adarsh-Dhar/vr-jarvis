"""Resolver registry mapping languages to resolver adapters."""
from typing import Dict, Optional
from .base import ResolverAdapter
from .python_resolver import PythonResolver
from .javascript_resolver import JavaScriptResolver


# Mapping from language identifiers to resolver classes
# Language identifiers match those used in graph nodes. A language is only
# registered here when a real resolver exists; languages with only tree-sitter
# grammar support stay unresolvable (call sites recorded as unresolved).
_RESOLVERS: Dict[str, type] = {
    'python': PythonResolver,
    'javascript': JavaScriptResolver,
    'typescript': JavaScriptResolver,
}


def get_resolver(language: str) -> Optional[ResolverAdapter]:
    """Get a resolver for the given language."""
    resolver_class = _RESOLVERS.get(language.lower())
    if resolver_class:
        return resolver_class()
    return None


def register_resolver(language: str, resolver_class: type):
    """Register a new resolver for a language."""
    _RESOLVERS[language.lower()] = resolver_class


def supported_languages() -> list:
    """Return list of supported languages."""
    return list(_RESOLVERS.keys())
