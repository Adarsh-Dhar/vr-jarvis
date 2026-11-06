"""Python symbol locator for finding function AST nodes by qualified name."""
import ast
from typing import Optional, List, Dict, Any


def find_function_ast(
    tree: ast.AST,
    graph_symbol: Dict[str, Any]
) -> Optional[ast.FunctionDef]:
    """
    Find a function AST node by graph symbol information.

    Uses the graph symbol's:
    - Canonical qualified name
    - File path
    - Start line
    - End line
    - Symbol kind

    Returns the matching FunctionDef or AsyncFunctionDef, or None if not found.
    """
    if not graph_symbol:
        return None

    target_name = graph_symbol.get('qualname') or graph_symbol.get('name')
    target_file = graph_symbol.get('file')
    target_start = graph_symbol.get('start')
    target_end = graph_symbol.get('end')
    target_kind = graph_symbol.get('kind')

    if not target_name or not target_file:
        return None

    # Collect all candidate functions
    candidates: List[ast.FunctionDef] = []

    class FunctionVisitor(ast.NodeVisitor):
        def __init__(self):
            self.functions = []

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self.functions.append(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            self.functions.append(node)
            self.generic_visit(node)

    visitor = FunctionVisitor()
    visitor.visit(tree)
    candidates = visitor.functions

    # Filter by line range if provided
    if target_start is not None:
        candidates = [
            f for f in candidates
            if f.lineno == target_start
        ]

    # Filter by end line if provided
    if target_end is not None:
        candidates = [
            f for f in candidates
            if (f.end_lineno or f.lineno) == target_end
        ]

    # Filter by name
    candidates = [
        f for f in candidates
        if f.name == target_name
    ]

    # If we have exactly one match, return it
    if len(candidates) == 1:
        return candidates[0]

    # If we have multiple matches, try to disambiguate by qualified name
    if len(candidates) > 1:
        # In a real implementation, we'd compute qualified names from the AST
        # For now, return the first match
        return candidates[0]

    # No match found
    return None


def resolve_function_by_name(
    tree: ast.AST,
    function_name: str,
    file_path: str
) -> Optional[ast.FunctionDef]:
    """
    Resolve a function by simple name (fallback method).

    This is less reliable than find_function_ast but can be used when
    full symbol information is not available.
    """
    class NameVisitor(ast.NodeVisitor):
        def __init__(self, target_name):
            self.target_name = target_name
            self.matches = []

        def visit_FunctionDef(self, node: ast.FunctionDef):
            if node.name == self.target_name:
                self.matches.append(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            if node.name == self.target_name:
                self.matches.append(node)
            self.generic_visit(node)

    visitor = NameVisitor(function_name)
    visitor.visit(tree)

    if len(visitor.matches) == 1:
        return visitor.matches[0]
    elif len(visitor.matches) > 1:
        # Multiple matches - this is ambiguous
        return None
    else:
        return None
