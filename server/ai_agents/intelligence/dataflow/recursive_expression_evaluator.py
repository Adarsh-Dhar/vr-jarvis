"""Recursive expression evaluator for DFG extraction."""
import ast
from typing import List, Dict, Any, Optional, Set, Tuple
from .models import VariableUse, ExpressionFact


class ExpressionEvaluationContext:
    """Context for expression evaluation."""

    def __init__(self, function_id: str, file: str, local_vars: Set[str], cfg_node_map: Dict[str, str], ast_index, facts):
        self.function_id = function_id
        self.file = file
        self.local_vars = local_vars
        self.cfg_node_map = cfg_node_map
        self.ast_index = ast_index
        self.facts = facts
        self._operation_counter = 0
        self._use_counter = 0
        self._evaluated_nodes: Set[int] = set()  # Track evaluated nodes to avoid duplicates

    def generate_operation_id(self) -> str:
        """Generate a unique operation ID."""
        self._operation_counter += 1
        return f"{self.function_id}_op_{self._operation_counter}"

    def generate_use_id(self, variable: str) -> str:
        """Generate a unique use ID."""
        self._use_counter += 1
        return f"{self.function_id}_use_{variable}_{self._use_counter}"

    def get_cfg_node_ids(self, node: ast.AST) -> List[str]:
        """Get CFG node IDs for an AST node."""
        if not self.ast_index:
            return []
        node_ids = self.ast_index.get_cfg_nodes(node)
        return node_ids if node_ids else []

    def is_local_var(self, name: str) -> bool:
        """Check if a name is a local variable."""
        return name in self.local_vars or not self.local_vars


