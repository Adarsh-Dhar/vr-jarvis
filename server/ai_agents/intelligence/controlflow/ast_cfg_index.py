"""AST-to-CFG index for mapping expressions to execution nodes."""
from collections import defaultdict
from typing import List, Dict, Any, Optional, Set
import ast


class ASTCFGIndex:
    """Maps AST nodes to their corresponding CFG execution nodes."""

    def __init__(self):
        self.ast_to_cfg_nodes: Dict[int, List[str]] = defaultdict(list)
        self.expression_roles: Dict[int, List[str]] = defaultdict(list)
        self.source_locations: Dict[int, Dict[str, int]] = {}
        self.diagnostics: List[Dict[str, Any]] = []

    def bind(self, ast_node: ast.AST, cfg_node_id: str, role: str) -> None:
        """Bind an AST node to a CFG node with a specific role."""
        if not isinstance(ast_node, ast.AST):
            self.diagnostics.append({
                'code': 'invalid_ast_node',
                'message': f'Attempted to bind non-AST object: {type(ast_node)}',
                'severity': 'error'
            })
            return

        key = id(ast_node)
        if cfg_node_id not in self.ast_to_cfg_nodes[key]:
            self.ast_to_cfg_nodes[key].append(cfg_node_id)
        if role not in self.expression_roles[key]:
            self.expression_roles[key].append(role)

        # Preserve source location
        if key not in self.source_locations:
            self.source_locations[key] = {
                'lineno': getattr(ast_node, 'lineno', None),
                'col_offset': getattr(ast_node, 'col_offset', None),
                'end_lineno': getattr(ast_node, 'end_lineno', None),
                'end_col_offset': getattr(ast_node, 'end_col_offset', None),
            }

    def bind_expression_tree(
        self,
        expression: Optional[ast.AST],
        cfg_node_id: str,
        role: str = "expression"
    ) -> None:
        """Bind an entire expression tree to a CFG node."""
        if expression is None:
            return
        for node in ast.walk(expression):
            # Support both expr nodes and pattern nodes
            if isinstance(node, (ast.expr, ast.pattern)):
                self.bind(node, cfg_node_id, role)

    def get_cfg_nodes(self, ast_node: ast.AST) -> List[str]:
        """Get all CFG node IDs associated with an AST node."""
        key = id(ast_node)
        return self.ast_to_cfg_nodes.get(key, [])

    def get_primary_cfg_node(self, ast_node: ast.AST) -> Optional[str]:
        """Get the primary (first) CFG node ID for an AST node."""
        nodes = self.get_cfg_nodes(ast_node)
        return nodes[0] if nodes else None

    def get_roles(self, ast_node: ast.AST) -> List[str]:
        """Get all roles associated with an AST node."""
        key = id(ast_node)
        return self.expression_roles.get(key, [])

    def get_primary_role(self, ast_node: ast.AST) -> Optional[str]:
        """Get the primary (first) role for an AST node."""
        roles = self.get_roles(ast_node)
        return roles[0] if roles else None

    def get_source_location(self, ast_node: ast.AST) -> Optional[Dict[str, int]]:
        """Get source location for an AST node."""
        key = id(ast_node)
        return self.source_locations.get(key)

    def get_diagnostics(self) -> List[Dict[str, Any]]:
        """Get all diagnostics from mapping operations."""
        return self.diagnostics
