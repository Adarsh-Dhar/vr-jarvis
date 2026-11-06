"""Python definition/use extractor for data-flow analysis."""
import ast
import symtable
from typing import List, Dict, Any, Optional, Set
from .models import Definition, VariableUse, DefUseFacts


class PythonDefUseExtractor:
    """Extract definition and use facts from Python AST."""

    def extract_function(
        self,
        function_ast: ast.FunctionDef,
        function_id: str,
        source: str,
        cfg,
        file_path: str
    ) -> DefUseFacts:
        """Extract definition/use facts for a function."""
        file_path = function_id.split('::')[0] if '::' in function_id else 'unknown'

        facts = DefUseFacts(
            function_id=function_id,
            file=file_path,
        )

        # Get binding key from function
        binding_key = function_id

        # Track CFG node ID mapping
        if cfg and hasattr(cfg, 'ast_node_map'):
            self.cfg_node_map = cfg.ast_node_map
        else:
            self.cfg_node_map = {}

        # Build symbol table to get scope information
        try:
            sym_table = symtable.symtable(source, file_path, 'exec')
            func_sym = self._find_function_symbol(sym_table, function_ast.name)
            local_vars = self._get_local_variables(func_sym) if func_sym else set()
        except Exception:
            # Fallback if symbol table fails
            local_vars = set()

        # Extract parameters as definitions
        param_cfg_node_id = cfg.entry_node_id if cfg else ""
        param_defs = self._extract_parameters(function_ast, function_id, file_path, binding_key, param_cfg_node_id)
        facts.definitions.extend(param_defs)

        # Track CFG node ID mapping (simplified for now)
        # In a full implementation, we'd map each statement to its CFG node
        cfg_node_map = {}

        # Walk the AST to extract definitions and uses
        visitor = DefUseVisitor(
            function_id=function_id,
            file=file_path,
            local_vars=local_vars,
            cfg_node_map=cfg_node_map,
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
        binding_key: str,
        cfg_node_id: str = ""
    ) -> List[Definition]:
        """Extract function parameters as definitions."""
        definitions = []
        args = function_ast.args

        # Positional-only args
        for arg in args.posonlyargs:
            definitions.append(Definition(
                id=f"{function_id}_param_{arg.arg}",
                variable=arg.arg,
                function_id=function_id,
                file=file_path,
                line=function_ast.lineno,
                column=arg.col_offset if hasattr(arg, 'col_offset') else 0,
                kind='parameter',
                cfg_node_id=cfg_node_id,
                binding_key=binding_key,
                expression=None,
            ))

        # Regular args
        for arg in args.args:
            definitions.append(Definition(
                id=f"{function_id}_param_{arg.arg}",
                variable=arg.arg,
                function_id=function_id,
                file=file_path,
                line=function_ast.lineno,
                column=arg.col_offset if hasattr(arg, 'col_offset') else 0,
                kind='parameter',
                cfg_node_id=cfg_node_id,
                binding_key=binding_key,
                expression=None,
            ))

        if args.vararg:
            definitions.append(Definition(
                id=f"{function_id}_param_{args.vararg.arg}",
                variable=args.vararg.arg,
                function_id=function_id,
                file=file_path,
                line=function_ast.lineno,
                column=args.vararg.col_offset if hasattr(args.vararg, 'col_offset') else 0,
                kind='parameter',
                cfg_node_id=cfg_node_id,
                binding_key=binding_key,
                expression=None,
            ))

        for arg in args.kwonlyargs:
            definitions.append(Definition(
                id=f"{function_id}_param_{arg.arg}",
                variable=arg.arg,
                function_id=function_id,
                file=file_path,
                line=function_ast.lineno,
                column=arg.col_offset if hasattr(arg, 'col_offset') else 0,
                kind='parameter',
                cfg_node_id=cfg_node_id,
                binding_key=binding_key,
                expression=None,
            ))

        if args.kwarg:
            definitions.append(Definition(
                id=f"{function_id}_param_{args.kwarg.arg}",
                variable=args.kwarg.arg,
                function_id=function_id,
                file=file_path,
                line=function_ast.lineno,
                column=args.kwarg.col_offset if hasattr(args.kwarg, 'col_offset') else 0,
                kind='parameter',
                cfg_node_id=cfg_node_id,
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
        facts: DefUseFacts,
    ):
        self.function_id = function_id
        self.file = file
        self.local_vars = local_vars
        self.cfg_node_map = cfg_node_map
        self.facts = facts
        self._definition_counter = 0
        self._use_counter = 0

    def _generate_def_id(self, variable: str) -> str:
        """Generate a unique definition ID."""
        self._definition_counter += 1
        return f"{self.function_id}_def_{variable}_{self._definition_counter}"

    def _generate_use_id(self, variable: str) -> str:
        """Generate a unique use ID."""
        self._use_counter += 1
        return f"{self.function_id}_use_{variable}_{self._use_counter}"

    def _get_cfg_node_id(self, node: ast.AST) -> str:
        """Get the CFG node ID for an AST node."""
        # Simplified: use line number as proxy
        line = getattr(node, 'lineno', 0)
        return f"{self.function_id}_line_{line}"

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignment statements."""
        # Extract uses from RHS
        self.visit(node.value)

        # Extract definitions from targets
        binding_key = self.function_id
        for target in node.targets:
            self._extract_target_definitions(target, node, 'assignment', binding_key)

        # Do NOT call generic_visit(node) - would duplicate RHS visit

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Visit annotated assignment statements."""
        binding_key = self.function_id

        # Extract uses from RHS
        if node.value:
            self.visit(node.value)

        # Extract definition from target
        if node.target:
            self._extract_target_definitions(node.target, node, 'annotated_assignment', binding_key)

        # Do NOT call generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Visit augmented assignment statements (+=, -=, etc.)."""
        binding_key = self.function_id

        # Target is both used and defined
        if isinstance(node.target, ast.Name):
            # Use
            self.facts.uses.append(VariableUse(
                id=self._generate_use_id(node.target.id),
                variable=node.target.id,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=node.target.col_offset if hasattr(node.target, 'col_offset') else 0,
                cfg_node_id=self._get_cfg_node_id(node),
                binding_key=binding_key,
                expression=ast.unparse(node.target) if hasattr(ast, 'unparse') else node.target.id,
            ))

        # Extract uses from RHS
        self.visit(node.value)

        # Extract definition from target
        self._extract_target_definitions(node.target, node, 'augmented_assignment', binding_key)

        # Do NOT call generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Visit for loops."""
        # Extract uses from iterable
        self.visit(node.iter)

        # Loop variable is a definition
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
                self._extract_target_definitions(item.optional_vars, node, 'with_binding', binding_key)

        # Visit body
        for stmt in node.body:
            self.visit(stmt)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Visit exception handlers."""
        # Exception name is a definition if present
        if node.name:
            self.facts.definitions.append(Definition(
                id=self._generate_def_id(node.name),
                variable=node.name,
                function_id=self.function_id,
                file=self.file,
                line=node.lineno,
                column=node.col_offset if hasattr(node, 'col_offset') else 0,
                kind='exception_handler',
                cfg_node_id=self._get_cfg_node_id(node),
                expression=None,
            ))

        # Visit body
        for stmt in node.body:
            self.visit(stmt)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        """Visit named expressions (walrus operator :=)."""
        binding_key = self.function_id

        # Extract uses from value
        self.visit(node.value)

        # Target is a definition
        self._extract_target_definitions(node.target, node, 'named_expression', binding_key)

    def visit_Return(self, node: ast.Return) -> None:
        """Visit return statements."""
        if node.value:
            self.visit(node.value)

    def visit_Name(self, node: ast.Name) -> None:
        """Visit name nodes."""
        binding_key = self.function_id

        if isinstance(node.ctx, ast.Load):
            # Variable use
            # Only track if it's a local variable (not an attribute access like self.x)
            if node.id in self.local_vars or not self.local_vars:
                self.facts.uses.append(VariableUse(
                    id=self._generate_use_id(node.id),
                    variable=node.id,
                    function_id=self.function_id,
                    file=self.file,
                    line=node.lineno,
                    column=node.col_offset if hasattr(node, 'col_offset') else 0,
                    cfg_node_id=self._get_cfg_node_id(node),
                    binding_key=binding_key,
                    expression=ast.unparse(node) if hasattr(ast, 'unparse') else node.id,
                ))

    def _extract_target_definitions(
        self,
        target: ast.AST,
        source_node: ast.AST,
        kind: str,
        binding_key: str
    ) -> None:
        """Extract definitions from assignment targets."""
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
                cfg_node_id=self._get_cfg_node_id(source_node),
                binding_key=binding_key,
                expression=ast.unparse(source_node) if hasattr(ast, 'unparse') else None,
            ))
        elif isinstance(target, (ast.Tuple, ast.List)):
            # Tuple/list unpacking: `a, b = value`
            for elt in target.elts:
                self._extract_target_definitions(elt, source_node, f"{kind}_unpack", binding_key)
        elif isinstance(target, ast.Starred):
            # Starred unpacking: `*rest = value`
            self._extract_target_definitions(target.value, source_node, f"{kind}_starred", binding_key)
        elif isinstance(target, ast.Attribute):
            # Attribute assignment: `self.x = value`
            # For now, we don't track attribute definitions as local variables
            # This would require alias analysis
            pass
