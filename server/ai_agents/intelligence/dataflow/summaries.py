"""Call summaries and library models for function call analysis."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
import json
from pathlib import Path


@dataclass
class FunctionSummary:
    """Summary of a function's behavior for data-flow analysis."""
    qualified_name: str  # e.g., 'builtins.abs', 'list.append'
    pure: bool = False  # True if function has no side effects
    returns_from: List[str] = field(default_factory=list)  # Which arguments are returned (e.g., [0] for first arg)
    mutates: List[str] = field(default_factory=list)  # Which arguments are mutated (e.g., ['self'] for methods)
    reads: List[str] = field(default_factory=list)  # Which arguments are read
    raises: List[str] = field(default_factory=list)  # Exception types that may be raised
    sinks: List[str] = field(default_factory=list)  # Security sinks (e.g., 'sql', 'command')
    sources: List[str] = field(default_factory=list)  # Taint sources
    metadata: Dict[str, Any] = field(default_factory=dict)


class SummaryRegistry:
    """
    Registry of function summaries for library functions.

    Replaces hard-coded mutation lists with a declarative, extensible system.
    """

    def __init__(self):
        self._summaries: Dict[str, FunctionSummary] = {}
        self._load_builtin_summaries()

    def _load_builtin_summaries(self):
        """Load built-in function summaries."""
        # Pure built-in functions
        pure_functions = [
            ('builtins.abs', {'pure': True, 'returns_from': [0]}),
            ('builtins.len', {'pure': True, 'returns_from': [0]}),
            ('builtins.max', {'pure': True, 'returns_from': [0]}),
            ('builtins.min', {'pure': True, 'returns_from': [0]}),
            ('builtins.sum', {'pure': True, 'returns_from': [0]}),
            ('builtins.sorted', {'pure': True, 'returns_from': [0]}),
            ('builtins.reversed', {'pure': True, 'returns_from': [0]}),
            ('builtins.map', {'pure': True, 'returns_from': [0]}),
            ('builtins.filter', {'pure': True, 'returns_from': [0]}),
            ('builtins.zip', {'pure': True, 'returns_from': [0]}),
            ('builtins.range', {'pure': True, 'returns_from': [0]}),
            ('builtins.enumerate', {'pure': True, 'returns_from': [0]}),
            ('builtins.str', {'pure': True, 'returns_from': [0]}),
            ('builtins.int', {'pure': True, 'returns_from': [0]}),
            ('builtins.float', {'pure': True, 'returns_from': [0]}),
            ('builtins.bool', {'pure': True, 'returns_from': [0]}),
            ('builtins.list', {'pure': True, 'returns_from': [0]}),
            ('builtins.dict', {'pure': True, 'returns_from': [0]}),
            ('builtins.set', {'pure': True, 'returns_from': [0]}),
            ('builtins.tuple', {'pure': True, 'returns_from': [0]}),
        ]

        for name, info in pure_functions:
            self.add_summary(FunctionSummary(qualified_name=name, **info))

        # Mutating list methods
        list_mutations = [
            ('list.append', {'mutates': ['self'], 'reads': [1]}),
            ('list.extend', {'mutates': ['self'], 'reads': [1]}),
            ('list.insert', {'mutates': ['self'], 'reads': [1, 2]}),
            ('list.remove', {'mutates': ['self'], 'reads': [1], 'raises': ['ValueError']}),
            ('list.pop', {'mutates': ['self'], 'returns_from': [0], 'raises': ['IndexError']}),
            ('list.clear', {'mutates': ['self']}),
            ('list.sort', {'mutates': ['self'], 'reads': [1] if True else []}),  # key param optional
            ('list.reverse', {'mutates': ['self']}),
        ]

        for name, info in list_mutations:
            self.add_summary(FunctionSummary(qualified_name=name, **info))

        # Mutating dict methods
        dict_mutations = [
            ('dict.update', {'mutates': ['self'], 'reads': [1]}),
            ('dict.setdefault', {'mutates': ['self'], 'reads': [1, 2], 'returns_from': [0]}),
            ('dict.pop', {'mutates': ['self'], 'reads': [1], 'returns_from': [0], 'raises': ['KeyError']}),
            ('dict.popitem', {'mutates': ['self'], 'returns_from': [0], 'raises': ['KeyError']}),
            ('dict.clear', {'mutates': ['self']}),
        ]

        for name, info in dict_mutations:
            self.add_summary(FunctionSummary(qualified_name=name, **info))

        # Mutating set methods
        set_mutations = [
            ('set.add', {'mutates': ['self'], 'reads': [1]}),
            ('set.discard', {'mutates': ['self'], 'reads': [1]}),
            ('set.remove', {'mutates': ['self'], 'reads': [1], 'raises': ['KeyError']}),
            ('set.pop', {'mutates': ['self'], 'returns_from': [0], 'raises': ['KeyError']}),
            ('set.clear', {'mutates': ['self']}),
        ]

        for name, info in set_mutations:
            self.add_summary(FunctionSummary(qualified_name=name, **info))

        # Security sinks
        security_sinks = [
            ('os.system', {'pure': False, 'sinks': ['command'], 'reads': [0], 'raises': ['OSError']}),
            ('subprocess.run', {'pure': False, 'sinks': ['command'], 'reads': [0], 'raises': ['subprocess.SubprocessError']}),
            ('subprocess.Popen', {'pure': False, 'sinks': ['command'], 'reads': [0]}),
            ('eval', {'pure': False, 'sinks': ['code'], 'reads': [0], 'raises': ['SyntaxError', 'NameError', 'TypeError']}),
            ('exec', {'pure': False, 'sinks': ['code'], 'reads': [0], 'raises': ['SyntaxError', 'NameError', 'TypeError']}),
        ]

        for name, info in security_sinks:
            self.add_summary(FunctionSummary(qualified_name=name, **info))

        # Database sinks
        database_sinks = [
            ('sqlite3.Cursor.execute', {'pure': False, 'sinks': ['sql'], 'reads': [1], 'returns_from': [0], 'raises': ['sqlite3.Error']}),
            ('sqlite3.Cursor.executemany', {'pure': False, 'sinks': ['sql'], 'reads': [1], 'returns_from': [0], 'raises': ['sqlite3.Error']}),
        ]

        for name, info in database_sinks:
            self.add_summary(FunctionSummary(qualified_name=name, **info))

    def add_summary(self, summary: FunctionSummary):
        """Add a function summary to the registry."""
        self._summaries[summary.qualified_name] = summary

    def get_summary(self, qualified_name: str) -> Optional[FunctionSummary]:
        """Get a function summary by qualified name."""
        return self._summaries.get(qualified_name)

    def get_summary_by_method_name(self, method_name: str) -> Optional[FunctionSummary]:
        """
        Get a summary by method name only (fallback for when resolution fails).

        Returns the first matching summary across all types.
        """
        for qualified_name, summary in self._summaries.items():
            if qualified_name.endswith('.' + method_name):
                return summary
        return None

    def has_summary(self, qualified_name: str) -> bool:
        """Check if a summary exists for a function."""
        return qualified_name in self._summaries

    def load_from_file(self, file_path: Path):
        """Load summaries from a JSON file."""
        with open(file_path) as f:
            data = json.load(f)

        for item in data:
            summary = FunctionSummary(**item)
            self.add_summary(summary)

    def save_to_file(self, file_path: Path):
        """Save summaries to a JSON file."""
        data = []
        for summary in self._summaries.values():
            data.append({
                'qualified_name': summary.qualified_name,
                'pure': summary.pure,
                'returns_from': summary.returns_from,
                'mutates': summary.mutates,
                'reads': summary.reads,
                'raises': summary.raises,
                'sinks': summary.sinks,
                'sources': summary.sources,
                'metadata': summary.metadata,
            })

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)


def infer_call_summary(
    operation,
    facts,
    registry: SummaryRegistry
) -> FunctionSummary:
    """
    Infer a summary for a call operation.

    Tries to resolve the call to a qualified name and look up its summary.
    Falls back to method name heuristics if resolution fails.
    """
    # Try to extract qualified name from expression
    expr = operation.expression

    # Check for method call: obj.method(...)
    if '.' in expr and '(' in expr:
        method_start = expr.rfind('.')
        method_end = expr.find('(')
        if method_start < method_end:
            method_name = expr[method_start + 1:method_end].strip()

            # Try to get summary by method name (fallback)
            summary = registry.get_summary_by_method_name(method_name)
            if summary:
                return summary

    # Default: unknown summary
    return FunctionSummary(
        qualified_name='unknown',
        pure=False,
        metadata={'inferred': True, 'expression': expr}
    )
