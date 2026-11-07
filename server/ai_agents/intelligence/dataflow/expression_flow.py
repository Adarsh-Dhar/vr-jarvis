"""Expression-level control flow analysis for fine-grained CFGs."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
import ast
from ..controlflow.models import ControlFlowGraph, CFGNode, CFGEdge


@dataclass
class ExpressionFlowResult:
    """Result of expression-level flow analysis."""
    added_nodes: List[CFGNode]
    added_edges: List[CFGEdge]
    entry_node_id: str
    exit_node_id: str
    diagnostics: List[Dict[str, Any]]


class ExpressionFlowBuilder:
    """
    Build expression-level control flow for fine-grained analysis.

    This is an opt-in feature that expands expressions into condition nodes.
    For example, `a and b` becomes a chain: a -> (true) -> b, a -> (false) -> exit.
    """

    def __init__(self):
        self._node_counter = 0
        self._edge_counter = 0

    def build_boolop_flow(
        self,
        node: ast.BoolOp,
        cfg: ControlFlowGraph,
        function_id: str,
        file: str,
        source: str
    ) -> ExpressionFlowResult:
        """
        Build control flow for a BoolOp (and/or).

        Short-circuit semantics:
        - `and`: if left is false, skip right; if left is true, evaluate right
        - `or`: if left is true, skip right; if left is false, evaluate right
        """
        added_nodes = []
        added_edges = []
        diagnostics = []

        self._node_counter += 1
        entry_id = f"{function_id}_boolop_entry_{self._node_counter}"

        # Create entry node
        entry_node = CFGNode(
            id=entry_id,
            kind='boolop_entry',
            label=ast.unparse(node) if hasattr(ast, 'unparse') else 'boolop',
            function_id=function_id,
            file=file,
            start_line=node.lineno,
            end_line=node.lineno,
            ast_kind='BoolOp',
            condition=ast.unparse(node) if hasattr(ast, 'unparse') else 'boolop',
            metadata={'op_type': 'And' if isinstance(node.op, ast.And) else 'Or'}
        )
        added_nodes.append(entry_node)

        # Build chain for each value
        prev_node_id = entry_id
        for i, value in enumerate(node.values):
            self._node_counter += 1
            value_id = f"{function_id}_boolop_value_{self._node_counter}"

            value_node = CFGNode(
                id=value_id,
                kind='expression',
                label=ast.unparse(value) if hasattr(ast, 'unparse') else 'value',
                function_id=function_id,
                file=file,
                start_line=value.lineno,
                end_line=value.lineno,
                ast_kind='Expr',
                metadata={'value_index': i}
            )
            added_nodes.append(value_node)

            # Add edge from previous to this value
            self._edge_counter += 1
            edge = CFGEdge(
                id=f"{function_id}_edge_{self._edge_counter}",
                source=prev_node_id,
                target=value_id,
                kind='next',
                condition=None,
                evidence={'file': file}
            )
            added_edges.append(edge)

            prev_node_id = value_id

        # Create exit node
        self._node_counter += 1
        exit_id = f"{function_id}_boolop_exit_{self._node_counter}"

        exit_node = CFGNode(
            id=exit_id,
            kind='boolop_exit',
            label='boolop_result',
            function_id=function_id,
            file=file,
            start_line=node.lineno,
            end_line=node.lineno,
            ast_kind='BoolOp',
            metadata={}
        )
        added_nodes.append(exit_node)

        # Add edge from last value to exit
        self._edge_counter += 1
        edge = CFGEdge(
            id=f"{function_id}_edge_{self._edge_counter}",
            source=prev_node_id,
            target=exit_id,
            kind='next',
            condition=None,
            evidence={'file': file}
        )
        added_edges.append(edge)

        return ExpressionFlowResult(
            added_nodes=added_nodes,
            added_edges=added_edges,
            entry_node_id=entry_id,
            exit_node_id=exit_id,
            diagnostics=diagnostics
        )

    def build_ifexp_flow(
        self,
        node: ast.IfExp,
        cfg: ControlFlowGraph,
        function_id: str,
        file: str,
        source: str
    ) -> ExpressionFlowResult:
        """
        Build control flow for an IfExp (ternary expression).

        Structure: test -> (true) -> body, test -> (false) -> orelse
        """
        added_nodes = []
        added_edges = []
        diagnostics = []

        self._node_counter += 1
        test_id = f"{function_id}_ifexp_test_{self._node_counter}"

        # Create test node
        test_node = CFGNode(
            id=test_id,
            kind='condition',
            label=ast.unparse(node.test) if hasattr(ast, 'unparse') else 'condition',
            function_id=function_id,
            file=file,
            start_line=node.test.lineno,
            end_line=node.test.lineno,
            ast_kind='IfExp',
            condition=ast.unparse(node.test) if hasattr(ast, 'unparse') else 'condition',
            metadata={}
        )
        added_nodes.append(test_node)

        # Create body node
        self._node_counter += 1
        body_id = f"{function_id}_ifexp_body_{self._node_counter}"

        body_node = CFGNode(
            id=body_id,
            kind='expression',
            label=ast.unparse(node.body) if hasattr(ast, 'unparse') else 'body',
            function_id=function_id,
            file=file,
            start_line=node.body.lineno,
            end_line=node.body.lineno,
            ast_kind='Expr',
            metadata={'branch': 'true'}
        )
        added_nodes.append(body_node)

        # Create orelse node
        self._node_counter += 1
        orelse_id = f"{function_id}_ifexp_orelse_{self._node_counter}"

        orelse_node = CFGNode(
            id=orelse_id,
            kind='expression',
            label=ast.unparse(node.orelse) if hasattr(ast, 'unparse') else 'orelse',
            function_id=function_id,
            file=file,
            start_line=node.orelse.lineno,
            end_line=node.orelse.lineno,
            ast_kind='Expr',
            metadata={'branch': 'false'}
        )
        added_nodes.append(orelse_node)

        # Create exit node
        self._node_counter += 1
        exit_id = f"{function_id}_ifexp_exit_{self._node_counter}"

        exit_node = CFGNode(
            id=exit_id,
            kind='ifexp_exit',
            label='ifexp_result',
            function_id=function_id,
            file=file,
            start_line=node.lineno,
            end_line=node.lineno,
            ast_kind='IfExp',
            metadata={}
        )
        added_nodes.append(exit_node)

        # Add edges: test -> body (true), test -> orelse (false)
        self._edge_counter += 1
        true_edge = CFGEdge(
            id=f"{function_id}_edge_{self._edge_counter}",
            source=test_id,
            target=body_id,
            kind='true',
            condition={'predicate': ast.unparse(node.test) if hasattr(ast, 'unparse') else 'condition', 'polarity': True},
            evidence={'file': file}
        )
        added_edges.append(true_edge)

        self._edge_counter += 1
        false_edge = CFGEdge(
            id=f"{function_id}_edge_{self._edge_counter}",
            source=test_id,
            target=orelse_id,
            kind='false',
            condition={'predicate': ast.unparse(node.test) if hasattr(ast, 'unparse') else 'condition', 'polarity': False},
            evidence={'file': file}
        )
        added_edges.append(false_edge)

        # Add edges: body -> exit, orelse -> exit
        self._edge_counter += 1
        body_exit_edge = CFGEdge(
            id=f"{function_id}_edge_{self._edge_counter}",
            source=body_id,
            target=exit_id,
            kind='next',
            condition=None,
            evidence={'file': file}
        )
        added_edges.append(body_exit_edge)

        self._edge_counter += 1
        orelse_exit_edge = CFGEdge(
            id=f"{function_id}_edge_{self._edge_counter}",
            source=orelse_id,
            target=exit_id,
            kind='next',
            condition=None,
            evidence={'file': file}
        )
        added_edges.append(orelse_exit_edge)

        return ExpressionFlowResult(
            added_nodes=added_nodes,
            added_edges=added_edges,
            entry_node_id=test_id,
            exit_node_id=exit_id,
            diagnostics=diagnostics
        )
