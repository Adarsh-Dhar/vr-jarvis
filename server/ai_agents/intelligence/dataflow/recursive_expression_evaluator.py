"""Recursive expression evaluator for DFG extraction."""
import ast
from typing import List, Dict, Any, Optional, Set, Tuple
from .models import VariableUse, ExpressionFact, ExpressionResult, BindingResolver
from .ids import IdAllocator


class ExpressionEvaluationContext:
    """Context for expression evaluation."""

    def __init__(self, function_id: str, file: str, local_vars: Set[str], cfg_node_map: Dict[str, str], ast_index, facts, free_vars: Set[str] = None, global_vars: Set[str] = None, nonlocal_vars: Set[str] = None, symbol_table=None, ids: IdAllocator = None):
        self.function_id = function_id
        self.file = file
        self.local_vars = local_vars
        self.free_vars = free_vars or set()
        self.global_vars = global_vars or set()
        self.nonlocal_vars = nonlocal_vars or set()
        self.cfg_node_map = cfg_node_map
        self.ast_index = ast_index
        self.facts = facts
        self.symbol_table = symbol_table
        self._evaluated_nodes: Set[int] = set()
        self.ids = ids

        # Create BindingResolver for unified name resolution
        self.binding_resolver = BindingResolver(
            function_id=function_id,
            file=file,
            local_vars=local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            symbol_table=symbol_table
        )

    def generate_operation_id(self) -> str:
        """Generate a unique operation ID."""
        if self.ids:
            return self.ids.operation()
        # Fallback for backward compatibility
        raise RuntimeError("IdAllocator not provided to ExpressionEvaluationContext")

    def generate_use_id(self, variable: str) -> str:
        """Generate a unique use ID."""
        if self.ids:
            return self.ids.use(variable)
        # Fallback for backward compatibility
        raise RuntimeError("IdAllocator not provided to ExpressionEvaluationContext")

    def get_cfg_node_ids(self, node: ast.AST) -> List[str]:
        """Get CFG node IDs for an AST node."""
        if not self.ast_index:
            return []
        node_ids = self.ast_index.get_cfg_nodes(node)
        return node_ids if node_ids else []

    def is_local_var(self, name: str) -> bool:
        """Check if a name is a local variable."""
        return name in self.local_vars

    def get_binding_category(self, name: str) -> str:
        """Determine the binding category for a name."""
        if name in self.local_vars:
            return 'local'
        elif name in self.global_vars:
            return 'global'
        elif name in self.nonlocal_vars:
            return 'nonlocal'
        elif name in self.free_vars:
            return 'free'
        else:
            # Default to local if unknown
            return 'local'