class RecursiveExpressionEvaluator:
    """Recursively evaluates expressions and creates DFG facts."""
    
    def __init__(self, ctx: ExpressionEvaluationContext):
        self.ctx = ctx
    
    def evaluate(self, node: ast.AST) -> Tuple[List[str], Optional[str], List[str]]:
        """
        Evaluate an expression recursively.

        Returns:
            Tuple of (use_ids created, operation_id created or None, child_operation_ids)
        """
        node_id = id(node)
        if node_id in self.ctx._evaluated_nodes:
            return [], None, []

        self.ctx._evaluated_nodes.add(node_id)

        if isinstance(node, ast.Name):
            return self._evaluate_name(node)
        elif isinstance(node, ast.Constant):
            return self._evaluate_constant(node)
        elif isinstance(node, ast.BinOp):
            return self._evaluate_binop(node)
        elif isinstance(node, ast.UnaryOp):
            return self._evaluate_unaryop(node)
        elif isinstance(node, ast.Compare):
            return self._evaluate_compare(node)
        elif isinstance(node, ast.BoolOp):
            return self._evaluate_boolop(node)
        elif isinstance(node, ast.Call):
            return self._evaluate_call(node)
        elif isinstance(node, ast.Attribute):
            return self._evaluate_attribute(node)
        elif isinstance(node, ast.Subscript):
            return self._evaluate_subscript(node)
        elif isinstance(node, ast.IfExp):
            return self._evaluate_ifexp(node)
        elif isinstance(node, ast.Lambda):
            return self._evaluate_lambda(node)
        elif isinstance(node, ast.List):
            return self._evaluate_list(node)
        elif isinstance(node, ast.Tuple):
            return self._evaluate_tuple(node)
        elif isinstance(node, ast.Dict):
            return self._evaluate_dict(node)
        elif isinstance(node, ast.Set):
            return self._evaluate_set(node)
        elif isinstance(node, ast.ListComp):
            return self._evaluate_listcomp(node)
        elif isinstance(node, ast.SetComp):
            return self._evaluate_setcomp(node)
        elif isinstance(node, ast.DictComp):
            return self._evaluate_dictcomp(node)
        elif isinstance(node, ast.GeneratorExp):
            return self._evaluate_generatorexp(node)
        elif isinstance(node, ast.Yield):
            return self._evaluate_yield(node)
        elif isinstance(node, ast.YieldFrom):
            return self._evaluate_yieldfrom(node)
        elif isinstance(node, ast.Await):
            return self._evaluate_await(node)
        else:
            # Generic fallback
            return self._evaluate_generic(node)
    
    def _evaluate_name(self, node: ast.Name) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate a name reference."""
        if isinstance(node.ctx, ast.Load) and self.ctx.is_local_var(node.id):
            use_id = self.ctx.generate_use_id(node.id)
            binding_key = f"{self.ctx.function_id}::{node.id}"
            cfg_node_ids = self.ctx.get_cfg_node_ids(node)

            self.ctx.facts.uses.append(VariableUse(
                id=use_id,
                variable=node.id,
                function_id=self.ctx.function_id,
                file=self.ctx.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=ast.unparse(node) if hasattr(ast, 'unparse') else node.id,
            ))
            return [use_id], None, []
        return [], None, []
    
    def _evaluate_constant(self, node: ast.Constant) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate a constant literal."""
        # Constants don't create uses or operations
        return [], None, []
    
    def _evaluate_binop(self, node: ast.BinOp) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate a binary operation."""
        # Recursively evaluate left and right
        left_uses, left_op_id, left_child_ops = self.evaluate(node.left)
        right_uses, right_op_id, right_child_ops = self.evaluate(node.right)

        all_uses = left_uses + right_uses
        child_ops = [op_id for op_id in [left_op_id, right_op_id] if op_id] + left_child_ops + right_child_ops

        # Create operation fact
        op_type = type(node.op).__name__
        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else str(op_type)
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation=op_type,
            input_use_ids=all_uses,
            input_operation_ids=child_ops,
            output_definition_ids=[],
            metadata={'op_type': op_type},
        ))

        return all_uses, op_id, child_ops
    
    def _evaluate_unaryop(self, node: ast.UnaryOp) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate a unary operation."""
        operand_uses, operand_op_id, operand_child_ops = self.evaluate(node.operand)
        child_ops = [operand_op_id] if operand_op_id else []
        child_ops.extend(operand_child_ops)

        op_type = type(node.op).__name__
        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else str(op_type)
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation=op_type,
            input_use_ids=operand_uses,
            input_operation_ids=child_ops,
            output_definition_ids=[],
            metadata={'op_type': op_type},
        ))

        return operand_uses, op_id, child_ops
    
    def _evaluate_compare(self, node: ast.Compare) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate a comparison operation."""
        # Evaluate left and comparators
        left_uses, left_op_id, left_child_ops = self.evaluate(node.left)
        all_uses = left_uses[:]
        child_ops = [left_op_id] if left_op_id else []
        child_ops.extend(left_child_ops)

        for comparator in node.comparators:
            comp_uses, comp_op_id, comp_child_ops = self.evaluate(comparator)
            all_uses.extend(comp_uses)
            if comp_op_id:
                child_ops.append(comp_op_id)
            child_ops.extend(comp_child_ops)

        # Create operation for each comparison
        op_ids = []
        for i, op in enumerate(node.ops):
            op_type = type(op).__name__
            op_id = self.ctx.generate_operation_id()
            expression = ast.unparse(node) if hasattr(ast, 'unparse') else str(op_type)
            cfg_node_ids = self.ctx.get_cfg_node_ids(node)

            self.ctx.facts.operations.append(ExpressionFact(
                id=op_id,
                function_id=self.ctx.function_id,
                file=self.ctx.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                cfg_node_ids=cfg_node_ids,
                expression=expression,
                operation=op_type,
                input_use_ids=all_uses,
                input_operation_ids=child_ops,
                output_definition_ids=[],
                metadata={'op_type': op_type, 'comparison_index': i},
            ))
            op_ids.append(op_id)

        return all_uses, None, child_ops  # Multiple operations, no single ID
    
    def _evaluate_boolop(self, node: ast.BoolOp) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate a boolean operation (and/or)."""
        all_uses = []
        child_ops = []

        for value in node.values:
            value_uses, value_op_id, value_child_ops = self.evaluate(value)
            all_uses.extend(value_uses)
            if value_op_id:
                child_ops.append(value_op_id)
            child_ops.extend(value_child_ops)

        op_type = type(node.op).__name__
        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else str(op_type)
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation=op_type,
            input_use_ids=all_uses,
            input_operation_ids=child_ops,
            output_definition_ids=[],
            metadata={'op_type': op_type},
        ))

        return all_uses, op_id, child_ops
    
    def _evaluate_call(self, node: ast.Call) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate a function call."""
        # Evaluate function and arguments
        func_uses, func_op_id, func_child_ops = self.evaluate(node.func)
        all_uses = func_uses[:]
        child_ops = [func_op_id] if func_op_id else []
        child_ops.extend(func_child_ops)

        # Evaluate positional arguments
        for arg in node.args:
            arg_uses, arg_op_id, arg_child_ops = self.evaluate(arg)
            all_uses.extend(arg_uses)
            if arg_op_id:
                child_ops.append(arg_op_id)
            child_ops.extend(arg_child_ops)

        # Evaluate keyword arguments (BUG FIX: was missing)
        for keyword in node.keywords:
            if keyword.value:
                kw_uses, kw_op_id, kw_child_ops = self.evaluate(keyword.value)
                all_uses.extend(kw_uses)
                if kw_op_id:
                    child_ops.append(kw_op_id)
                child_ops.extend(kw_child_ops)

        # Determine if this is a known mutation
        known_mutations = ['append', 'extend', 'insert', 'remove', 'pop', 'clear', 'sort', 'reverse', 'update', 'add', 'discard']
        metadata = {'side_effect': 'unknown', 'confidence': 'low'}

        if isinstance(node.func, ast.Attribute):
            if node.func.attr in known_mutations:
                metadata = {
                    'side_effect': 'known_mutation',
                    'mutation_kind': node.func.attr,
                    'receiver': ast.unparse(node.func.value) if hasattr(ast, 'unparse') else str(node.func.value)
                }

        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else "call"
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation="Call",
            input_use_ids=all_uses,
            input_operation_ids=child_ops,
            output_definition_ids=[],
            metadata=metadata
        ))

        return all_uses, op_id, child_ops
    
    def _evaluate_attribute(self, node: ast.Attribute) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate attribute access."""
        value_uses, value_op_id, value_child_ops = self.evaluate(node.value)
        child_ops = [value_op_id] if value_op_id else []
        child_ops.extend(value_child_ops)

        # Track attribute read as a use if the receiver is a local variable
        if isinstance(node.value, ast.Name) and self.ctx.is_local_var(node.value.id):
            attr_name = ast.unparse(node) if hasattr(ast, 'unparse') else f"{node.value.id}.{node.attr}"
            use_id = self.ctx.generate_use_id(attr_name)
            binding_key = f"{self.ctx.function_id}::attribute::{attr_name}"
            cfg_node_ids = self.ctx.get_cfg_node_ids(node)

            self.ctx.facts.uses.append(VariableUse(
                id=use_id,
                variable=attr_name,
                function_id=self.ctx.function_id,
                file=self.ctx.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=ast.unparse(node) if hasattr(ast, 'unparse') else attr_name,
                metadata={
                    'is_attribute_read': True,
                    'receiver': node.value.id,
                    'attribute': node.attr
                }
            ))
            value_uses.append(use_id)

        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else f"{ast.unparse(node.value)}.{node.attr}"
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation='Attribute',
            input_use_ids=value_uses,
            input_operation_ids=child_ops,
            output_definition_ids=[],
            metadata={
                'attribute': node.attr,
                'receiver': ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value)
            },
        ))

        return value_uses, op_id, child_ops
    
    def _evaluate_subscript(self, node: ast.Subscript) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate subscript access."""
        value_uses, value_op_id, value_child_ops = self.evaluate(node.value)
        slice_uses, slice_op_id, slice_child_ops = self.evaluate(node.slice)
        all_uses = value_uses + slice_uses
        child_ops = [op_id for op_id in [value_op_id, slice_op_id] if op_id]
        child_ops.extend(value_child_ops + slice_child_ops)

        # Track subscript read as a use if the collection is a local variable
        if isinstance(node.value, ast.Name) and self.ctx.is_local_var(node.value.id):
            subscript_name = ast.unparse(node) if hasattr(ast, 'unparse') else f"{node.value.id}[{ast.unparse(node.slice) if hasattr(ast, 'unparse') else 'index'}]"
            use_id = self.ctx.generate_use_id(subscript_name)
            binding_key = f"{self.ctx.function_id}::subscript::{subscript_name}"
            cfg_node_ids = self.ctx.get_cfg_node_ids(node)

            self.ctx.facts.uses.append(VariableUse(
                id=use_id,
                variable=subscript_name,
                function_id=self.ctx.function_id,
                file=self.ctx.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=ast.unparse(node) if hasattr(ast, 'unparse') else subscript_name,
                metadata={
                    'is_subscript_read': True,
                    'collection': node.value.id,
                    'key': ast.unparse(node.slice) if hasattr(ast, 'unparse') else str(node.slice)
                }
            ))
            all_uses.append(use_id)

        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else "subscript"
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation='Subscript',
            input_use_ids=all_uses,
            input_operation_ids=child_ops,
            output_definition_ids=[],
            metadata={
                'base': ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value)
            },
        ))

        return all_uses, op_id, child_ops
    
    def _evaluate_ifexp(self, node: ast.IfExp) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate conditional expression (a if cond else b)."""
        test_uses, test_op_id, test_child_ops = self.evaluate(node.test)
        body_uses, body_op_id, body_child_ops = self.evaluate(node.body)
        orelse_uses, orelse_op_id, orelse_child_ops = self.evaluate(node.orelse)
        all_uses = test_uses + body_uses + orelse_uses
        child_ops = [op_id for op_id in [test_op_id, body_op_id, orelse_op_id] if op_id]
        child_ops.extend(test_child_ops + body_child_ops + orelse_child_ops)

        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else "ifexp"
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation='IfExp',
            input_use_ids=all_uses,
            input_operation_ids=child_ops,
            output_definition_ids=[],
            metadata={},
        ))

        return all_uses, op_id, child_ops
    
    def _evaluate_lambda(self, node: ast.Lambda) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate lambda expression."""
        # Evaluate body (usually an expression)
        body_uses, body_op_id, body_child_ops = self.evaluate(node.body)
        child_ops = [body_op_id] if body_op_id else []
        child_ops.extend(body_child_ops)

        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else "lambda"
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation='Lambda',
            input_use_ids=body_uses,
            input_operation_ids=child_ops,
            output_definition_ids=[],
            metadata={'param_count': len(node.args.args)},
        ))

        return body_uses, op_id, child_ops

    def _evaluate_list(self, node: ast.List) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate list literal."""
        all_uses = []
        child_ops = []
        for elt in node.elts:
            elt_uses, elt_op_id, elt_child_ops = self.evaluate(elt)
            all_uses.extend(elt_uses)
            if elt_op_id:
                child_ops.append(elt_op_id)
            child_ops.extend(elt_child_ops)
        return all_uses, None, child_ops

    def _evaluate_tuple(self, node: ast.Tuple) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate tuple literal."""
        all_uses = []
        child_ops = []
        for elt in node.elts:
            elt_uses, elt_op_id, elt_child_ops = self.evaluate(elt)
            all_uses.extend(elt_uses)
            if elt_op_id:
                child_ops.append(elt_op_id)
            child_ops.extend(elt_child_ops)
        return all_uses, None, child_ops

    def _evaluate_dict(self, node: ast.Dict) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate dict literal."""
        all_uses = []
        child_ops = []
        for key in node.keys:
            if key:
                key_uses, key_op_id, key_child_ops = self.evaluate(key)
                all_uses.extend(key_uses)
                if key_op_id:
                    child_ops.append(key_op_id)
                child_ops.extend(key_child_ops)
        for value in node.values:
            value_uses, value_op_id, value_child_ops = self.evaluate(value)
            all_uses.extend(value_uses)
            if value_op_id:
                child_ops.append(value_op_id)
            child_ops.extend(value_child_ops)
        return all_uses, None, child_ops

    def _evaluate_set(self, node: ast.Set) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate set literal."""
        all_uses = []
        child_ops = []
        for elt in node.elts:
            elt_uses, elt_op_id, elt_child_ops = self.evaluate(elt)
            all_uses.extend(elt_uses)
            if elt_op_id:
                child_ops.append(elt_op_id)
            child_ops.extend(elt_child_ops)
        return all_uses, None, child_ops

    def _evaluate_listcomp(self, node: ast.ListComp) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate list comprehension."""
        # Evaluate generators first (correct evaluation order)
        all_uses = []
        child_ops = []

        for generator in node.generators:
            iter_uses, iter_op_id, iter_child_ops = self.evaluate(generator.iter)
            all_uses.extend(iter_uses)
            if iter_op_id:
                child_ops.append(iter_op_id)
            child_ops.extend(iter_child_ops)

            for if_test in generator.ifs:
                if_uses, if_op_id, if_child_ops = self.evaluate(if_test)
                all_uses.extend(if_uses)
                if if_op_id:
                    child_ops.append(if_op_id)
                child_ops.extend(if_child_ops)

        # Then evaluate the element expression
        elt_uses, elt_op_id, elt_child_ops = self.evaluate(node.elt)
        all_uses.extend(elt_uses)
        if elt_op_id:
            child_ops.append(elt_op_id)
        child_ops.extend(elt_child_ops)

        return all_uses, None, child_ops

    def _evaluate_setcomp(self, node: ast.SetComp) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate set comprehension."""
        # Evaluate generators first
        all_uses = []
        child_ops = []

        for generator in node.generators:
            iter_uses, iter_op_id, iter_child_ops = self.evaluate(generator.iter)
            all_uses.extend(iter_uses)
            if iter_op_id:
                child_ops.append(iter_op_id)
            child_ops.extend(iter_child_ops)

            for if_test in generator.ifs:
                if_uses, if_op_id, if_child_ops = self.evaluate(if_test)
                all_uses.extend(if_uses)
                if if_op_id:
                    child_ops.append(if_op_id)
                child_ops.extend(if_child_ops)

        # Then evaluate the element expression
        elt_uses, elt_op_id, elt_child_ops = self.evaluate(node.elt)
        all_uses.extend(elt_uses)
        if elt_op_id:
            child_ops.append(elt_op_id)
        child_ops.extend(elt_child_ops)

        return all_uses, None, child_ops

    def _evaluate_dictcomp(self, node: ast.DictComp) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate dict comprehension."""
        # Evaluate generators first
        all_uses = []
        child_ops = []

        for generator in node.generators:
            iter_uses, iter_op_id, iter_child_ops = self.evaluate(generator.iter)
            all_uses.extend(iter_uses)
            if iter_op_id:
                child_ops.append(iter_op_id)
            child_ops.extend(iter_child_ops)

            for if_test in generator.ifs:
                if_uses, if_op_id, if_child_ops = self.evaluate(if_test)
                all_uses.extend(if_uses)
                if if_op_id:
                    child_ops.append(if_op_id)
                child_ops.extend(if_child_ops)

        # Then evaluate key and value expressions
        key_uses, key_op_id, key_child_ops = self.evaluate(node.key)
        value_uses, value_op_id, value_child_ops = self.evaluate(node.value)
        all_uses.extend(key_uses + value_uses)
        if key_op_id:
            child_ops.append(key_op_id)
        if value_op_id:
            child_ops.append(value_op_id)
        child_ops.extend(key_child_ops + value_child_ops)

        return all_uses, None, child_ops

    def _evaluate_generatorexp(self, node: ast.GeneratorExp) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate generator expression."""
        # Evaluate generators first
        all_uses = []
        child_ops = []

        for generator in node.generators:
            iter_uses, iter_op_id, iter_child_ops = self.evaluate(generator.iter)
            all_uses.extend(iter_uses)
            if iter_op_id:
                child_ops.append(iter_op_id)
            child_ops.extend(iter_child_ops)

            for if_test in generator.ifs:
                if_uses, if_op_id, if_child_ops = self.evaluate(if_test)
                all_uses.extend(if_uses)
                if if_op_id:
                    child_ops.append(if_op_id)
                child_ops.extend(if_child_ops)

        # Then evaluate the element expression
        elt_uses, elt_op_id, elt_child_ops = self.evaluate(node.elt)
        all_uses.extend(elt_uses)
        if elt_op_id:
            child_ops.append(elt_op_id)
        child_ops.extend(elt_child_ops)

        return all_uses, None, child_ops

    def _evaluate_yield(self, node: ast.Yield) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate yield expression."""
        if node.value:
            value_uses, value_op_id, value_child_ops = self.evaluate(node.value)
            child_ops = [value_op_id] if value_op_id else []
            child_ops.extend(value_child_ops)
            return value_uses, None, child_ops
        return [], None, []

    def _evaluate_yieldfrom(self, node: ast.YieldFrom) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate yield from expression."""
        value_uses, value_op_id, value_child_ops = self.evaluate(node.value)
        child_ops = [value_op_id] if value_op_id else []
        child_ops.extend(value_child_ops)
        return value_uses, None, child_ops

    def _evaluate_await(self, node: ast.Await) -> Tuple[List[str], Optional[str], List[str]]:
        """Evaluate await expression."""
        value_uses, value_op_id, value_child_ops = self.evaluate(node.value)
        child_ops = [value_op_id] if value_op_id else []
        child_ops.extend(value_child_ops)
        return value_uses, None, child_ops

    def _evaluate_generic(self, node: ast.AST) -> Tuple[List[str], Optional[str], List[str]]:
        """Generic fallback for unhandled node types."""
        # Try to visit child nodes recursively
        all_uses = []
        child_ops = []
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                child_uses, child_op_id, child_child_ops = self.evaluate(value)
                all_uses.extend(child_uses)
                if child_op_id:
                    child_ops.append(child_op_id)
                child_ops.extend(child_child_ops)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        child_uses, child_op_id, child_child_ops = self.evaluate(item)
                        all_uses.extend(child_uses)
                        if child_op_id:
                            child_ops.append(child_op_id)
                        child_ops.extend(child_child_ops)
        return all_uses, None, child_ops
