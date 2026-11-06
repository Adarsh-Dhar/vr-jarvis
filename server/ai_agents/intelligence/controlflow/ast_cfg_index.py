"""AST-to-CFG index for mapping expressions to execution nodes."""
from collections import defaultdict
from typing import List, Dict, Any, Optional
import ast


class ASTCFGIndex:
    """Maps AST nodes to their corresponding CFG execution nodes."""

    def __init__(self):
        self.ast_to_cfg_nodes: Dict[int, List[str]] = defaultdict(list)
        self.expression_roles: Dict[int, str] = {}

    def bind(self, ast_node: ast.AST, cfg_node_id: str, role: str) -> None:
        """Bind an AST node to a CFG node with a specific role."""
        key = id(ast_node)
        if cfg_node_id not in self.ast_to_cfg_nodes[key]:
            self.ast_to_cfg_nodes[key].append(cfg_node_id)
        self.expression_roles[key] = role

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
            if isinstance(node, ast.expr):
                self.bind(node, cfg_node_id, role)

    def get_cfg_nodes(self, ast_node: ast.AST) -> List[str]:
        """Get all CFG node IDs associated with an AST node."""
        key = id(ast_node)
        return self.ast_to_cfg_nodes.get(key, [])

    def get_primary_cfg_node(self, ast_node: ast.AST) -> Optional[str]:
        """Get the primary (first) CFG node ID for an AST node."""
        nodes = self.get_cfg_nodes(ast_node)
        return nodes[0] if nodes else None