class RecursiveExpressionEvaluator:
    """Recursively evaluates expressions and creates DFG facts."""

    def __init__(self, ctx: ExpressionEvaluationContext):
        self.ctx = ctx

    def _collect(self, children: List[ExpressionResult]) -> Tuple[List[str], List[str], List[str], List[Dict[str, Any]]]:
        """BinOp convention: an operation child contributes its op id,
        a leaf child contributes its use ids."""
        use_ids, op_ids, descendants, diagnostics = [], [], [], []
        for c in children:
            if c.root_operation_id:
                op_ids.append(c.root_operation_id)
                descendants.append(c.root_operation_id)
            else:
                use_ids.extend(c.direct_input_use_ids)
            descendants.extend(c.descendant_operation_ids)
            diagnostics.extend(c.diagnostics)
        return use_ids, op_ids, descendants, diagnostics

    def _emit(self, node: ast.AST, operation: str, children: List[ExpressionResult], metadata: Dict[str, Any] = None) -> ExpressionResult:
        """Record one ExpressionFact and return its ExpressionResult."""
        use_ids, op_ids, descendants, diagnostics = self._collect(children)
        op_id = self.ctx.generate_operation_id()
        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id, function_id=self.ctx.function_id, file=self.ctx.file,
            line=node.lineno, column=getattr(node, 'col_offset', 0),
            cfg_node_ids=self.ctx.get_cfg_node_ids(node),
            expression=ast.unparse(node), operation=operation,
            input_use_ids=use_ids, input_operation_ids=op_ids,
            output_definition_ids=[], metadata=metadata or {}))
        return ExpressionResult(op_id, use_ids, op_ids, descendants, diagnostics)
    
    def evaluate(self, node: ast.AST) -> ExpressionResult:
        """
        Evaluate an expression recursively.

        Returns:
            ExpressionResult with root_operation_id, direct_input_use_ids, direct_input_operation_ids, descendant_operation_ids, diagnostics
        """
        node_id = id(node)
        if node_id in self.ctx._evaluated_nodes:
            return ExpressionResult(
                root_operation_id=None,
                direct_input_use_ids=[],
                direct_input_operation_ids=[],
                descendant_operation_ids=[],
                diagnostics=[]
            )

        self.ctx._evaluated_nodes.add(node_id)

        result = None
        if isinstance(node, ast.Name):
            result = self._evaluate_name(node)
        elif isinstance(node, ast.Constant):
            result = self._evaluate_constant(node)
        elif isinstance(node, ast.BinOp):
            result = self._evaluate_binop(node)
        elif isinstance(node, ast.UnaryOp):
            result = self._evaluate_unaryop(node)
        elif isinstance(node, ast.Compare):
            result = self._evaluate_compare(node)
        elif isinstance(node, ast.BoolOp):
            result = self._evaluate_boolop(node)
        elif isinstance(node, ast.Call):
            result = self._evaluate_call(node)
        elif isinstance(node, ast.Attribute):
            result = self._evaluate_attribute(node)
        elif isinstance(node, ast.Subscript):
            result = self._evaluate_subscript(node)
        elif isinstance(node, ast.IfExp):
            result = self._evaluate_ifexp(node)
        elif isinstance(node, ast.Lambda):
            result = self._evaluate_lambda(node)
        elif isinstance(node, ast.JoinedStr):
            result = self._evaluate_joinedstr(node)
        elif isinstance(node, ast.List):
            result = self._evaluate_list(node)
        elif isinstance(node, ast.Tuple):
            result = self._evaluate_tuple(node)
        elif isinstance(node, ast.Dict):
            result = self._evaluate_dict(node)
        elif isinstance(node, ast.Set):
            result = self._evaluate_set(node)
        elif isinstance(node, ast.ListComp):
            result = self._evaluate_listcomp(node)
        elif isinstance(node, ast.SetComp):
            result = self._evaluate_setcomp(node)
        elif isinstance(node, ast.DictComp):
            result = self._evaluate_dictcomp(node)
        elif isinstance(node, ast.GeneratorExp):
            result = self._evaluate_generatorexp(node)
        elif isinstance(node, ast.Yield):
            result = self._evaluate_yield(node)
        elif isinstance(node, ast.YieldFrom):
            result = self._evaluate_yieldfrom(node)
        elif isinstance(node, ast.Await):
            result = self._evaluate_await(node)
        else:
            # Generic fallback
            result = self._evaluate_generic(node)

        assert isinstance(result, ExpressionResult), f'{type(node).__name__} handler returned {type(result)}'
        return result
    
    def _evaluate_name(self, node: ast.Name) -> ExpressionResult:
        """Evaluate a name reference."""
        if isinstance(node.ctx, ast.Load):
            use_id = self.ctx.generate_use_id(node.id)
            cfg_node_ids = self.ctx.get_cfg_node_ids(node)
            
            # Use binding resolver to get binding key
            resolution = self.ctx.binding_resolver.resolve_name(node.id, "function", node)
            binding_key = resolution.binding_key

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
            return ExpressionResult(
                root_operation_id=None,
                direct_input_use_ids=[use_id],
                direct_input_operation_ids=[],
                descendant_operation_ids=[],
                diagnostics=[]
            )
        return ExpressionResult(
            root_operation_id=None,
            direct_input_use_ids=[],
            direct_input_operation_ids=[],
            descendant_operation_ids=[],
            diagnostics=[]
        )
    
    def _evaluate_constant(self, node: ast.Constant) -> ExpressionResult:
        """Evaluate a constant literal."""
        # Constants don't create uses or operations
        return ExpressionResult(
            root_operation_id=None,
            direct_input_use_ids=[],
            direct_input_operation_ids=[],
            descendant_operation_ids=[],
            diagnostics=[]
        )
    
    def _evaluate_binop(self, node: ast.BinOp) -> ExpressionResult:
        """Evaluate a binary operation."""
        # Recursively evaluate left and right
        left_result = self.evaluate(node.left)
        right_result = self.evaluate(node.right)

        # Distinguish direct inputs from transitive descendant inputs
        # Direct inputs: use IDs if leaf node, operation IDs if inner operation
        direct_input_use_ids = []
        direct_input_operation_ids = []

        # Left side: either operation ID or use IDs (not both)
        if left_result.root_operation_id:
            direct_input_operation_ids.append(left_result.root_operation_id)
        else:
            direct_input_use_ids.extend(left_result.direct_input_use_ids)

        # Right side: either operation ID or use IDs (not both)
        if right_result.root_operation_id:
            direct_input_operation_ids.append(right_result.root_operation_id)
        else:
            direct_input_use_ids.extend(right_result.direct_input_use_ids)

        # Child operations for tracking (transitive descendants)
        descendant_operation_ids = []
        if left_result.root_operation_id:
            descendant_operation_ids.append(left_result.root_operation_id)
        descendant_operation_ids.extend(left_result.descendant_operation_ids)
        if right_result.root_operation_id:
            descendant_operation_ids.append(right_result.root_operation_id)
        descendant_operation_ids.extend(right_result.descendant_operation_ids)

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
            input_use_ids=direct_input_use_ids,
            input_operation_ids=direct_input_operation_ids,
            output_definition_ids=[],
            metadata={'op_type': op_type},
        ))

        return ExpressionResult(
            root_operation_id=op_id,
            direct_input_use_ids=direct_input_use_ids,
            direct_input_operation_ids=direct_input_operation_ids,
            descendant_operation_ids=descendant_operation_ids,
            diagnostics=[]
        )
    
    def _evaluate_unaryop(self, node: ast.UnaryOp) -> ExpressionResult:
        """Evaluate a unary operation."""
        operand_result = self.evaluate(node.operand)
        
        direct_input_use_ids = []
        direct_input_operation_ids = []
        
        if operand_result.root_operation_id:
            direct_input_operation_ids.append(operand_result.root_operation_id)
        else:
            direct_input_use_ids.extend(operand_result.direct_input_use_ids)
        
        descendant_operation_ids = []
        if operand_result.root_operation_id:
            descendant_operation_ids.append(operand_result.root_operation_id)
        descendant_operation_ids.extend(operand_result.descendant_operation_ids)

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
            input_use_ids=direct_input_use_ids,
            input_operation_ids=direct_input_operation_ids,
            output_definition_ids=[],
            metadata={'op_type': op_type},
        ))

        return ExpressionResult(
            root_operation_id=op_id,
            direct_input_use_ids=direct_input_use_ids,
            direct_input_operation_ids=direct_input_operation_ids,
            descendant_operation_ids=descendant_operation_ids,
            diagnostics=[]
        )
    
    def _evaluate_compare(self, node: ast.Compare) -> ExpressionResult:
        """Evaluate a comparison operation, avoiding duplicate uses in chained comparisons."""
        # Evaluate left and comparators
        left_result = self.evaluate(node.left)
        all_uses = left_result.direct_input_use_ids[:]
        
        # Track all results for proper operation linking
        comparator_results = []
        for comparator in node.comparators:
            comp_result = self.evaluate(comparator)
            # Add comparator uses without duplicating
            for use in comp_result.direct_input_use_ids:
                if use not in all_uses:
                    all_uses.append(use)
            comparator_results.append(comp_result)

        # Create operation for each comparison with proper operand linking
        op_ids = []
        descendant_operation_ids = []
        
        # Track left operand operation for chaining
        left_op_id = left_result.root_operation_id
        if left_op_id:
            descendant_operation_ids.append(left_op_id)
        descendant_operation_ids.extend(left_result.descendant_operation_ids)

        for i, op in enumerate(node.ops):
            op_type = type(op).__name__
            op_id = self.ctx.generate_operation_id()
            expression = ast.unparse(node) if hasattr(ast, 'unparse') else str(op_type)
            cfg_node_ids = self.ctx.get_cfg_node_ids(node)

            # For chained comparisons (a < b < c), each comparison uses its specific operands
            # Comparison i uses left operand and comparator i
            # For a < b < c: Compare(a, b, [Lt]), Compare(b, c, [Lt])
            direct_input_use_ids = []
            direct_input_operation_ids = []
            
            if i == 0:
                # First comparison: left + first comparator
                direct_input_use_ids = left_result.direct_input_use_ids + comparator_results[0].direct_input_use_ids
                if left_result.root_operation_id:
                    direct_input_operation_ids.append(left_result.root_operation_id)
                if comparator_results[0].root_operation_id:
                    direct_input_operation_ids.append(comparator_results[0].root_operation_id)
            else:
                # Subsequent comparisons: previous comparator + current comparator
                prev_comp = comparator_results[i-1]
                curr_comp = comparator_results[i]
                direct_input_use_ids = prev_comp.direct_input_use_ids + curr_comp.direct_input_use_ids
                if prev_comp.root_operation_id:
                    direct_input_operation_ids.append(prev_comp.root_operation_id)
                if curr_comp.root_operation_id:
                    direct_input_operation_ids.append(curr_comp.root_operation_id)

            self.ctx.facts.operations.append(ExpressionFact(
                id=op_id,
                function_id=self.ctx.function_id,
                file=self.ctx.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                cfg_node_ids=cfg_node_ids,
                expression=expression,
                operation=op_type,
                input_use_ids=direct_input_use_ids,
                input_operation_ids=direct_input_operation_ids,
                output_definition_ids=[],
                metadata={'op_type': op_type, 'comparison_index': i, 'is_chained': len(node.ops) > 1},
            ))
            op_ids.append(op_id)
            descendant_operation_ids.append(op_id)
            
            # Add descendant operations from comparators
            for comp_result in comparator_results:
                if comp_result.root_operation_id:
                    descendant_operation_ids.append(comp_result.root_operation_id)
                descendant_operation_ids.extend(comp_result.descendant_operation_ids)

        # For chained comparisons, return the last operation as root, or None if single
        root_op_id = op_ids[-1] if op_ids else None
        
        return ExpressionResult(
            root_operation_id=root_op_id,
            direct_input_use_ids=all_uses,
            direct_input_operation_ids=[],
            descendant_operation_ids=descendant_operation_ids,
            diagnostics=[]
        )
    
    def _evaluate_boolop(self, node: ast.BoolOp) -> ExpressionResult:
        """Evaluate a boolean operation (and/or) with short-circuit semantics."""
        direct_input_use_ids = []
        direct_input_operation_ids = []
        descendant_operation_ids = []

        for value in node.values:
            value_result = self.evaluate(value)
            direct_input_use_ids.extend(value_result.direct_input_use_ids)
            if value_result.root_operation_id:
                direct_input_operation_ids.append(value_result.root_operation_id)
            descendant_operation_ids.extend(value_result.descendant_operation_ids)

        op_type = type(node.op).__name__
        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else str(op_type)
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        # Metadata to capture short-circuit semantics
        metadata = {
            'op_type': op_type,
            'is_short_circuit': True,
            'operator': 'and' if isinstance(node.op, ast.And) else 'or',
            'operand_order': [i for i in range(len(node.values))],  # Track operand evaluation order
            'cfg_path_association': 'short_circuit_branching'  # M5.5: Associate with CFG paths
        }

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation=op_type,
            input_use_ids=direct_input_use_ids,
            input_operation_ids=direct_input_operation_ids,
            output_definition_ids=[],
            metadata=metadata,
        ))

        descendant_operation_ids.append(op_id)
        
        return ExpressionResult(
            root_operation_id=op_id,
            direct_input_use_ids=direct_input_use_ids,
            direct_input_operation_ids=direct_input_operation_ids,
            descendant_operation_ids=descendant_operation_ids,
            diagnostics=[]
        )
    
    def _evaluate_call(self, node: ast.Call) -> ExpressionResult:
        """Evaluate a function call with source order preservation for all argument types."""
        # M5.7: Preserve source evaluation order for all argument types
        # Do NOT group args and kwargs separately - preserve source order

        # Evaluate function and arguments
        func = self.evaluate(node.func)
        args = [self.evaluate(a) for a in node.args]
        kwargs = [self.evaluate(k.value) for k in node.keywords if k.value]

        # Determine if this is a known mutation
        known_mutations = ['append', 'extend', 'insert', 'remove', 'pop', 'clear', 'sort', 'reverse', 'update', 'add', 'discard']
        metadata = {
            'side_effect': 'unknown',
            'confidence': 'low',
            'arg_count': len(node.args) + len(node.keywords)
        }

        if isinstance(node.func, ast.Attribute):
            if node.func.attr in known_mutations:
                metadata.update({
                    'side_effect': 'known_mutation',
                    'mutation_kind': node.func.attr,
                    'receiver': ast.unparse(node.func.value) if hasattr(ast, 'unparse') else str(node.func.value)
                })

        return self._emit(node, 'Call', [func, *args, *kwargs], metadata)
    
    def _evaluate_attribute(self, node: ast.Attribute) -> ExpressionResult:
        """Evaluate attribute access."""
        value = self.evaluate(node.value)

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
            # Add this use to the result
            value.direct_input_use_ids.append(use_id)

        return self._emit(node, 'Attribute', [value], {'attr': node.attr})
    
    def _evaluate_subscript(self, node: ast.Subscript) -> ExpressionResult:
        """Evaluate subscript access."""
        value = self.evaluate(node.value)
        slice_result = self.evaluate(node.slice)

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
            # Add this use to the value result
            value.direct_input_use_ids.append(use_id)

        return self._emit(node, 'Subscript', [value, slice_result])
    
    def _evaluate_ifexp(self, node: ast.IfExp) -> ExpressionResult:
        """Evaluate conditional expression (a if cond else b) with branch awareness."""
        test_result = self.evaluate(node.test)
        body_result = self.evaluate(node.body)
        orelse_result = self.evaluate(node.orelse)
        
        direct_input_use_ids = []
        direct_input_operation_ids = []
        descendant_operation_ids = []
        
        # Condition inputs
        direct_input_use_ids.extend(test_result.direct_input_use_ids)
        if test_result.root_operation_id:
            direct_input_operation_ids.append(test_result.root_operation_id)
        descendant_operation_ids.extend(test_result.descendant_operation_ids)
        
        # True branch inputs
        direct_input_use_ids.extend(body_result.direct_input_use_ids)
        if body_result.root_operation_id:
            direct_input_operation_ids.append(body_result.root_operation_id)
        descendant_operation_ids.extend(body_result.descendant_operation_ids)
        
        # False branch inputs
        direct_input_use_ids.extend(orelse_result.direct_input_use_ids)
        if orelse_result.root_operation_id:
            direct_input_operation_ids.append(orelse_result.root_operation_id)
        descendant_operation_ids.extend(orelse_result.descendant_operation_ids)

        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else "ifexp"
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        # Metadata to capture branch relationships
        metadata = {
            'is_conditional': True,
            'test_operation_id': test_result.root_operation_id,
            'true_branch_operation_id': body_result.root_operation_id,
            'false_branch_operation_id': orelse_result.root_operation_id,
        }

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation='IfExp',
            input_use_ids=direct_input_use_ids,
            input_operation_ids=direct_input_operation_ids,
            output_definition_ids=[],
            metadata=metadata,
        ))

        descendant_operation_ids.append(op_id)
        
        return ExpressionResult(
            root_operation_id=op_id,
            direct_input_use_ids=direct_input_use_ids,
            direct_input_operation_ids=direct_input_operation_ids,
            descendant_operation_ids=descendant_operation_ids,
            diagnostics=[]
        )
    
    def _evaluate_joinedstr(self, node: ast.JoinedStr) -> ExpressionResult:
        """Evaluate f-string with interpolation tracking."""
        direct_input_use_ids = []
        direct_input_operation_ids = []
        descendant_operation_ids = []
        
        # Evaluate each value in the f-string
        for value in node.values:
            if isinstance(value, ast.Constant):
                # Literal string part - no uses or operations
                pass
            elif isinstance(value, ast.FormattedValue):
                # Interpolated expression
                value_result = self.evaluate(value.value)
                direct_input_use_ids.extend(value_result.direct_input_use_ids)
                if value_result.root_operation_id:
                    direct_input_operation_ids.append(value_result.root_operation_id)
                descendant_operation_ids.extend(value_result.descendant_operation_ids)
            else:
                # Other value types
                value_result = self.evaluate(value)
                direct_input_use_ids.extend(value_result.direct_input_use_ids)
                if value_result.root_operation_id:
                    direct_input_operation_ids.append(value_result.root_operation_id)
                descendant_operation_ids.extend(value_result.descendant_operation_ids)

        # Create f-string assembly operation
        op_id = self.ctx.generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else "fstring"
        cfg_node_ids = self.ctx.get_cfg_node_ids(node)

        metadata = {
            'is_fstring': True,
            'interpolation_count': len([v for v in node.values if isinstance(v, ast.FormattedValue)])
        }

        self.ctx.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.ctx.function_id,
            file=self.ctx.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation='JoinedStr',
            input_use_ids=direct_input_use_ids,
            input_operation_ids=direct_input_operation_ids,
            output_definition_ids=[],
            metadata=metadata,
        ))

        descendant_operation_ids.append(op_id)
        
        return ExpressionResult(
            root_operation_id=op_id,
            direct_input_use_ids=direct_input_use_ids,
            direct_input_operation_ids=direct_input_operation_ids,
            descendant_operation_ids=descendant_operation_ids,
            diagnostics=[]
        )
    
    def _evaluate_lambda(self, node: ast.Lambda) -> ExpressionResult:
        """Evaluate lambda expression with proper scope handling and unique scope ID."""
        # M4.6: Generate unique scope ID for this lambda
        lambda_id = self.ctx.binding_resolver._generate_scope_id()

        # Create parameter definitions for lambda
        from .models import Definition
        param_defs = []
        for arg in node.args.args:
            param_id = f"{self.ctx.function_id}_lambda_param_{arg.arg}_{lambda_id}"
            # M4.6: Use unique lambda scope ID in binding key
            binding_key = f"{self.ctx.function_id}::lambda:{lambda_id}::{arg.arg}"
            self.ctx.facts.definitions.append(Definition(
                id=param_id,
                variable=arg.arg,
                function_id=self.ctx.function_id,
                file=self.ctx.file,
                line=node.lineno,
                column=arg.col_offset if hasattr(arg, 'col_offset') else 0,
                kind='lambda_parameter',
                cfg_node_ids=self.ctx.get_cfg_node_ids(node),
                binding_key=binding_key,
                expression=ast.unparse(node) if hasattr(ast, 'unparse') else arg.arg,
                metadata={
                    'is_lambda_param': True,
                    'lambda_scope_id': lambda_id
                }
            ))
            param_defs.append(param_id)

        # Evaluate body (usually an expression)
        body = self.evaluate(node.body)

        metadata = {
            'param_count': len(node.args.args),
            'param_definition_ids': param_defs,
            'is_lambda': True,
            'lambda_scope_id': lambda_id
        }

        result = self._emit(node, 'Lambda', [body], metadata)
        # Lambda produces parameter definitions
        for op in self.ctx.facts.operations:
            if op.id == result.root_operation_id:
                op.output_definition_ids = param_defs
                break
        return result

    def _evaluate_list(self, node: ast.List) -> ExpressionResult:
        """Evaluate list literal."""
        children = [self.evaluate(elt) for elt in node.elts]
        use_ids, op_ids, descendants, diagnostics = self._collect(children)
        return ExpressionResult(None, use_ids, op_ids, descendants, diagnostics)

    def _evaluate_tuple(self, node: ast.Tuple) -> ExpressionResult:
        """Evaluate tuple literal."""
        children = [self.evaluate(elt) for elt in node.elts]
        use_ids, op_ids, descendants, diagnostics = self._collect(children)
        return ExpressionResult(None, use_ids, op_ids, descendants, diagnostics)

    def _evaluate_dict(self, node: ast.Dict) -> ExpressionResult:
        """Evaluate dict literal."""
        children = []
        for key in node.keys:
            if key:
                children.append(self.evaluate(key))
        for value in node.values:
            children.append(self.evaluate(value))
        use_ids, op_ids, descendants, diagnostics = self._collect(children)
        return ExpressionResult(None, use_ids, op_ids, descendants, diagnostics)

    def _evaluate_set(self, node: ast.Set) -> ExpressionResult:
        """Evaluate set literal."""
        children = [self.evaluate(elt) for elt in node.elts]
        use_ids, op_ids, descendants, diagnostics = self._collect(children)
        return ExpressionResult(None, use_ids, op_ids, descendants, diagnostics)

    def _evaluate_listcomp(self, node: ast.ListComp) -> ExpressionResult:
        """Evaluate list comprehension with unique scope ID."""
        # M4.6: Generate unique scope ID for this comprehension
        comprehension_id = self.ctx.binding_resolver._generate_scope_id()

        # Evaluate generators first (correct evaluation order)
        children = []

        for generator in node.generators:
            # Evaluate the iterable
            children.append(self.evaluate(generator.iter))

            # Create target definition for the loop variable with unique scope ID
            if isinstance(generator.target, ast.Name):
                target_name = generator.target.id
                cfg_node_ids = self.ctx.get_cfg_node_ids(node)
                # M4.6: Use unique comprehension scope ID in binding key
                binding_key = f"{self.ctx.function_id}::comprehension:{comprehension_id}::{target_name}"

                # Create a definition for the comprehension target
                from .models import Definition
                target_def_id = f"{self.ctx.function_id}_def_{target_name}_comp_{comprehension_id}"
                self.ctx.facts.definitions.append(Definition(
                    id=target_def_id,
                    variable=target_name,
                    function_id=self.ctx.function_id,
                    file=self.ctx.file,
                    line=node.lineno,
                    column=generator.target.col_offset if hasattr(generator.target, 'col_offset') else 0,
                    kind='comprehension_target',
                    cfg_node_ids=cfg_node_ids,
                    binding_key=binding_key,
                    expression=ast.unparse(generator.target) if hasattr(ast, 'unparse') else target_name,
                    metadata={
                        'is_comprehension_target': True,
                        'comprehension_scope_id': comprehension_id
                    }
                ))

            # Evaluate filter conditions
            for if_test in generator.ifs:
                children.append(self.evaluate(if_test))

        # Then evaluate the element expression
        children.append(self.evaluate(node.elt))

        use_ids, op_ids, descendants, diagnostics = self._collect(children)
        return ExpressionResult(None, use_ids, op_ids, descendants, diagnostics)

    def _evaluate_setcomp(self, node: ast.SetComp) -> ExpressionResult:
        """Evaluate set comprehension with unique scope ID."""
        # M4.6: Generate unique scope ID for this comprehension
        comprehension_id = self.ctx.binding_resolver._generate_scope_id()

        # Evaluate generators first
        children = []

        for generator in node.generators:
            children.append(self.evaluate(generator.iter))

            # M4.6: Create target definition with unique scope ID
            if isinstance(generator.target, ast.Name):
                target_name = generator.target.id
                cfg_node_ids = self.ctx.get_cfg_node_ids(node)
                binding_key = f"{self.ctx.function_id}::comprehension:{comprehension_id}::{target_name}"

                from .models import Definition
                target_def_id = f"{self.ctx.function_id}_def_{target_name}_comp_{comprehension_id}"
                self.ctx.facts.definitions.append(Definition(
                    id=target_def_id,
                    variable=target_name,
                    function_id=self.ctx.function_id,
                    file=self.ctx.file,
                    line=node.lineno,
                    column=generator.target.col_offset if hasattr(generator.target, 'col_offset') else 0,
                    kind='comprehension_target',
                    cfg_node_ids=cfg_node_ids,
                    binding_key=binding_key,
                    expression=ast.unparse(generator.target) if hasattr(ast, 'unparse') else target_name,
                    metadata={
                        'is_comprehension_target': True,
                        'comprehension_scope_id': comprehension_id
                    }
                ))

            for if_test in generator.ifs:
                children.append(self.evaluate(if_test))

        # Then evaluate the element expression
        children.append(self.evaluate(node.elt))

        use_ids, op_ids, descendants, diagnostics = self._collect(children)
        return ExpressionResult(None, use_ids, op_ids, descendants, diagnostics)

    def _evaluate_dictcomp(self, node: ast.DictComp) -> ExpressionResult:
        """Evaluate dict comprehension with unique scope ID."""
        # M4.6: Generate unique scope ID for this comprehension
        comprehension_id = self.ctx.binding_resolver._generate_scope_id()

        # Evaluate generators first
        children = []

        for generator in node.generators:
            children.append(self.evaluate(generator.iter))

            # M4.6: Create target definition with unique scope ID
            if isinstance(generator.target, ast.Name):
                target_name = generator.target.id
                cfg_node_ids = self.ctx.get_cfg_node_ids(node)
                binding_key = f"{self.ctx.function_id}::comprehension:{comprehension_id}::{target_name}"

                from .models import Definition
                target_def_id = f"{self.ctx.function_id}_def_{target_name}_comp_{comprehension_id}"
                self.ctx.facts.definitions.append(Definition(
                    id=target_def_id,
                    variable=target_name,
                    function_id=self.ctx.function_id,
                    file=self.ctx.file,
                    line=node.lineno,
                    column=generator.target.col_offset if hasattr(generator.target, 'col_offset') else 0,
                    kind='comprehension_target',
                    cfg_node_ids=cfg_node_ids,
                    binding_key=binding_key,
                    expression=ast.unparse(generator.target) if hasattr(ast, 'unparse') else target_name,
                    metadata={
                        'is_comprehension_target': True,
                        'comprehension_scope_id': comprehension_id
                    }
                ))

            for if_test in generator.ifs:
                children.append(self.evaluate(if_test))

        # Then evaluate key and value expressions
        children.append(self.evaluate(node.key))
        children.append(self.evaluate(node.value))

        use_ids, op_ids, descendants, diagnostics = self._collect(children)
        return ExpressionResult(None, use_ids, op_ids, descendants, diagnostics)

    def _evaluate_generatorexp(self, node: ast.GeneratorExp) -> ExpressionResult:
        """Evaluate generator expression with unique scope ID."""
        # M4.6: Generate unique scope ID for this comprehension
        comprehension_id = self.ctx.binding_resolver._generate_scope_id()

        # Evaluate generators first
        children = []

        for generator in node.generators:
            children.append(self.evaluate(generator.iter))

            # M4.6: Create target definition with unique scope ID
            if isinstance(generator.target, ast.Name):
                target_name = generator.target.id
                cfg_node_ids = self.ctx.get_cfg_node_ids(node)
                binding_key = f"{self.ctx.function_id}::comprehension:{comprehension_id}::{target_name}"

                from .models import Definition
                target_def_id = f"{self.ctx.function_id}_def_{target_name}_comp_{comprehension_id}"
                self.ctx.facts.definitions.append(Definition(
                    id=target_def_id,
                    variable=target_name,
                    function_id=self.ctx.function_id,
                    file=self.ctx.file,
                    line=node.lineno,
                    column=generator.target.col_offset if hasattr(generator.target, 'col_offset') else 0,
                    kind='comprehension_target',
                    cfg_node_ids=cfg_node_ids,
                    binding_key=binding_key,
                    expression=ast.unparse(generator.target) if hasattr(ast, 'unparse') else target_name,
                    metadata={
                        'is_comprehension_target': True,
                        'comprehension_scope_id': comprehension_id
                    }
                ))

            for if_test in generator.ifs:
                children.append(self.evaluate(if_test))

        # Then evaluate the element expression
        children.append(self.evaluate(node.elt))

        use_ids, op_ids, descendants, diagnostics = self._collect(children)
        return ExpressionResult(None, use_ids, op_ids, descendants, diagnostics)

    def _evaluate_yield(self, node: ast.Yield) -> ExpressionResult:
        """Evaluate yield expression."""
        if node.value:
            result = self.evaluate(node.value)
            return result
        return ExpressionResult(None, [], [], [], [])

    def _evaluate_yieldfrom(self, node: ast.YieldFrom) -> ExpressionResult:
        """Evaluate yield from expression."""
        return self.evaluate(node.value)

    def _evaluate_await(self, node: ast.Await) -> ExpressionResult:
        """Evaluate await expression."""
        return self.evaluate(node.value)

    def _evaluate_generic(self, node: ast.AST) -> ExpressionResult:
        """Generic fallback for unhandled node types."""
        # Try to visit child nodes recursively
        children = []
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                children.append(self.evaluate(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        children.append(self.evaluate(item))
        use_ids, op_ids, descendants, diagnostics = self._collect(children)
        return ExpressionResult(None, use_ids, op_ids, descendants, diagnostics)
