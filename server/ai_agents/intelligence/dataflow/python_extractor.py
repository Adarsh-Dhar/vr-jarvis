"""Python definition/use extractor for data-flow analysis."""
import ast
import symtable
from typing import List, Dict, Any, Optional, Set
from .models import Definition, VariableUse, DefUseFacts


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
        """Visit assignment statements with operation linking."""
        # Extract uses from RHS and track if it's a complex expression
        use_ids_before = [u.id for u in self.facts.uses]
        op_ids_before = [o.id for o in self.facts.operations]
        
        self.visit(node.value)
        
        # Get new uses and operations created by RHS
        new_use_ids = [u.id for u in self.facts.uses if u.id not in use_ids_before]
        new_op_ids = [o.id for o in self.facts.operations if o.id not in op_ids_before]
        
        # If RHS created operations, link the last one to the target definitions
        last_op_id = new_op_ids[-1] if new_op_ids else None
        
        # Extract definitions from targets using the existing method
        for target in node.targets:
            binding_key = f"{self.function_id}::{self._get_variable_name(target)}"
            # Temporarily collect definition IDs to link to operation
            def_ids_before = [d.id for d in self.facts.definitions]
            self._extract_target_definitions(target, node, 'assignment', binding_key)
            new_def_ids = [d.id for d in self.facts.definitions if d.id not in def_ids_before]
            
            # Link the last operation to these new definitions
            if last_op_id:
                for op in self.facts.operations:
                    if op.id == last_op_id:
                        op.output_definition_ids.extend(new_def_ids)
                        break

        # Do NOT call generic_visit(node) - would duplicate RHS visit

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Visit annotated assignment statements."""
        # Extract uses from RHS
        if node.value:
            self.visit(node.value)

        # Extract definition from target
        if node.target:
            binding_key = f"{self.function_id}::{self._get_variable_name(node.target)}"
            self._extract_target_definitions(node.target, node, 'annotated_assignment', binding_key)

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

        # Extract uses from RHS
        self.visit(node.value)

        # Extract definition from target
        binding_key = f"{self.function_id}::{self._get_variable_name(node.target)}"
        self._extract_target_definitions(node.target, node, 'augmented_assignment', binding_key, cfg_node_ids)

        # Do NOT call generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Visit for loops."""
        # Extract uses from iterable
        self.visit(node.iter)

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
        # Extract uses from context managers
        for item in node.items:
            self.visit(item.context_expr)

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
        # Extract uses from value
        self.visit(node.value)

        # Target is a definition
        binding_key = f"{self.function_id}::{self._get_variable_name(node.target)}"
        self._extract_target_definitions(node.target, node, 'named_expression', binding_key)

    def visit_Return(self, node: ast.Return) -> None:
        """Visit return statements."""
        if node.value:
            self.visit(node.value)

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

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Visit binary operations (a + b, etc.)."""
        # Visit left and right operands first to create use nodes
        self.visit(node.left)
        self.visit(node.right)

        # Collect use IDs for operands
        input_use_ids = []
        for operand in [node.left, node.right]:
            if isinstance(operand, ast.Name):
                binding_key = f"{self.function_id}::{operand.id}"
                use_id = self._generate_use_id(operand.id)
                # Find if we already created this use
                for use in self.facts.uses:
                    if use.variable == operand.id and use.line == operand.lineno:
                        input_use_ids.append(use.id)
                        break

        # Create operation fact
        op_type = type(node.op).__name__
        op_id = self._generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else str(op_type)
        cfg_node_ids = self._get_cfg_node_ids(node)

        from .models import ExpressionFact
        self.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.function_id,
            file=self.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation=op_type,
            input_use_ids=input_use_ids,
            output_definition_ids=[],  # Will be filled when we know which definition this produces
            metadata={},
        ))

        # Continue generic visit for nested structures
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        """Visit unary operations (-a, not a, etc.)."""
        # Visit operand first to create use node
        self.visit(node.operand)

        # Collect use ID for operand
        input_use_ids = []
        if isinstance(node.operand, ast.Name):
            binding_key = f"{self.function_id}::{node.operand.id}"
            for use in self.facts.uses:
                if use.variable == node.operand.id and use.line == node.operand.lineno:
                    input_use_ids.append(use.id)
                    break

        # Create operation fact
        op_type = type(node.op).__name__
        op_id = self._generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else str(op_type)
        cfg_node_ids = self._get_cfg_node_ids(node)

        from .models import ExpressionFact
        self.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.function_id,
            file=self.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation=op_type,
            input_use_ids=input_use_ids,
            output_definition_ids=[],
            metadata={},
        ))

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit attribute access (obj.attr) with write context tracking."""
        # Visit the object being accessed first
        self.visit(node.value)
        
        # Check if this is in a write context (simplified check)
        is_write = False
        # This is a simplified check - full context tracking would require parent AST info
        
        # Track attribute access as an operation
        op_id = self._generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else f"{ast.unparse(node.value)}.{node.attr}"
        cfg_node_ids = self._get_cfg_node_ids(node)
        
        from .models import ExpressionFact
        self.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.function_id,
            file=self.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation='Attribute',
            input_use_ids=[],
            output_definition_ids=[],
            metadata={
                'attribute': node.attr,
                'access_type': 'write' if is_write else 'read',
                'mutation': is_write,
                'receiver': ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value)
            },
        ))
        # Don't call generic_visit - we already visited node.value

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Visit subscript access (obj[index]) with write context tracking."""
        # Visit the object and index first
        self.visit(node.value)
        self.visit(node.slice)
        
        # Simplified write context check
        is_write = False
        
        op_id = self._generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else "subscript"
        cfg_node_ids = self._get_cfg_node_ids(node)
        
        from .models import ExpressionFact
        self.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.function_id,
            file=self.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation='Subscript',
            input_use_ids=[],
            output_definition_ids=[],
            metadata={
                'access_type': 'write' if is_write else 'read',
                'mutation': is_write,
                'base': ast.unparse(node.value) if hasattr(ast, 'unparse') else str(node.value)
            },
        ))
        
        # Track subscript access as an operation
        op_id = self._generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else f"{ast.unparse(node.value)}[...]"
        cfg_node_ids = self._get_cfg_node_ids(node)
        
        from .models import ExpressionFact
        self.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.function_id,
            file=self.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation='Subscript',
            input_use_ids=[],  # Object and index uses tracked via explicit visit above
            output_definition_ids=[],
            metadata={},
        ))
        # Don't call generic_visit - we already visited node.value and node.slice

    def visit_ListComp(self, node: ast.ListComp) -> None:
        """Visit list comprehensions."""
        # Visit the iterable first
        self.visit(node.elt)
        for generator in node.generators:
            self.visit(generator.iter)
            if generator.ifs:
                for if_test in generator.ifs:
                    self.visit(if_test)
        
        # Comprehension creates a new scope for the loop variable
        # Track the target as a definition in comprehension scope
        if node.generators:
            target = node.generators[0].target
            cfg_node_ids = self._get_cfg_node_ids(node)
            binding_key = f"{self.function_id}::comprehension::{ast.unparse(target)}"
            
            # Extract target definitions (may be a simple name or unpacking)
            self._extract_target_definitions(target, node, binding_key, cfg_node_ids)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        """Visit set comprehensions."""
        self.visit(node.elt)
        for generator in node.generators:
            self.visit(generator.iter)
            if generator.ifs:
                for if_test in generator.ifs:
                    self.visit(if_test)
        
        if node.generators:
            target = node.generators[0].target
            cfg_node_ids = self._get_cfg_node_ids(node)
            binding_key = f"{self.function_id}::comprehension::{ast.unparse(target)}"
            self._extract_target_definitions(target, node, binding_key, cfg_node_ids)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        """Visit dict comprehensions."""
        self.visit(node.key)
        self.visit(node.value)
        for generator in node.generators:
            self.visit(generator.iter)
            if generator.ifs:
                for if_test in generator.ifs:
                    self.visit(if_test)
        
        if node.generators:
            target = node.generators[0].target
            cfg_node_ids = self._get_cfg_node_ids(node)
            binding_key = f"{self.function_id}::comprehension::{ast.unparse(target)}"
            self._extract_target_definitions(target, node, binding_key, cfg_node_ids)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        """Visit generator expressions."""
        self.visit(node.elt)
        for generator in node.generators:
            self.visit(generator.iter)
            if generator.ifs:
                for if_test in generator.ifs:
                    self.visit(if_test)
        
        if node.generators:
            target = node.generators[0].target
            cfg_node_ids = self._get_cfg_node_ids(node)
            binding_key = f"{self.function_id}::comprehension::{ast.unparse(target)}"
            self._extract_target_definitions(target, node, binding_key, cfg_node_ids)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function calls with side-effect tracking."""
        # Visit function and arguments
        self.visit(node.func)
        for arg in node.args:
            self.visit(arg)

        # Collect use IDs for arguments
        input_use_ids = []
        for arg in node.args:
            if isinstance(arg, ast.Name):
                for use in self.facts.uses:
                    if use.variable == arg.id and use.line == arg.lineno:
                        input_use_ids.append(use.id)
                        break

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

        # Create operation fact for the call
        op_id = self._generate_operation_id()
        expression = ast.unparse(node) if hasattr(ast, 'unparse') else "call"
        cfg_node_ids = self._get_cfg_node_ids(node)

        from .models import ExpressionFact
        self.facts.operations.append(ExpressionFact(
            id=op_id,
            function_id=self.function_id,
            file=self.file,
            line=node.lineno,
            column=node.col_offset if hasattr(node, 'col_offset') else 0,
            cfg_node_ids=cfg_node_ids,
            expression=expression,
            operation="Call",
            input_use_ids=input_use_ids,
            output_definition_ids=[],
            metadata=metadata
        ))

        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        """Visit match statements and pattern bindings."""
        # Visit the subject expression
        self.visit(node.subject)
        
        # Visit each case and its pattern
        for case in node.cases:
            self.visit(case.pattern)
            if case.guard:
                self.visit(case.guard)
            self.visit(case.body)

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
