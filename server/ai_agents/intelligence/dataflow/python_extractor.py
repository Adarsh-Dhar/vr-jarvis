"""Python definition/use extractor for data-flow analysis."""
import ast
import symtable
from typing import List, Dict, Any, Optional, Set
from .models import Definition, VariableUse, DefUseFacts
from .recursive_expression_evaluator import RecursiveExpressionEvaluator, ExpressionEvaluationContext


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

        file_path = function_id.split('::')[0] if '::' in function_id else 'unknown'

        facts = DefUseFacts(
            function_id=function_id,
            file=file_path,
        )

        # Build symbol table to get scope information
        try:
            sym_table = symtable.symtable(source, file_path, 'exec')
            func_sym = self._find_function_symbol(sym_table, function_ast.name)
            local_vars = self._get_local_variables(func_sym) if func_sym else set()
        except Exception:
            # Fallback if symbol table fails
            local_vars = set()

        # Extract parameters as definitions
        param_cfg_node_ids = ast_index.get_cfg_nodes(function_ast) if cfg.entry_node_id else []
        param_defs = self._extract_parameters(function_ast, function_id, file_path, function_id, param_cfg_node_ids)
        facts.definitions.extend(param_defs)

        # Walk the AST to extract definitions and uses
        visitor = DefUseVisitor(
            function_id=function_id,
            file=file_path,
            local_vars=local_vars,
            cfg_node_map=cfg.ast_node_map,
            ast_index=ast_index,
            facts=facts,
        )
        visitor.visit(function_ast)

        return facts

    def _find_function_symbol(self, sym_table: symtable.SymbolTable, name: str) -> Optional[symtable.Function]:
        """Find a function symbol in the symbol table."""
        for sym in sym_table.get_symbols():
            if sym.get_name() == name and isinstance(sym, symtable.Function):
                return sym
        # Search nested scopes
        for child in sym_table.get_children():
            result = self._find_function_symbol(child, name)
            if result:
                return result
        return None

    def _get_local_variables(self, func_sym: symtable.Function) -> Set[str]:
        """Get the set of local variable names from a function symbol."""
        local_vars = set()
        for sym in func_sym.get_symbols():
            if sym.is_local():
                local_vars.add(sym.get_name())
        return local_vars

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
    ):
        self.function_id = function_id
        self.file = file
        self.local_vars = local_vars
        self.cfg_node_map = cfg_node_map
        self.ast_index = ast_index
        self.facts = facts
        self._definition_counter = 0
        self._use_counter = 0
        self._operation_counter = 0

    def _generate_def_id(self, variable: str) -> str:
        """Generate a unique definition ID."""
        self._definition_counter += 1
        return f"{self.function_id}_def_{variable}_{self._definition_counter}"

    def _generate_use_id(self, variable: str) -> str:
        """Generate a unique use ID."""
        self._use_counter += 1
        return f"{self.function_id}_use_{variable}_{self._use_counter}"

    def _generate_operation_id(self) -> str:
        """Generate a unique operation ID."""
        self._operation_counter += 1
        return f"{self.function_id}_op_{self._operation_counter}"

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
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        use_ids, op_id = evaluator.evaluate(node.value)
        
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

        # Do NOT call generic_visit(node) - would duplicate RHS visit

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Visit annotated assignment statements."""
        # Extract uses from RHS using recursive evaluator
        if node.value:
            ctx = ExpressionEvaluationContext(
                function_id=self.function_id,
                file=self.file,
                local_vars=self.local_vars,
                cfg_node_map=self.cfg_node_map,
                ast_index=self.ast_index,
                facts=self.facts
            )
            evaluator = RecursiveExpressionEvaluator(ctx)
            use_ids, op_id = evaluator.evaluate(node.value)
            
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
        if isinstance(node.target, ast.Name):
            binding_key = f"{self.function_id}::{node.target.id}"
            # Use
            self.facts.uses.append(VariableUse(
                id=self._generate_use_id(node.target.id),
                variable=node.target.id,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=node.target.col_offset if hasattr(node.target, 'col_offset') else 0,
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=ast.unparse(node.target) if hasattr(ast, 'unparse') else node.target.id,
            ))

        # Extract uses from RHS using recursive evaluator
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        use_ids, op_id = evaluator.evaluate(node.value)

        # Extract definition from target
        binding_key = f"{self.function_id}::{self._get_variable_name(node.target)}"
        def_ids_before = [d.id for d in self.facts.definitions]
        self._extract_target_definitions(node.target, node, 'augmented_assignment', binding_key, cfg_node_ids)
        new_def_ids = [d.id for d in self.facts.definitions if d.id not in def_ids_before]
        
        # Link operation to definition
        if op_id:
            for op in self.facts.operations:
                if op.id == op_id:
                    op.output_definition_ids.extend(new_def_ids)
                    break

        # Do NOT call generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Visit for loops."""
        # Extract uses from iterable using recursive evaluator
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        use_ids, op_id = evaluator.evaluate(node.iter)

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
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        
        for item in node.items:
            use_ids, op_id = evaluator.evaluate(item.context_expr)

            # Optional binding: `with resource as x`
            if item.optional_vars:
                binding_key = f"{self.function_id}::{self._get_variable_name(item.optional_vars)}"
                self._extract_target_definitions(item.optional_vars, node, 'with_binding', binding_key)

        # Visit body
        for stmt in node.body:
            self.visit(stmt)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Visit exception handlers."""
        # Exception name is a definition if present
        if node.name:
            binding_key = f"{self.function_id}::{node.name}"
            self.facts.definitions.append(Definition(
                id=self._generate_def_id(node.name),
                variable=node.name,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                kind='exception_handler',
                cfg_node_ids=self._get_cfg_node_ids(node),
                binding_key=binding_key,
                expression=None,
            ))

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
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        use_ids, op_id = evaluator.evaluate(node.value)

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
        """Visit return statements."""
        if node.value:
            ctx = ExpressionEvaluationContext(
                function_id=self.function_id,
                file=self.file,
                local_vars=self.local_vars,
                cfg_node_map=self.cfg_node_map,
                ast_index=self.ast_index,
                facts=self.facts
            )
            evaluator = RecursiveExpressionEvaluator(ctx)
            use_ids, op_id = evaluator.evaluate(node.value)

    def visit_Name(self, node: ast.Name) -> None:
        """Visit name nodes."""
        if isinstance(node.ctx, ast.Load):
            # Variable use
            # Only track if it's a local variable (not an attribute access like self.x)
            if node.id in self.local_vars or not self.local_vars:
                # Use module-level binding for globals
                binding_key = f"{self.function_id}::{node.id}"
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
                ))

    def visit_Global(self, node: ast.Global) -> None:
        """Visit global declarations."""
        for name in node.names:
            # Globals are module-level references
            binding_key = f"global::{name}"
            cfg_node_ids = self._get_cfg_node_ids(node) if self.ast_index else []
            self.facts.definitions.append(Definition(
                id=self._generate_def_id(name),
                variable=name,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                kind='global',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=None,
            ))

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        """Visit nonlocal declarations."""
        for name in node.names:
            # Nonlocals are closure references
            binding_key = f"nonlocal::{self.function_id}::{name}"
            cfg_node_ids = self._get_cfg_node_ids(node) if self.ast_index else []
            self.facts.definitions.append(Definition(
                id=self._generate_def_id(name),
                variable=name,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                kind='nonlocal',
                cfg_node_ids=cfg_node_ids,
                binding_key=binding_key,
                expression=None,
            ))

    # Expression visit methods are now handled by RecursiveExpressionEvaluator
    # in the higher-level statement visitors (Assign, AugAssign, Return, etc.)
    # These individual expression visitors are no longer needed.

    def visit_ListComp(self, node: ast.ListComp) -> None:
        """Visit list comprehensions."""
        # Use recursive evaluator for elements and generators
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        use_ids, op_id = evaluator.evaluate(node.elt)
        
        for generator in node.generators:
            iter_uses, _ = evaluator.evaluate(generator.iter)
            for if_test in generator.ifs:
                if_uses, _ = evaluator.evaluate(if_test)
        
        # Track loop variable as definition
        if node.generators:
            target = node.generators[0].target
            cfg_node_ids = self._get_cfg_node_ids(node)
            target_str = ast.unparse(target) if hasattr(ast, 'unparse') else str(target)
            binding_key = f"{self.function_id}::comprehension::{target_str}"
            self._extract_target_definitions(target, node, 'comprehension', binding_key, cfg_node_ids)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        """Visit set comprehensions."""
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        use_ids, op_id = evaluator.evaluate(node.elt)
        
        for generator in node.generators:
            iter_uses, _ = evaluator.evaluate(generator.iter)
            for if_test in generator.ifs:
                if_uses, _ = evaluator.evaluate(if_test)
        
        if node.generators:
            target = node.generators[0].target
            cfg_node_ids = self._get_cfg_node_ids(node)
            target_str = ast.unparse(target) if hasattr(ast, 'unparse') else str(target)
            binding_key = f"{self.function_id}::comprehension::{target_str}"
            self._extract_target_definitions(target, node, 'comprehension', binding_key, cfg_node_ids)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        """Visit dict comprehensions."""
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        use_ids, op_id = evaluator.evaluate(node.key)
        use_ids, op_id = evaluator.evaluate(node.value)
        
        for generator in node.generators:
            iter_uses, _ = evaluator.evaluate(generator.iter)
            for if_test in generator.ifs:
                if_uses, _ = evaluator.evaluate(if_test)
        
        if node.generators:
            target = node.generators[0].target
            cfg_node_ids = self._get_cfg_node_ids(node)
            target_str = ast.unparse(target) if hasattr(ast, 'unparse') else str(target)
            binding_key = f"{self.function_id}::comprehension::{target_str}"
            self._extract_target_definitions(target, node, 'comprehension', binding_key, cfg_node_ids)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        """Visit generator expressions."""
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        use_ids, op_id = evaluator.evaluate(node.elt)
        
        for generator in node.generators:
            iter_uses, _ = evaluator.evaluate(generator.iter)
            for if_test in generator.ifs:
                if_uses, _ = evaluator.evaluate(if_test)
        
        if node.generators:
            target = node.generators[0].target
            cfg_node_ids = self._get_cfg_node_ids(node)
            target_str = ast.unparse(target) if hasattr(ast, 'unparse') else str(target)
            binding_key = f"{self.function_id}::comprehension::{target_str}"
            self._extract_target_definitions(target, node, 'comprehension', binding_key, cfg_node_ids)

    def visit_Match(self, node: ast.Match) -> None:
        """Visit match statements and pattern bindings."""
        # Visit the subject expression using recursive evaluator
        ctx = ExpressionEvaluationContext(
            function_id=self.function_id,
            file=self.file,
            local_vars=self.local_vars,
            cfg_node_map=self.cfg_node_map,
            ast_index=self.ast_index,
            facts=self.facts
        )
        evaluator = RecursiveExpressionEvaluator(ctx)
        use_ids, op_id = evaluator.evaluate(node.subject)
        
        # Visit each case and its pattern
        for case in node.cases:
            self.visit(case.pattern)
            if case.guard:
                self.visit(case.guard)
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
            
            self._extract_target_definitions(
                target=node,
                source_node=node,
                binding_key=binding_key,
                cfg_node_ids=cfg_node_ids,
                kind='match_star'
            )

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

    def visit_Delete(self, node: ast.Delete) -> None:
        """Visit deletion statements (del x)."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                # Create a deletion fact
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
                    metadata={'is_deletion': True}
                ))
            elif isinstance(target, (ast.Attribute, ast.Subscript)):
                # Visit the complex target
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
            self._extract_target_definitions(target.value, source_node, f"{kind}_starred", binding_key, cfg_node_ids)
        elif isinstance(target, ast.Attribute):
            # Attribute assignment: `self.x = value`
            # For now, we don't track attribute definitions as local variables
            # This would require alias analysis
            pass
