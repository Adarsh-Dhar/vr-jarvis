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
    
    def evaluate(self, node: ast.AST) -> Tuple[List[str], Optional[str]]:
        """
        Evaluate an expression recursively.
        
        Returns:
            Tuple of (use_ids created, operation_id created or None)
        """
        node_id = id(node)
        if node_id in self.ctx._evaluated_nodes:
            return [], None
        
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
    
    def _evaluate_name(self, node: ast.Name) -> Tuple[List[str], Optional[str]]:
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
            return [use_id], None
        return [], None
    
    def _evaluate_constant(self, node: ast.Constant) -> Tuple[List[str], Optional[str]]:
        """Evaluate a constant literal."""
        # Constants don't create uses or operations
        return [], None
    
    def _evaluate_binop(self, node: ast.BinOp) -> Tuple[List[str], Optional[str]]:
        """Evaluate a binary operation."""
        # Recursively evaluate left and right
        left_uses, _ = self.evaluate(node.left)
        right_uses, _ = self.evaluate(node.right)
        
        all_uses = left_uses + right_uses
        
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
            output_definition_ids=[],
            metadata={'op_type': op_type},
        ))
        
        return all_uses, op_id
    
    def _evaluate_unaryop(self, node: ast.UnaryOp) -> Tuple[List[str], Optional[str]]:
        """Evaluate a unary operation."""
        operand_uses, _ = self.evaluate(node.operand)
        
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
            output_definition_ids=[],
            metadata={'op_type': op_type},
        ))
        
        return operand_uses, op_id
    
    def _evaluate_compare(self, node: ast.Compare) -> Tuple[List[str], Optional[str]]:
        """Evaluate a comparison operation."""
        # Evaluate left and comparators
        left_uses, _ = self.evaluate(node.left)
        all_uses = left_uses[:]
        
        for comparator in node.comparators:
            comp_uses, _ = self.evaluate(comparator)
            all_uses.extend(comp_uses)
        
        # Create operation for each comparison
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
                output_definition_ids=[],
                metadata={'op_type': op_type, 'comparison_index': i},
            ))
        
        return all_uses, None  # Multiple operations, no single ID
    
    def _evaluate_boolop(self, node: ast.BoolOp) -> Tuple[List[str], Optional[str]]:
        """Evaluate a boolean operation (and/or)."""
        all_uses = []
        
        for value in node.values:
            value_uses, _ = self.evaluate(value)
            all_uses.extend(value_uses)
        
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
            output_definition_ids=[],
            metadata={'op_type': op_type},
        ))
        
        return all_uses, op_id
    
    def _evaluate_call(self, node: ast.Call) -> Tuple[List[str], Optional[str]]:
        """Evaluate a function call."""
        # Evaluate function and arguments
        func_uses, _ = self.evaluate(node.func)
        all_uses = func_uses[:]
        
        for arg in node.args:
            arg_uses, _ = self.evaluate(arg)
            all_uses.extend(arg_uses)
        
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
            output_definition_ids=[],
            metadata=metadata
        ))
        
        return all_uses, op_id
    
    def _evaluate_attribute(self, node: ast.Attribute) -> Tuple[List[str], Optional[str]]:
        """Evaluate attribute access."""
        value_uses, _ = self.evaluate(node.value)
        
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
            output_definition_ids=[],
            metadata={
                'attribute': node.attr,
                'receiver': ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value)
            },
        ))
        
        return value_uses, op_id
    
    def _evaluate_subscript(self, node: ast.Subscript) -> Tuple[List[str], Optional[str]]:
        """Evaluate subscript access."""
        value_uses, _ = self.evaluate(node.value)
        slice_uses, _ = self.evaluate(node.slice)
        all_uses = value_uses + slice_uses
        
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
            output_definition_ids=[],
            metadata={
                'base': ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value)
            },
        ))
        
        return all_uses, op_id
    
    def _evaluate_ifexp(self, node: ast.IfExp) -> Tuple[List[str], Optional[str]]:
        """Evaluate conditional expression (a if cond else b)."""
        test_uses, _ = self.evaluate(node.test)
        body_uses, _ = self.evaluate(node.body)
        orelse_uses, _ = self.evaluate(node.orelse)
        all_uses = test_uses + body_uses + orelse_uses
        
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
            output_definition_ids=[],
            metadata={},
        ))
        
        return all_uses, op_id
    
    def _evaluate_lambda(self, node: ast.Lambda) -> Tuple[List[str], Optional[str]]:
        """Evaluate lambda expression."""
        # Evaluate body (usually an expression)
        body_uses, _ = self.evaluate(node.body)
        
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
            output_definition_ids=[],
            metadata={'param_count': len(node.args.args)},
        ))
        
        return body_uses, op_id
    
    def _evaluate_list(self, node: ast.List) -> Tuple[List[str], Optional[str]]:
        """Evaluate list literal."""
        all_uses = []
        for elt in node.elts:
            elt_uses, _ = self.evaluate(elt)
            all_uses.extend(elt_uses)
        return all_uses, None
    
    def _evaluate_tuple(self, node: ast.Tuple) -> Tuple[List[str], Optional[str]]:
        """Evaluate tuple literal."""
        all_uses = []
        for elt in node.elts:
            elt_uses, _ = self.evaluate(elt)
            all_uses.extend(elt_uses)
        return all_uses, None
    
    def _evaluate_dict(self, node: ast.Dict) -> Tuple[List[str], Optional[str]]:
        """Evaluate dict literal."""
        all_uses = []
        for key in node.keys:
            if key:
                key_uses, _ = self.evaluate(key)
                all_uses.extend(key_uses)
        for value in node.values:
            value_uses, _ = self.evaluate(value)
            all_uses.extend(value_uses)
        return all_uses, None
    
    def _evaluate_set(self, node: ast.Set) -> Tuple[List[str], Optional[str]]:
        """Evaluate set literal."""
        all_uses = []
        for elt in node.elts:
            elt_uses, _ = self.evaluate(elt)
            all_uses.extend(elt_uses)
        return all_uses, None
    
    def _evaluate_listcomp(self, node: ast.ListComp) -> Tuple[List[str], Optional[str]]:
        """Evaluate list comprehension."""
        # Visit elements and generators
        elt_uses, _ = self.evaluate(node.elt)
        all_uses = elt_uses[:]
        
        for generator in node.generators:
            iter_uses, _ = self.evaluate(generator.iter)
            all_uses.extend(iter_uses)
            for if_test in generator.ifs:
                if_uses, _ = self.evaluate(if_test)
                all_uses.extend(if_uses)
        
        return all_uses, None
    
    def _evaluate_setcomp(self, node: ast.SetComp) -> Tuple[List[str], Optional[str]]:
        """Evaluate set comprehension."""
        elt_uses, _ = self.evaluate(node.elt)
        all_uses = elt_uses[:]
        
        for generator in node.generators:
            iter_uses, _ = self.evaluate(generator.iter)
            all_uses.extend(iter_uses)
            for if_test in generator.ifs:
                if_uses, _ = self.evaluate(if_test)
                all_uses.extend(if_uses)
        
        return all_uses, None
    
    def _evaluate_dictcomp(self, node: ast.DictComp) -> Tuple[List[str], Optional[str]]:
        """Evaluate dict comprehension."""
        key_uses, _ = self.evaluate(node.key)
        value_uses, _ = self.evaluate(node.value)
        all_uses = key_uses + value_uses
        
        for generator in node.generators:
            iter_uses, _ = self.evaluate(generator.iter)
            all_uses.extend(iter_uses)
            for if_test in generator.ifs:
                if_uses, _ = self.evaluate(if_test)
                all_uses.extend(if_uses)
        
        return all_uses, None
    
    def _evaluate_generatorexp(self, node: ast.GeneratorExp) -> Tuple[List[str], Optional[str]]:
        """Evaluate generator expression."""
        elt_uses, _ = self.evaluate(node.elt)
        all_uses = elt_uses[:]
        
        for generator in node.generators:
            iter_uses, _ = self.evaluate(generator.iter)
            all_uses.extend(iter_uses)
            for if_test in generator.ifs:
                if_uses, _ = self.evaluate(if_test)
                all_uses.extend(if_uses)
        
        return all_uses, None
    
    def _evaluate_yield(self, node: ast.Yield) -> Tuple[List[str], Optional[str]]:
        """Evaluate yield expression."""
        if node.value:
            value_uses, _ = self.evaluate(node.value)
            return value_uses, None
        return [], None
    
    def _evaluate_yieldfrom(self, node: ast.YieldFrom) -> Tuple[List[str], Optional[str]]:
        """Evaluate yield from expression."""
        value_uses, _ = self.evaluate(node.value)
        return value_uses, None
    
    def _evaluate_await(self, node: ast.Await) -> Tuple[List[str], Optional[str]]:
        """Evaluate await expression."""
        value_uses, _ = self.evaluate(node.value)
        return value_uses, None
    
    def _evaluate_generic(self, node: ast.AST) -> Tuple[List[str], Optional[str]]:
        """Generic fallback for unhandled node types."""
        # Try to visit child nodes recursively
        all_uses = []
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                child_uses, _ = self.evaluate(value)
                all_uses.extend(child_uses)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        child_uses, _ = self.evaluate(item)
                        all_uses.extend(child_uses)
        return all_uses, None
