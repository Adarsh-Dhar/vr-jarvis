"""Python definition/use extractor for data-flow analysis."""
import ast
import symtable
from typing import List, Dict, Any, Optional, Set
from .models import Definition, VariableUse, DefUseFacts, BindingResolver
from .recursive_expression_evaluator import RecursiveExpressionEvaluator, ExpressionEvaluationContext
from .ids import IdAllocator


class PythonDefUseExtractor:
    """Extract definition and use facts from Python AST."""

    def extract_function(
        self,
        artifact,
        source: str,
        file_path: str
    ) -> DefUseFacts:
        """Extract definition/use facts for a function using a CFG artifact."""
        function_ast = artifact.function_ast
        cfg = artifact.graph
        ast_index = artifact.ast_index
        function_id = cfg.function_id

        # Use explicitly supplied file_path, not derived from function_id
        facts = DefUseFacts(
            function_id=function_id,
            file=file_path,
        )

        # Build symbol table to get scope information
        local_vars = set()
        free_vars = set()
        global_vars = set()
        nonlocal_vars = set()
        try:
            sym_table = symtable.symtable(source, file_path, 'exec')
            func_sym = self._find_function_symbol(sym_table, function_id, function_ast.name)
            if func_sym:
                local_vars = self._get_local_variables(func_sym)
                free_vars = self._get_free_variables(func_sym)
                global_vars = self._get_global_variables(func_sym)
                nonlocal_vars = self._get_nonlocal_variables(func_sym)
        except Exception:
            # Fallback if symbol table fails - don't assume all names are local
            local_vars = set()
            free_vars = set()
            global_vars = set()
            nonlocal_vars = set()

        # Extract parameters as definitions
        param_cfg_node_ids = ast_index.get_cfg_nodes(function_ast) if cfg.entry_node_id else []
        param_defs = self._extract_parameters(function_ast, function_id, file_path, function_id, param_cfg_node_ids)
        facts.definitions.extend(param_defs)

        # Mark the root function so scope boundary visitors know to traverse it
        function_ast._is_root_function = True

        # Walk the AST to extract definitions and uses
        visitor = DefUseVisitor(
            function_id=function_id,
            file=file_path,
            local_vars=local_vars,
            free_vars=free_vars,
            global_vars=global_vars,
            nonlocal_vars=nonlocal_vars,
            cfg_node_map=cfg.ast_node_map,
            ast_index=ast_index,
            facts=facts,
            # Pass scope information for BindingResolver
            symbol_table=sym_table if 'sym_table' in locals() else None,
        )
        visitor.visit(function_ast)

        return facts

    def _find_function_symbol(self, sym_table: symtable.SymbolTable, function_id: str, name: str) -> Optional[symtable.Function]:
        """Find a function symbol in the symbol table using qualified identity.
        
        M4.2: Use precise matching with:
        - AST qualified scope
        - Parent lexical scope
        - Function name
        - Source line
        - Scope type
        """
        # First try to find by qualified function_id if available
        if '::' in function_id:
            # Extract the function name from qualified ID
            parts = function_id.split('::')
            if parts:
                name = parts[-1]

        # Search children (function scope tables) instead of get_symbols()
        # get_symbols() returns Symbol objects, not Function tables
        candidates = []
        for child in sym_table.get_children():
            if isinstance(child, symtable.Function) and child.get_name() == name:
                candidates.append(child)
            # Recursively search nested scopes
            result = self._find_function_symbol(child, function_id, name)
            if result:
                candidates.append(result)
        
        # M4.2: If multiple candidates, use source line and scope type to disambiguate
        if len(candidates) > 1:
            # For now, return the first match - could be improved with line number matching
            # if function AST line information is available
            return candidates[0]
        elif candidates:
            return candidates[0]
        
        return None

    def _get_local_variables(self, func_sym: symtable.Function) -> Set[str]:
        """Get the set of local variable names from a function symbol."""
        local_vars = set()
        for sym in func_sym.get_symbols():
            if sym.is_local() and not sym.is_global() and not sym.is_nonlocal():
                local_vars.add(sym.get_name())
        return local_vars

    def _get_free_variables(self, func_sym: symtable.Function) -> Set[str]:
        """Get free variables (closure variables) from a function symbol."""
        free_vars = set()
        for sym in func_sym.get_symbols():
            if sym.is_free():
                free_vars.add(sym.get_name())
        return free_vars

    def _get_global_variables(self, func_sym: symtable.Function) -> Set[str]:
        """Get global variables from a function symbol."""
        global_vars = set()
        for sym in func_sym.get_symbols():
            if sym.is_global():
                global_vars.add(sym.get_name())
        return global_vars

    def _get_nonlocal_variables(self, func_sym: symtable.Function) -> Set[str]:
        """Get nonlocal variables from a function symbol."""
        nonlocal_vars = set()
        for sym in func_sym.get_symbols():
            if sym.is_nonlocal():
                nonlocal_vars.add(sym.get_name())
        return nonlocal_vars

    def _extract_parameters(
        self,
        function_ast: ast.FunctionDef,
        function_id: str,
        file_path: str,
        function_binding_key: str,
        cfg_node_ids: List[str] = None
    ) -> List[Definition]:
        """Extract function parameters as definitions."""
        if cfg_node_ids is None:
            cfg_node_ids = []
        definitions = []
        args = function_ast.args

        # Positional-only args
        for arg in args.posonlyargs:
            binding_key = f"{function_id}::{arg.arg}"
            definitions.append(Definition(
                id=f"{function_id}_param_{arg.arg}",
                variable=arg.arg,
                function_id=function_id,
                file=file_path,
                line=function_ast.lineno,
                column=arg.col_offset if hasattr(arg, 'col_offset') else 0,
                kind='parameter',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=None,
            ))

        # Regular args
        for arg in args.args:
            binding_key = f"{function_id}::{arg.arg}"
            definitions.append(Definition(
                id=f"{function_id}_param_{arg.arg}",
                variable=arg.arg,
                function_id=function_id,
                file=file_path,
                line=function_ast.lineno,
                column=arg.col_offset if hasattr(arg, 'col_offset') else 0,
                kind='parameter',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=None,
            ))

        if args.vararg:
            binding_key = f"{function_id}::{args.vararg.arg}"
            definitions.append(Definition(
                id=f"{function_id}_param_{args.vararg.arg}",
                variable=args.vararg.arg,
                function_id=function_id,
                file=file_path,
                line=function_ast.lineno,
                column=args.vararg.col_offset if hasattr(args.vararg, 'col_offset') else 0,
                kind='parameter',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=None,
            ))

        for arg in args.kwonlyargs:
            binding_key = f"{function_id}::{arg.arg}"
            definitions.append(Definition(
                id=f"{function_id}_param_{arg.arg}",
                variable=arg.arg,
                function_id=function_id,
                file=file_path,
                line=function_ast.lineno,
                column=arg.col_offset if hasattr(arg, 'col_offset') else 0,
                kind='parameter',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=None,
            ))

        if args.kwarg:
            binding_key = f"{function_id}::{args.kwarg.arg}"
            definitions.append(Definition(
                id=f"{function_id}_param_{args.kwarg.arg}",
                variable=args.kwarg.arg,
                function_id=function_id,
                file=file_path,
                line=function_ast.lineno,
                column=args.kwarg.col_offset if hasattr(args.kwarg, 'col_offset') else 0,
                kind='parameter',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=None,
            ))

        return definitions


class DefUseVisitor(ast.NodeVisitor):
    """AST visitor to collect definitions and uses."""

    def __init__(
        self,
        function_id: str,
        file: str,
        local_vars: Set[str],
        cfg_node_map: Dict[str, str],
        ast_index,
        facts: DefUseFacts,
        free_vars: Set[str] = None,
        global_vars: Set[str] = None,
        nonlocal_vars: Set[str] = None,
        symbol_table=None,
    ):
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
        self.ids = IdAllocator(function_id)

    def _generate_def_id(self, variable: str) -> str:
        """Generate a unique definition ID."""
        return self.ids.definition(variable)

    def _generate_use_id(self, variable: str) -> str:
        """Generate a unique use ID."""
        return self.ids.use(variable)

    def _generate_operation_id(self) -> str:
        """Generate a unique operation ID."""
        return self.ids.operation()

    def _get_variable_name(self, node: ast.AST) -> str:
        """Extract variable name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # For attribute access like self.x, use the full attribute path
            return ast.unparse(node) if hasattr(ast, 'unparse') else str(node.id)
        elif isinstance(node, ast.Subscript):
            # For subscript like arr[i], use the full expression
            return ast.unparse(node) if hasattr(ast, 'unparse') else "subscript"
        else:
            return str(type(node).__name__)

    def _get_cfg_node_ids(self, node: ast.AST) -> List[str]:
        """Get CFG node IDs for an AST node using the AST-to-CFG index."""
        if not self.ast_index:
            return []
        node_ids = self.ast_index.get_cfg_nodes(node)
        if not node_ids:
            # Some nodes (like Global, Nonlocal) may not have explicit CFG nodes
            # Return empty list rather than raising error
            return []
        return node_ids

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignment statements with operation linking using recursive evaluator."""
        # Use recursive evaluator for RHS
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        result = evaluator.evaluate(node.value)
        use_ids = result.direct_input_use_ids
        op_id = result.root_operation_id
        child_ops = result.descendant_operation_ids

        # Extract definitions from targets
        for target in node.targets:
            binding_key = f"{self.function_id}::{self._get_variable_name(target)}"
            def_ids_before = [d.id for d in self.facts.definitions]
            self._extract_target_definitions(target, node, 'assignment', binding_key)
            new_def_ids = [d.id for d in self.facts.definitions if d.id not in def_ids_before]

            # Link the operation to these new definitions
            if op_id:
                for op in self.facts.operations:
                    if op.id == op_id:
                        op.output_definition_ids.extend(new_def_ids)
                        break
            else:
                # Handle simple assignments (x = y, x = 10) that don't create operations
                # M5.10: Create comprehensive copy/literal assignment metadata
                for new_def_id in new_def_ids:
                    for def_obj in self.facts.definitions:
                        if def_obj.id == new_def_id:
                            # Add metadata about the source
                            if isinstance(node.value, ast.Name):
                                def_obj.metadata = def_obj.metadata or {}
                                def_obj.metadata['copy_from'] = node.value.id
                                def_obj.metadata['is_copy'] = True
                                def_obj.metadata['source_type'] = 'variable'
                                def_obj.metadata['source_variable'] = node.value.id
                            elif isinstance(node.value, ast.Constant):
                                def_obj.metadata = def_obj.metadata or {}
                                def_obj.metadata['literal_value'] = str(node.value.value)
                                def_obj.metadata['is_literal'] = True
                                def_obj.metadata['source_type'] = 'literal'
                                def_obj.metadata['literal_type'] = type(node.value.value).__name__
                            elif isinstance(node.value, ast.Attribute):
                                # M5.10: Attribute copy: x = obj.attr
                                def_obj.metadata = def_obj.metadata or {}
                                def_obj.metadata['is_attribute_copy'] = True
                                def_obj.metadata['source_type'] = 'attribute'
                                def_obj.metadata['attribute_path'] = ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value)
                            elif isinstance(node.value, ast.Subscript):
                                # M5.10: Subscript copy: x = arr[i]
                                def_obj.metadata = def_obj.metadata or {}
                                def_obj.metadata['is_subscript_copy'] = True
                                def_obj.metadata['source_type'] = 'subscript'
                                def_obj.metadata['subscript_path'] = ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value)
                            break
                if isinstance(node.value, ast.Name) and use_ids:
                    # Simple copy: x = y
                    for use_id in use_ids:
                        # Find the use and link it to the definition
                        for use in self.facts.uses:
                            if use.id == use_id:
                                # Add metadata to definition indicating it's a copy
                                for def_id in new_def_ids:
                                    for definition in self.facts.definitions:
                                        if definition.id == def_id:
                                            definition.metadata['is_copy'] = True
                                            definition.metadata['source_use_id'] = use_id
                                            definition.metadata['source_variable'] = use.variable
                                            break
                                break
                elif isinstance(node.value, ast.Constant):
                    # Literal assignment: x = 10
                    for def_id in new_def_ids:
                        for definition in self.facts.definitions:
                            if definition.id == def_id:
                                definition.metadata['is_literal'] = True
                                definition.metadata['literal_value'] = node.value.value
                                break

        # Do NOT call generic_visit(node) - would duplicate RHS visit

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Visit annotated assignment statements."""
        # Extract uses from RHS using recursive evaluator
        if node.value:
            ctx = ExpressionEvaluationContext(
                function_id=self.function_id,
                file=self.file,
                local_vars=self.local_vars,
                free_vars=self.free_vars,
                global_vars=self.global_vars,
                nonlocal_vars=self.nonlocal_vars,
                cfg_node_map=self.cfg_node_map,
                ast_index=self.ast_index,
                facts=self.facts,
                symbol_table=self.symbol_table,
                ids=self.ids,
            )
            evaluator = RecursiveExpressionEvaluator(ctx)
            result = evaluator.evaluate(node.value)
            use_ids = result.direct_input_use_ids
            op_id = result.root_operation_id
            child_ops = result.descendant_operation_ids

            # Extract definition from target
            if node.target:
                binding_key = f"{self.function_id}::{self._get_variable_name(node.target)}"
                def_ids_before = [d.id for d in self.facts.definitions]
                self._extract_target_definitions(node.target, node, 'annotated_assignment', binding_key)
                new_def_ids = [d.id for d in self.facts.definitions if d.id not in def_ids_before]

                # Link operation to definition
                if op_id:
                    for op in self.facts.operations:
                        if op.id == op_id:
                            op.output_definition_ids.extend(new_def_ids)
                            break

        # Do NOT call generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Visit augmented assignment statements (+=, -=, etc.)."""
        # Target is both used and defined
        cfg_node_ids = self._get_cfg_node_ids(node)
        target_use_id = None
        if isinstance(node.target, ast.Name):
            binding_key = f"{self.function_id}::{node.target.id}"
            # Use of old target value
            target_use_id = self._generate_use_id(node.target.id)
            self.facts.uses.append(VariableUse(
                id=target_use_id,
                variable=node.target.id,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=node.target.col_offset if hasattr(node.target, 'col_offset') else 0,
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
            ))
        
        # Evaluate RHS with recursive evaluator to get operation graph
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids,
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        result = evaluator.evaluate(node.value)
        use_ids = result.direct_input_use_ids
        op_id = result.root_operation_id
        child_ops = result.descendant_operation_ids

        # Link augmented operation with RHS child operations (Milestone 5.3 fix)
        if op_id and child_ops:
            for op in self.facts.operations:
                if op.id == op_id:
                    op.input_operation_ids.extend(child_ops)
                    break

        # Extract uses from RHS using recursive evaluator
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids,
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        rhs_result = evaluator.evaluate(node.value)
        rhs_use_ids = rhs_result.direct_input_use_ids
        rhs_op_id = rhs_result.root_operation_id
        child_ops = rhs_result.descendant_operation_ids

        # Create the augmented binary operation node (e.g., Add for +=)
        # Map operator to operation type
        op_map = {
            ast.Add: 'Add',
            ast.Sub: 'Sub',
            ast.Mult: 'Mult',
            ast.Div: 'Div',
            ast.FloorDiv: 'FloorDiv',
            ast.Mod: 'Mod',
            ast.Pow: 'Pow',
            ast.LShift: 'LShift',
            ast.RShift: 'RShift',
            ast.BitOr: 'BitOr',
            ast.BitXor: 'BitXor',
            ast.BitAnd: 'BitAnd',
            ast.MatMult: 'MatMult',
        }
        op_type = op_map.get(type(node.op), 'AugmentedOp')

        # Collect input use IDs (old target + RHS uses)
        input_use_ids = []
        if target_use_id:
            input_use_ids.append(target_use_id)
        input_use_ids.extend(rhs_use_ids)

        # Create the augmented operation
        from .models import ExpressionFact
        aug_op_id = self._generate_operation_id()
        self.facts.operations.append(ExpressionFact(
            id=aug_op_id,
            operation=op_type,
            function_id=self.function_id,
            file=self.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            input_use_ids=input_use_ids,
            output_definition_ids=[],  # Will be filled after creating definition
            expression=ast.unparse(node) if hasattr(ast, 'unparse') else str(type(node.op).__name__),
        ))

        # Extract definition from target
        binding_key = f"{self.function_id}::{self._get_variable_name(node.target)}"
        def_ids_before = [d.id for d in self.facts.definitions]
        self._extract_target_definitions(node.target, node, 'augmented_assignment', binding_key, cfg_node_ids)
        new_def_ids = [d.id for d in self.facts.definitions if d.id not in def_ids_before]

        # Link augmented operation to the new definition
        for op in self.facts.operations:
            if op.id == aug_op_id:
                op.output_definition_ids.extend(new_def_ids)
                break

        # Do NOT call generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Visit if statements - extract condition expression."""
        # Evaluate the condition expression
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        test_result = evaluator.evaluate(node.test)
        use_ids = test_result.direct_input_use_ids
        op_id = test_result.root_operation_id
        child_ops = test_result.descendant_operation_ids

        # Visit body and else clause
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_While(self, node: ast.While) -> None:
        """Visit while statements - extract condition expression."""
        # Evaluate the condition expression
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        test_result = evaluator.evaluate(node.test)
        use_ids = test_result.direct_input_use_ids
        op_id = test_result.root_operation_id
        child_ops = test_result.descendant_operation_ids

        # Visit body and else clause
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_Assert(self, node: ast.Assert) -> None:
        """Visit assert statements - extract test and message expressions."""
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)

        # Evaluate test expression
        test_result = evaluator.evaluate(node.test)
        use_ids = test_result.direct_input_use_ids
        op_id = test_result.root_operation_id
        child_ops = test_result.descendant_operation_ids

        # Evaluate message expression if present
        if node.msg:
            msg_result = evaluator.evaluate(node.msg)
            use_ids = msg_result.direct_input_use_ids
            op_id = msg_result.root_operation_id
            child_ops = msg_result.descendant_operation_ids

    def visit_For(self, node: ast.For) -> None:
        """Visit for loops."""
        # Extract uses from iterable using recursive evaluator
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        iter_result = evaluator.evaluate(node.iter)
        use_ids = iter_result.direct_input_use_ids
        op_id = iter_result.root_operation_id
        child_ops = iter_result.descendant_operation_ids

        # Loop variable is a definition
        binding_key = f"{self.function_id}::{self._get_variable_name(node.target)}"
        self._extract_target_definitions(node.target, node, 'for_loop', binding_key)

        # Visit body (but don't traverse into nested functions)
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Record as binding but don't traverse into nested scope
                continue
            self.visit(stmt)

        # Visit else clause
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_With(self, node: ast.With) -> None:
        """Visit with statements."""
        # Extract uses from context managers using recursive evaluator
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)

        for item in node.items:
            context_result = evaluator.evaluate(item.context_expr)
            use_ids = context_result.direct_input_use_ids
            op_id = context_result.root_operation_id
            child_ops = context_result.descendant_operation_ids

            # Optional binding: `with resource as x`
            if item.optional_vars:
                binding_key = f"{self.function_id}::{self._get_variable_name(item.optional_vars)}"
                self._extract_target_definitions(item.optional_vars, node, 'with_binding', binding_key)

        # Visit body
        for stmt in node.body:
            self.visit(stmt)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        """Visit named expressions (walrus operator :=)."""
        # Extract uses from value using recursive evaluator
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        result = evaluator.evaluate(node.value)
        use_ids = result.direct_input_use_ids
        op_id = result.root_operation_id
        child_ops = result.descendant_operation_ids

        # Target is a definition
        binding_key = f"{self.function_id}::{self._get_variable_name(node.target)}"
        def_ids_before = [d.id for d in self.facts.definitions]
        self._extract_target_definitions(node.target, node, 'named_expression', binding_key)
        new_def_ids = [d.id for d in self.facts.definitions if d.id not in def_ids_before]

        # Link operation to definition
        if op_id:
            for op in self.facts.operations:
                if op.id == op_id:
                    op.output_definition_ids.extend(new_def_ids)
                    break

    def visit_Return(self, node: ast.Return) -> None:
        """Visit return statements and connect return expression to return-value sink."""
        from .models import ExpressionFact
        
        if node.value:
            ctx = ExpressionEvaluationContext(
                function_id=self.function_id,
                file=self.file,
                local_vars=self.local_vars,
                free_vars=self.free_vars,
                global_vars=self.global_vars,
                nonlocal_vars=self.nonlocal_vars,
                cfg_node_map=self.cfg_node_map,
                ast_index=self.ast_index,
                facts=self.facts,
                symbol_table=self.symbol_table,
                ids=self.ids
            )
            evaluator = RecursiveExpressionEvaluator(ctx)
            result = evaluator.evaluate(node.value)
            use_ids = result.direct_input_use_ids
            op_id = result.root_operation_id
            child_ops = result.descendant_operation_ids

            # Connect the root operation to the return-value sink
            # M5.11: Connect return expression to return-value sink with operation graph
            # We represent this by storing the operation_id in a special metadata field
            # on a synthetic "return_value" operation fact
            if op_id:
                # Create a return-value sink operation that represents the return value
                return_sink_id = self._generate_operation_id()
                self.facts.operations.append(ExpressionFact(
                    id=return_sink_id,
                    function_id=self.function_id,
                    file=self.file,
                    line=node.lineno,
                    column=node.col_offset if hasattr(node, 'col_offset') else 0,
                    cfg_node_ids=self._get_cfg_node_ids(node),
                    expression=ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value),
                    operation='return_value',
                    input_use_ids=use_ids,
                    input_operation_ids=[op_id] if op_id else [],
                    output_definition_ids=[],
                    metadata={
                        'is_return_sink': True,
                        'root_operation_id': op_id,
                        'return_expression_connected': True  # M5.11: Confirm connection
                    }
                ))
            elif isinstance(node.value, ast.Name):
                # M5.11: For simple return x, connect reaching definition of x to return sink
                # This is tracked via the use_ids which reference the variable's uses
                return_sink_id = self._generate_operation_id()
                self.facts.operations.append(ExpressionFact(
                    id=return_sink_id,
                    function_id=self.function_id,
                    file=self.file,
                    line=node.lineno,
                    column=node.col_offset if hasattr(node, 'col_offset') else 0,
                    cfg_node_ids=self._get_cfg_node_ids(node),
                    expression=ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value),
                    operation='return_value',
                    input_use_ids=use_ids,
                    input_operation_ids=[],
                    output_definition_ids=[],
                    metadata={
                        'is_return_sink': True,
                        'return_variable': node.value.id,
                        'return_via_binding': True  # M5.11: Return via binding resolution
                    }
                ))
            elif isinstance(node.value, ast.Constant):
                # M5.11: For return 42, record literal provenance
                return_sink_id = self._generate_operation_id()
                self.facts.operations.append(ExpressionFact(
                    id=return_sink_id,
                    function_id=self.function_id,
                    file=self.file,
                    line=node.lineno,
                    column=node.col_offset if hasattr(node, 'col_offset') else 0,
                    cfg_node_ids=self._get_cfg_node_ids(node),
                    expression=ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value),
                    operation='return_value',
                    input_use_ids=[],
                    input_operation_ids=[],
                    output_definition_ids=[],
                    metadata={
                        'is_return_sink': True,
                        'literal_value': str(node.value.value),
                        'return_literal': True  # M5.11: Return literal provenance
                    }
                ))

    def visit_Expr(self, node: ast.Expr) -> None:
        """Visit expression statements (standalone function calls, etc.)."""
        if node.value:
            ctx = ExpressionEvaluationContext(
                function_id=self.function_id,
                file=self.file,
                local_vars=self.local_vars,
                free_vars=self.free_vars,
                global_vars=self.global_vars,
                nonlocal_vars=self.nonlocal_vars,
                cfg_node_map=self.cfg_node_map,
                ast_index=self.ast_index,
                facts=self.facts,
                symbol_table=self.symbol_table,
                ids=self.ids
            )
            evaluator = RecursiveExpressionEvaluator(ctx)
            result = evaluator.evaluate(node.value)
            use_ids = result.direct_input_use_ids
            op_id = result.root_operation_id
            child_ops = result.descendant_operation_ids
            # Operation facts are already created by the evaluator

    def visit_Name(self, node: ast.Name) -> None:
        """Visit name nodes."""
        if isinstance(node.ctx, ast.Load):
            # Variable use
            # Check if it's a local variable
            is_local = node.id in self.local_vars
            is_free = node.id in self.free_vars
            is_global = node.id in self.global_vars
            is_nonlocal = node.id in self.nonlocal_vars

            # If not local/free/global/nonlocal, check if it's a builtin
            if not (is_local or is_free or is_global or is_nonlocal) and node.id in dir(__builtins__):
                return  # Don't track builtins as uses

            # Track local variables, free variables (closures), globals, and nonlocals
            if is_local or is_free or is_global or is_nonlocal or not self.local_vars:
                # Determine binding key based on scope category
                if is_local:
                    # Local variable - function-scoped binding
                    binding_key = f"{self.function_id}::{node.id}"
                elif is_free:
                    # Free variable (closure) - resolves to enclosing scope
                    # Use a special binding key that indicates it's captured
                    binding_key = f"closure::{node.id}"
                elif is_nonlocal:
                    # Nonlocal variable - resolves to enclosing function scope
                    binding_key = f"nonlocal::{node.id}"
                elif is_global:
                    # Global variable - module-level binding
                    binding_key = f"global::{node.id}"
                else:
                    # Fallback: external/unresolved reference
                    binding_key = f"external::{node.id}"
                cfg_node_ids = self._get_cfg_node_ids(node)
                self.facts.uses.append(VariableUse(
                    id=self._generate_use_id(node.id),
                    variable=node.id,
                    function_id=self.function_id,
                    file=self.file,
                    line=node.lineno,
                    column=node.col_offset if hasattr(node, 'col_offset') else 0,
                    cfg_node_ids=cfg_node_ids,
                    binding_key=binding_key,
                    expression=ast.unparse(node) if hasattr(ast, 'unparse') else node.id,
                    metadata={
                        'is_closure': is_free,
                        'is_global': is_global,
                        'is_nonlocal': is_nonlocal,
                        'is_local': is_local
                    }
                ))

    def visit_Global(self, node: ast.Global) -> None:
        """Visit global declarations - do not create value definitions."""
        # Global declarations are scope markers, not value assignments
        # They indicate the variable refers to module-level binding
        pass

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        """Visit nonlocal declarations - do not create value definitions."""
        # Nonlocal declarations are scope markers, not value assignments
        # They indicate the variable refers to enclosing scope binding
        pass

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements - bind imported names as 'import'
        definitions scoped to this function."""
        self._visit_import(node, 'Import')

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from-imports - same binding treatment as visit_Import."""
        self._visit_import(node, 'ImportFrom')

    def _visit_import(self, node, operation: str) -> None:
        """Record an Import/ImportFrom operation plus one 'import' definition
        per bound name. The definition carries the import metadata and the
        function-scoped binding key, so reaching definitions and cross-module
        binding resolution can see function-local imports."""
        from .models import ExpressionFact
        cfg_node_ids = self._get_cfg_node_ids(node)
        self.facts.operations.append(ExpressionFact(
            id=self._generate_operation_id(),
            function_id=self.function_id,
            file=self.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=ast.unparse(node) if hasattr(ast, 'unparse') else operation,
            operation=operation,
            metadata={'scope': self.function_id}))
        for a in node.names:
            if isinstance(node, ast.Import):
                bound = (a.asname or a.name).split('.')[0]
                meta = {'import_module': a.name, 'import_kind': 'import',
                        'import_name': a.name, 'scope': self.function_id}
            else:
                if a.name == '*':
                    continue
                bound = a.asname or a.name
                meta = {'import_module': node.module or '',
                        'import_level': node.level, 'import_kind': 'from',
                        'import_name': a.name, 'scope': self.function_id}
            self.facts.definitions.append(Definition(
                id=self._generate_def_id(bound),
                variable=bound,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=0,
                kind='import',
                cfg_node_ids=cfg_node_ids,
                binding_key='%s::%s' % (self.function_id, bound),
                expression=ast.unparse(node) if hasattr(ast, 'unparse') else None,
                metadata=meta,
            ))

    # Expression visit methods are now handled by RecursiveExpressionEvaluator
    # in the higher-level statement visitors (Assign, AugAssign, Return, etc.)
    # These individual expression visitors are no longer needed.

    def visit_ListComp(self, node: ast.ListComp) -> None:
        """Visit list comprehensions."""
        # Use recursive evaluator for generators first (correct evaluation order)
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)

        # Process all generators first to establish scope
        for generator in node.generators:
            iter_result = evaluator.evaluate(generator.iter)
            iter_uses = iter_result.direct_input_use_ids
            for if_test in generator.ifs:
                if_result = evaluator.evaluate(if_test)
                if_uses = if_result.direct_input_use_ids
            # Define target for this generator
            target_str = ast.unparse(generator.target) if hasattr(ast, 'unparse') else str(generator.target)
            binding_key = f"{self.function_id}::comprehension::{target_str}"
            self._extract_target_definitions(generator.target, node, 'comprehension', binding_key, self._get_cfg_node_ids(node))

        # Now evaluate the element expression (can reference comprehension variables)
        elt_result = evaluator.evaluate(node.elt)
        use_ids = elt_result.direct_input_use_ids
        op_id = elt_result.root_operation_id

    def visit_SetComp(self, node: ast.SetComp) -> None:
        """Visit set comprehensions."""
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)

        # Process all generators first
        for generator in node.generators:
            iter_result = evaluator.evaluate(generator.iter)
            iter_uses = iter_result.direct_input_use_ids
            for if_test in generator.ifs:
                if_result = evaluator.evaluate(if_test)
                if_uses = if_result.direct_input_use_ids
            # Define target for this generator
            target_str = ast.unparse(generator.target) if hasattr(ast, 'unparse') else str(generator.target)
            binding_key = f"{self.function_id}::comprehension::{target_str}"
            self._extract_target_definitions(generator.target, node, 'comprehension', binding_key, self._get_cfg_node_ids(node))

        # Now evaluate the element expression
        elt_result = evaluator.evaluate(node.elt)
        use_ids = elt_result.direct_input_use_ids
        op_id = elt_result.root_operation_id

    def visit_DictComp(self, node: ast.DictComp) -> None:
        """Visit dict comprehensions."""
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)

        # Process all generators first
        for generator in node.generators:
            iter_result = evaluator.evaluate(generator.iter)
            iter_uses = iter_result.direct_input_use_ids
            for if_test in generator.ifs:
                if_result = evaluator.evaluate(if_test)
                if_uses = if_result.direct_input_use_ids
            # Define target for this generator
            target_str = ast.unparse(generator.target) if hasattr(ast, 'unparse') else str(generator.target)
            binding_key = f"{self.function_id}::comprehension::{target_str}"
            self._extract_target_definitions(generator.target, node, 'comprehension', binding_key, self._get_cfg_node_ids(node))

        # Now evaluate key and value expressions
        key_result = evaluator.evaluate(node.key)
        use_ids = key_result.direct_input_use_ids
        op_id = key_result.root_operation_id
        value_result = evaluator.evaluate(node.value)
        use_ids = value_result.direct_input_use_ids
        op_id = value_result.root_operation_id

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        """Visit generator expressions."""
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)

        # Process all generators first
        for generator in node.generators:
            iter_result = evaluator.evaluate(generator.iter)
            iter_uses = iter_result.direct_input_use_ids
            for if_test in generator.ifs:
                if_result = evaluator.evaluate(if_test)
                if_uses = if_result.direct_input_use_ids
            # Define target for this generator
            target_str = ast.unparse(generator.target) if hasattr(ast, 'unparse') else str(generator.target)
            binding_key = f"{self.function_id}::comprehension::{target_str}"
            self._extract_target_definitions(generator.target, node, 'comprehension', binding_key, self._get_cfg_node_ids(node))

        # Now evaluate the element expression
        elt_result = evaluator.evaluate(node.elt)
        use_ids = elt_result.direct_input_use_ids
        op_id = elt_result.root_operation_id

    def visit_Match(self, node: ast.Match) -> None:
        """Visit match statements and pattern bindings."""
        # Visit the subject expression using recursive evaluator
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            free_vars=self.free_vars,
            global_vars=self.global_vars,
            nonlocal_vars=self.nonlocal_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts,
            symbol_table=self.symbol_table,
            ids=self.ids
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        subject_result = evaluator.evaluate(node.subject)
        use_ids = subject_result.direct_input_use_ids
        op_id = subject_result.root_operation_id
        child_ops = subject_result.descendant_operation_ids

        # Visit each case and its pattern
        for case in node.cases:
            self.visit(case.pattern)
            if case.guard:
                # Evaluate guard expression using recursive evaluator
                guard_result = evaluator.evaluate(case.guard)
                use_ids = guard_result.direct_input_use_ids
                op_id = guard_result.root_operation_id
                child_ops = guard_result.descendant_operation_ids
            # Visit body statements individually, not as a list
            for stmt in case.body:
                self.visit(stmt)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        """Visit capture patterns (e.g., `as name`)."""
        # Visit the pattern being captured
        if node.pattern:
            self.visit(node.pattern)
        
        # If there's a name, create a definition for the captured variable
        if node.name:
            cfg_node_ids = self._get_cfg_node_ids(node)
            binding_key = f"{self.function_id}::{node.name}"
            
            self._extract_target_definitions(
                target=node,
                source_node=node,
                binding_key=binding_key,
                cfg_node_ids=cfg_node_ids,
                kind='match_capture'
            )

    def visit_MatchSequence(self, node: ast.MatchSequence) -> None:
        """Visit sequence patterns (e.g., `[a, b, c]`)."""
        for pattern in node.patterns:
            self.visit(pattern)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        """Visit mapping patterns (e.g., `{'key': value}`)."""
        for key_pattern in node.keys:
            if key_pattern:
                self.visit(key_pattern)
        for value_pattern in node.patterns:
            self.visit(value_pattern)

    def visit_MatchClass(self, node: ast.MatchClass) -> None:
        """Visit class patterns (e.g., `Point(x, y)`)."""
        self.visit(node.cls)
        for pattern in node.patterns:
            self.visit(pattern)
        for kw_pattern in node.kwd_patterns:
            self.visit(kw_pattern)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        """Visit star patterns (e.g., `*rest`)."""
        if node.name:
            cfg_node_ids = self._get_cfg_node_ids(node)
            binding_key = f"{self.function_id}::{node.name}"

            # Create definition for the star variable
            self.facts.definitions.append(Definition(
                id=self._generate_def_id(node.name),
                variable=node.name,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                kind='match_star',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=f"*{node.name}",
                metadata={'is_match_star': True, 'pattern_type': 'star'}
            ))

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        """Visit AS patterns (e.g., `pattern as name`)."""
        # Visit the inner pattern first
        if node.pattern:
            self.visit(node.pattern)
        # Create definition for the captured variable
        if node.name:
            cfg_node_ids = self._get_cfg_node_ids(node)
            binding_key = f"{self.function_id}::{node.name}"

            self.facts.definitions.append(Definition(
                id=self._generate_def_id(node.name),
                variable=node.name,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                kind='match_as',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=node.name,
                metadata={'is_match_as': True, 'pattern_type': 'capture'}
            ))

    def visit_MatchOr(self, node: ast.MatchOr) -> None:
        """Visit OR patterns (e.g., `a | b`)."""
        for pattern in node.patterns:
            self.visit(pattern)

    def visit_MatchValue(self, node: ast.MatchValue) -> None:
        """Visit value patterns (e.g., `1`, `'string'`)."""
        self.visit(node.value)

    def visit_MatchSingleton(self, node: ast.MatchSingleton) -> None:
        """Visit singleton patterns (e.g., `True`, `False`, `None`)."""
        # No variable binding, just the value
        pass

    # Scope boundary visitors - only traverse into the root function, not nested scopes
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions - only traverse if it's the root function."""
        # Only traverse if this is the function we're analyzing (has same function_id)
        # Nested functions are separate scopes - don't analyze their bodies
        if hasattr(node, '_is_root_function') and node._is_root_function:
            self.generic_visit(node)
        # Otherwise, skip nested function bodies

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definitions - only traverse if it's the root function."""
        if hasattr(node, '_is_root_function') and node._is_root_function:
            self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definitions - classes are separate scopes."""
        # Don't traverse into class bodies
        pass

    def visit_Lambda(self, node: ast.Lambda) -> None:
        """Visit lambda expressions - lambdas are separate scopes."""
        # Don't traverse into lambda bodies
        pass

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Visit exception handlers - create definition for exception variable and kill-only event."""
        # If handler has a name (e.g., 'except Exception as exc'), create a definition
        if node.name:
            cfg_node_ids = self._get_cfg_node_ids(node)
            # Use the same binding key format as regular variables for consistency
            # This ensures exception variables can be connected to their uses
            binding_key = f"{self.function_id}::{node.name}"

            # Create definition for the exception variable
            self.facts.definitions.append(Definition(
                id=self._generate_def_id(node.name),
                variable=node.name,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                kind='exception_variable',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=f"except ... as {node.name}",
                metadata={
                    'is_exception_variable': True,
                    'exception_type': ast.unparse(node.type) if node.type else 'Exception',
                    'is_cleared_after_handler': True
                }
            ))

        # Visit the handler body
        for stmt in node.body:
            self.visit(stmt)
        
        # M4.5: Create kill-only event after handler body for exception variable
        # This clears the exception variable on every normal and abrupt exit from the handler
        if node.name:
            cfg_node_ids = self._get_cfg_node_ids(node)
            binding_key = f"{self.function_id}::{node.name}"
            
            self.facts.definitions.append(Definition(
                id=self._generate_def_id(f"{node.name}_clear"),
                variable=node.name,
                function_id=self.function_id,
                file=self.file,
                line=node.body[-1].end_lineno if node.body else node.lineno,
                column=0,
                kind='exception_variable_clear',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=f"# Clear {node.name} after except handler",
                metadata={
                    'is_kill_only': True,
                    'clears_exception_variable': node.name,
                    'binding_key': binding_key
                }
            ))

    def visit_Delete(self, node: ast.Delete) -> None:
        """Visit deletion statements (del x) - create kill-only events."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                # Create a deletion fact (kill-only, not a value definition)
                cfg_node_ids = self._get_cfg_node_ids(node)
                binding_key = f"{self.function_id}::{target.id}"

                from .models import Definition
                deletion_id = self._generate_def_id(target.id)
                self.facts.definitions.append(Definition(
                    id=deletion_id,
                    variable=target.id,
                    function_id=self.function_id,
                    file=self.file,
                    line=node.lineno,
                    column=node.col_offset if hasattr(node, 'col_offset') else 0,
                    cfg_node_ids=cfg_node_ids,
                    binding_key=binding_key,
                    kind='deletion',
                    expression=f"del {target.id}",
                    metadata={'is_deletion': True, 'is_kill_only': True}
                ))
            elif isinstance(target, (ast.Attribute, ast.Subscript)):
                # Visit the complex target for reads
                self.visit(target)
                # Deletion could be tracked as a mutation operation
                pass
            else:
                # Tuple/list unpacking deletion
                self.visit(target)

    def _extract_target_definitions(
        self,
        target: ast.AST,
        source_node: ast.AST,
        kind: str,
        binding_key: str,
        cfg_node_ids: List[str] = None
    ) -> None:
        """Extract definitions from assignment targets."""
        if cfg_node_ids is None:
            cfg_node_ids = self._get_cfg_node_ids(source_node)
        if isinstance(target, ast.Name):
            # Simple name assignment
            self.facts.definitions.append(Definition(
                id=self._generate_def_id(target.id),
                variable=target.id,
                function_id=self.function_id,
                file=self.file,
                line=source_node.lineno,
                column=target.col_offset if hasattr(target, 'col_offset') else 0,
                kind=kind,
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=ast.unparse(source_node) if hasattr(ast, 'unparse') else None,
            ))
        elif isinstance(target, (ast.Tuple, ast.List)):
            # Tuple/list unpacking: `a, b = value`
            for elt in target.elts:
                # Create separate binding key for each unpacked variable
                elt_binding_key = f"{self.function_id}::{self._get_variable_name(elt)}"
                self._extract_target_definitions(elt, source_node, f"{kind}_unpack", elt_binding_key, cfg_node_ids)
        elif isinstance(target, ast.Starred):
            # Starred unpacking: `*rest = value`
            # Use the underlying Starred.value name, not the Starred node itself
            if isinstance(target.value, ast.Name):
                # Create definition for the actual variable name (e.g., 'rest' in '*rest')
                actual_name = target.value.id
                actual_binding_key = f"{self.function_id}::{actual_name}"
                self.facts.definitions.append(Definition(
                    id=self._generate_def_id(actual_name),
                    variable=actual_name,
                    function_id=self.function_id,
                    file=self.file,
                    line=source_node.lineno,
                    column=target.value.col_offset if hasattr(target.value, 'col_offset') else 0,
                    kind=f"{kind}_starred",
                    cfg_node_ids=cfg_node_ids,
                    binding_key=actual_binding_key,
                    expression=ast.unparse(target) if hasattr(ast, 'unparse') else actual_name,
                    metadata={'is_starred': True}
                ))
            else:
                # For complex starred expressions, recurse
                self._extract_target_definitions(target.value, source_node, f"{kind}_starred", binding_key, cfg_node_ids)
        elif isinstance(target, ast.Attribute):
            # Attribute assignment: `self.x = value`
            # Track as attribute definition with receiver identity
            attr_name = ast.unparse(target) if hasattr(ast, 'unparse') else f"{ast.unparse(target.value)}.{target.attr}"
            attr_binding_key = f"{self.function_id}::attribute::{attr_name}"

            # Generate use for the receiver (e.g., `self` in `self.x = value`)
            if isinstance(target.value, ast.Name) and target.value.id in self.local_vars:
                receiver_use_id = self._generate_use_id(target.value.id)
                receiver_binding_key = f"{self.function_id}::{target.value.id}"
                self.facts.uses.append(VariableUse(
                    id=receiver_use_id,
                    variable=target.value.id,
                    function_id=self.function_id,
                    file=self.file,
                    line=target.value.lineno if hasattr(target.value, 'lineno') else source_node.lineno,
                    column=target.value.col_offset if hasattr(target.value, 'col_offset') else 0,
                    cfg_node_ids=cfg_node_ids,
                    binding_key=receiver_binding_key,
                    expression=ast.unparse(target.value) if hasattr(ast, 'unparse') else target.value.id,
                    metadata={'is_attribute_receiver': True, 'target_attribute': target.attr}
                ))

            self.facts.definitions.append(Definition(
                id=self._generate_def_id(attr_name),
                variable=attr_name,
                function_id=self.function_id,
                file=self.file,
                line=source_node.lineno,
                column=target.col_offset if hasattr(target, 'col_offset') else 0,
                kind=f"{kind}_attribute",
                cfg_node_ids=cfg_node_ids,
                binding_key=attr_binding_key,
                expression=ast.unparse(source_node) if hasattr(ast, 'unparse') else None,
                metadata={
                    'is_attribute': True,
                    'receiver': ast.unparse(target.value) if hasattr(ast, 'unparse') else str(target.value),
                    'attribute': target.attr,
                    'is_mutation': kind in ('assignment', 'augmented_assignment')
                }
            ))
        elif isinstance(target, ast.Subscript):
            # Subscript assignment: `arr[i] = value`
            # Track as subscript definition with collection and key identity
            subscript_name = ast.unparse(target) if hasattr(ast, 'unparse') else "subscript"
            subscript_binding_key = f"{self.function_id}::subscript::{subscript_name}"

            # Generate use for the collection (e.g., `arr` in `arr[i] = value`)
            if isinstance(target.value, ast.Name) and target.value.id in self.local_vars:
                collection_use_id = self._generate_use_id(target.value.id)
                collection_binding_key = f"{self.function_id}::{target.value.id}"
                self.facts.uses.append(VariableUse(
                    id=collection_use_id,
                    variable=target.value.id,
                    function_id=self.function_id,
                    file=self.file,
                    line=target.value.lineno if hasattr(target.value, 'lineno') else source_node.lineno,
                    column=target.value.col_offset if hasattr(target.value, 'col_offset') else 0,
                    cfg_node_ids=cfg_node_ids,
                    binding_key=collection_binding_key,
                    expression=ast.unparse(target.value) if hasattr(ast, 'unparse') else target.value.id,
                    metadata={'is_subscript_collection': True}
                ))

            self.facts.definitions.append(Definition(
                id=self._generate_def_id(subscript_name),
                variable=subscript_name,
                function_id=self.function_id,
                file=self.file,
                line=source_node.lineno,
                column=target.col_offset if hasattr(target, 'col_offset') else 0,
                kind=f"{kind}_subscript",
                cfg_node_ids=cfg_node_ids,
                binding_key=subscript_binding_key,
                expression=ast.unparse(source_node) if hasattr(ast, 'unparse') else None,
                metadata={
                    'is_subscript': True,
                    'collection': ast.unparse(target.value) if hasattr(ast, 'unparse') else str(target.value),
                    'key': ast.unparse(target.slice) if hasattr(ast, 'unparse') else str(target.slice),
                    'is_mutation': kind in ('assignment', 'augmented_assignment')
                }
            ))
