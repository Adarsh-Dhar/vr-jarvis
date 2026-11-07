"""Recursive Python CFG builder with full control-flow support - FlowResult-based implementation."""
import ast
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from .models import CFGNode, CFGEdge, ControlFlowGraph, CFGBuildArtifact
from .ast_cfg_index import ASTCFGIndex
from .exception_classifier import ExceptionEffectClassifier


@dataclass
class Completion:
    """Represents an abrupt completion (return, raise, break, continue, yield)."""
    node_id: str
    kind: str  # 'return', 'raise', 'break', 'continue', 'yield'
    target_loop_id: Optional[str] = None  # For break/continue: which loop
    exception_type: Optional[str] = None  # For raise: exception type
    intended_target: Optional[str] = None  # Where this completion should resume
    source_metadata: Optional[Dict[str, Any]] = None  # Source location, etc.
    completion_id: Optional[str] = None  # Unique ID for tracking through finally


@dataclass
class FlowResult:
    """Result of processing a statement or suite."""
    entry_nodes: List[str] = field(default_factory=list)
    normal_exits: List[str] = field(default_factory=list)
    abrupt_exits: List[Completion] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


class BuildContext:
    """Context for CFG construction, tracking loops and control structures."""

    def __init__(self, function_id: str, file: str):
        self.function_id = function_id
        self.file = file
        self.node_counter = 0
        self.edge_counter = 0
        self.completion_counter = 0
        self.loop_stack: List[Dict[str, str]] = []
        self.try_stack: List[Dict[str, str]] = []
        self.ast_node_map: Dict[int, str] = {}
        self.ast_index = ASTCFGIndex()
        self.diagnostics: List[Dict[str, Any]] = []
        self.exception_classifier = ExceptionEffectClassifier()
        # Track lexical nesting depth for proper finalizer execution
        self.loop_depth = 0
        self.try_depth = 0

    def generate_node_id(self) -> str:
        node_id = f"{self.function_id}_N{self.node_counter}"
        self.node_counter += 1
        return node_id

    def generate_edge_id(self) -> str:
        edge_id = f"{self.function_id}_E{self.edge_counter}"
        self.edge_counter += 1
        return edge_id

    def generate_completion_id(self) -> str:
        completion_id = f"{self.function_id}_C{self.completion_counter}"
        self.completion_counter += 1
        return completion_id

    def add_diagnostic(self, code: str, line: int, message: str = "", severity: str = "warning"):
        self.diagnostics.append({'code': code, 'line': line, 'message': message, 'severity': severity})

    def push_loop(self, header_id: str, break_target: str, continue_target: str):
        self.loop_stack.append({'header': header_id, 'break_target': break_target, 'continue_target': continue_target, 'depth': self.loop_depth})
        self.loop_depth += 1

    def pop_loop(self) -> Optional[Dict[str, str]]:
        if self.loop_stack:
            self.loop_depth -= 1
        return self.loop_stack.pop() if self.loop_stack else None

    def current_loop(self) -> Optional[Dict[str, str]]:
        return self.loop_stack[-1] if self.loop_stack else None

    def push_try(self, try_body_id: str, finally_nodes: Optional[Dict[str, str]] = None, exception_dispatch: Optional[str] = None):
        self.try_stack.append({'try_body': try_body_id, 'finally': finally_nodes, 'exception_dispatch': exception_dispatch, 'original_completions': [], 'depth': self.try_depth})
        self.try_depth += 1

    def pop_try(self) -> Optional[Dict[str, str]]:
        if self.try_stack:
            self.try_depth -= 1
        return self.try_stack.pop() if self.try_stack else None

    def current_try(self) -> Optional[Dict[str, str]]:
        return self.try_stack[-1] if self.try_stack else None

    def add_abrupt_completion(self, completion: Completion):
        """Store an abrupt completion to be routed through finally if needed."""
        try_ctx = self.current_try()
        if try_ctx and try_ctx['finally']:
            try_ctx['original_completions'].append(completion)


class PythonCFGBuilder:
    """Build control-flow graphs from Python AST using FlowResult interface."""

    def build_function(
        self,
        function_ast,
        function_id: str,
        source: str,
        file_path: str
    ) -> CFGBuildArtifact:
        cfg = ControlFlowGraph(function_id=function_id, file=file_path)
        ctx = BuildContext(function_id, file_path)

        # Determine if this is an async function
        is_async = isinstance(function_ast, ast.AsyncFunctionDef)
        ast_kind = 'AsyncFunctionDef' if is_async else 'FunctionDef'

        # Entry node
        entry_id = ctx.generate_node_id()
        entry_node = CFGNode(
            id=entry_id, kind='entry', label='entry',
            function_id=function_id, file=file_path,
            start_line=function_ast.lineno, end_line=function_ast.lineno,
            ast_kind=ast_kind,
            metadata={'is_async': is_async} if is_async else {}
        )
        cfg.add_node(entry_node)
        cfg.entry_node_id = entry_id
        ctx.ast_node_map[id(function_ast)] = entry_id
        ctx.ast_index.bind(function_ast, entry_id, "function_entry")

        # Create exit nodes BEFORE building body so completions have valid targets
        # Normal exit node
        exit_id = ctx.generate_node_id()
        exit_node = CFGNode(
            id=exit_id, kind='exit', label='exit',
            function_id=function_id, file=file_path,
            start_line=function_ast.end_lineno or function_ast.lineno,
            end_line=function_ast.end_lineno or function_ast.lineno,
            ast_kind=ast_kind,
            metadata={'is_async': is_async} if is_async else {}
        )
        cfg.add_node(exit_node)
        cfg.exit_node_id = exit_id

        # Exception exit node
        exception_exit_id = ctx.generate_node_id()
        exception_exit_node = CFGNode(
            id=exception_exit_id, kind='exception_exit', label='exception_exit',
            function_id=function_id, file=file_path,
            start_line=function_ast.end_lineno or function_ast.lineno,
            end_line=function_ast.end_lineno or function_ast.lineno,
            ast_kind=ast_kind,
            metadata={'is_async': is_async} if is_async else {}
        )
        cfg.add_node(exception_exit_node)
        cfg.exception_exit_node_id = exception_exit_id

        # Build body (now completions can reference valid exit node IDs)
        result = self._build_suite(function_ast.body, cfg, ctx)

        # Handle empty functions (no body statements)
        if not result.entry_nodes and not result.normal_exits:
            # No body: connect entry directly to exit
            self._add_edge(cfg, ctx, entry_id, exit_id, 'next')
        else:
            # Connect entry to first statement
            if result.entry_nodes:
                self._add_edge(cfg, ctx, entry_id, result.entry_nodes[0], 'next')

            # Connect normal exits to exit node
            for normal_exit in result.normal_exits:
                self._add_edge(cfg, ctx, normal_exit, exit_id, 'next')

        # Connect abrupt completions to their intended targets
        # Only add edges for completions that don't already have edges through finally routing
        for completion in result.abrupt_exits:
            # Check if this completion already has outgoing edges (added by its builder)
            existing_edges = cfg.get_edges_from(completion.node_id)
            if existing_edges:
                # Already has edges (likely through finally routing), skip
                continue

            if completion.kind == 'return':
                if completion.intended_target:
                    self._add_edge(cfg, ctx, completion.node_id, completion.intended_target, 'return')
                else:
                    # Fallback if target not set (shouldn't happen with new architecture)
                    self._add_edge(cfg, ctx, completion.node_id, exit_id, 'return')
            elif completion.kind == 'raise':
                if completion.intended_target:
                    self._add_edge(cfg, ctx, completion.node_id, completion.intended_target, 'raise')
                else:
                    # Fallback if target not set
                    self._add_edge(cfg, ctx, completion.node_id, exception_exit_id, 'raise')
            elif completion.kind == 'break':
                if completion.intended_target:
                    self._add_edge(cfg, ctx, completion.node_id, completion.intended_target, 'break')
            elif completion.kind == 'continue':
                if completion.intended_target:
                    self._add_edge(cfg, ctx, completion.node_id, completion.intended_target, 'continue')

        cfg.metadata = {
            'function_name': function_ast.name,
            'parameters': [arg.arg for arg in function_ast.args.args],
            'source_file': file_path,
            'diagnostics': ctx.diagnostics,
        }

        # Store AST node map in CFG for backward compatibility
        cfg.ast_node_map = ctx.ast_node_map

        return CFGBuildArtifact(
            graph=cfg,
            ast_index=ctx.ast_index,
            function_ast=function_ast,
        )

    def _build_suite(self, statements, cfg, ctx) -> FlowResult:
        """Build a suite of statements with sequential reachable-flow construction.

        Only connect a statement if there's a normal continuation from the previous
        statement. Unreachable statements are diagnosed but do not contribute to the
        flow result.
        """
        if not statements:
            return FlowResult(entry_nodes=[], normal_exits=[], abrupt_exits=[])

        # Build the first statement
        first_result = self._build_statement(statements[0], cfg, ctx)
        entry_nodes = first_result.entry_nodes
        current_normal_exits = first_result.normal_exits
        all_abrupt_exits = list(first_result.abrupt_exits)

        # Process remaining statements sequentially
        for stmt in statements[1:]:
            if not current_normal_exits:
                # No normal continuation - statement is unreachable
                ctx.add_diagnostic(
                    "unreachable_statement",
                    stmt.lineno,
                    "Statement unreachable due to abrupt completion",
                    "warning"
                )
                # Build the statement for diagnostics but DON'T add its completions
                # Unreachable statements should not contribute to the reachable flow result
                self._build_statement(stmt, cfg, ctx)
                continue

            # Build the next statement
            next_result = self._build_statement(stmt, cfg, ctx)

            # Connect current normal exits to next entry nodes
            if next_result.entry_nodes:
                self._connect(cfg, ctx, current_normal_exits, next_result.entry_nodes, kind="next")

            # Update current state
            current_normal_exits = next_result.normal_exits
            all_abrupt_exits.extend(next_result.abrupt_exits)

        return FlowResult(
            entry_nodes=entry_nodes,
            normal_exits=current_normal_exits,
            abrupt_exits=all_abrupt_exits
        )

    def _build_statement(self, statement, cfg, ctx) -> FlowResult:
        if isinstance(statement, ast.If):
            return self._build_if(statement, cfg, ctx)
        elif isinstance(statement, ast.For):
            return self._build_for(statement, cfg, ctx)
        elif isinstance(statement, ast.While):
            return self._build_while(statement, cfg, ctx)
        elif isinstance(statement, ast.Try):
            return self._build_try(statement, cfg, ctx)
        elif isinstance(statement, ast.With):
            return self._build_with(statement, cfg, ctx)
        elif isinstance(statement, ast.Match):
            return self._build_match(statement, cfg, ctx)
        elif isinstance(statement, ast.Return):
            return self._build_return(statement, cfg, ctx)
        elif isinstance(statement, ast.Raise):
            return self._build_raise(statement, cfg, ctx)
        elif isinstance(statement, ast.Break):
            return self._build_break(statement, cfg, ctx)
        elif isinstance(statement, ast.Continue):
            return self._build_continue(statement, cfg, ctx)
        elif isinstance(statement, ast.Assert):
            return self._build_assert(statement, cfg, ctx)
        elif isinstance(statement, ast.TryStar):
            # TryStar (except*) is not fully supported - add diagnostic
            ctx.add_diagnostic(
                "unsupported_construct",
                statement.lineno,
                "TryStar (except*) exception groups are not fully supported",
                "warning"
            )
            # Treat as regular try for now
            return self._build_try(statement, cfg, ctx)
        elif isinstance(statement, (ast.Global, ast.Nonlocal)):
            # Global and nonlocal declarations are simple statements
            return self._build_simple_statement(statement, cfg, ctx)
        elif isinstance(statement, (ast.AsyncFor, ast.AsyncWith)):
            # Handle async constructs - for now treat like their sync counterparts
            if isinstance(statement, ast.AsyncFor):
                return self._build_for(statement, cfg, ctx, is_async=True)
            else:
                return self._build_with(statement, cfg, ctx, is_async=True)
        elif isinstance(statement, ast.Yield):
            return self._build_yield(statement, cfg, ctx)
        elif isinstance(statement, ast.YieldFrom):
            return self._build_yield_from(statement, cfg, ctx)
        elif isinstance(statement, ast.Await):
            return self._build_await(statement, cfg, ctx)
        else:
            return self._build_simple_statement(statement, cfg, ctx)

    def _create_statement_node(self, statement, kind, label, cfg, ctx) -> str:
        node_id = ctx.generate_node_id()
        node = CFGNode(
            id=node_id, kind=kind, label=label,
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno,
            end_line=getattr(statement, "end_lineno", statement.lineno),
            ast_kind=type(statement).__name__,
            metadata={
                "ast_span": [
                    statement.lineno, statement.col_offset,
                    getattr(statement, "end_lineno", statement.lineno),
                    getattr(statement, "end_col_offset", 0),
                ],
            },
        )
        cfg.add_node(node)
        # Map the statement AST node to the CFG node
        ctx.ast_node_map[id(statement)] = node_id
        return node_id

    def _connect(self, cfg, ctx, incoming_ids, target_ids, kind="next", condition=None):
        """Connect multiple source nodes to multiple target nodes."""
        if not isinstance(target_ids, list):
            target_ids = [target_ids]
        for source_id in incoming_ids:
            for target_id in target_ids:
                self._add_edge(cfg, ctx, source_id, target_id, kind, condition)

    def _build_simple_statement(self, statement, cfg, ctx) -> FlowResult:
        node_id = self._create_statement_node(
            statement, 'statement',
            ast.unparse(statement) if hasattr(ast, 'unparse') else 'statement',
            cfg, ctx,
        )
        # Bind the statement and its expression tree to the CFG node
        ctx.ast_index.bind(statement, node_id, "statement")
        if hasattr(statement, 'value'):
            ctx.ast_index.bind_expression_tree(statement.value, node_id, "assignment_value")
        # Special handling for augmented assignments
        if isinstance(statement, ast.AugAssign):
            ctx.ast_index.bind(statement.target, node_id, "augmented_target")
            ctx.ast_index.bind_expression_tree(statement.value, node_id, "augmented_value")

        # Check for potential exceptions in the statement's expression
        may_raise_info = self._check_may_raise(statement, ctx)
        if may_raise_info.get('may_raise'):
            # Add may_raise edge to nearest exception region or function exception exit
            exception_target = self._get_exception_target(cfg, ctx)
            if exception_target:
                self._add_edge(cfg, ctx, node_id, exception_target, 'may_raise', condition='implicit_exception')

        return FlowResult(entry_nodes=[node_id], normal_exits=[node_id], abrupt_exits=[])

    def _check_may_raise(self, statement, ctx) -> Dict[str, Any]:
        """Check if a statement may raise an exception."""
        # Check the statement's value expression if it exists
        expr = None
        if hasattr(statement, 'value') and statement.value:
            expr = statement.value
        elif isinstance(statement, ast.Expr) and statement.value:
            expr = statement.value
        if expr is None:
            return {'may_raise': False, 'exception_types': [], 'is_unknown': False}
        effect = ctx.exception_classifier.classify(expr)
        return {
            'may_raise': effect.may_raise,
            'exception_types': effect.exception_types,
            'is_unknown': effect.is_unknown,
        }

    def _get_exception_target(self, cfg, ctx) -> Optional[str]:
        """Get the target for exception edges (nearest exception region or function exit)."""
        # Check if there's an active try context
        try_ctx = ctx.current_try()
        if try_ctx and try_ctx.get('exception_dispatch'):
            return try_ctx['exception_dispatch']
        # Otherwise, use function exception exit
        return cfg.exception_exit_node_id

    def _build_if(self, statement, cfg, ctx) -> FlowResult:
        condition_id = ctx.generate_node_id()
        condition_expr = ast.unparse(statement.test) if hasattr(ast, 'unparse') else 'condition'
        condition_node = CFGNode(
            id=condition_id, kind='condition', label=condition_expr,
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='If', condition=condition_expr,
            metadata={
                "ast_span": [
                    statement.test.lineno, statement.test.col_offset,
                    getattr(statement.test, "end_lineno", statement.test.lineno),
                    getattr(statement.test, "end_col_offset", 0),
                ],
                "condition_ast": statement.test,
                "has_else": bool(statement.orelse)
            },
        )
        cfg.add_node(condition_node)
        ctx.ast_node_map[id(statement.test)] = condition_id
        # Bind expression tree to condition node
        ctx.ast_index.bind_expression_tree(statement.test, condition_id, "condition")

        # Add may_raise edge if condition can raise
        condition_effect = ctx.exception_classifier.classify(statement.test)
        if condition_effect.may_raise:
            exception_target = self._get_exception_target(cfg, ctx)
            self._add_edge(cfg, ctx, condition_id, exception_target, 'may_raise', 'may_raise')

        # Build true branch
        true_result = self._build_suite(statement.body, cfg, ctx)
        # Connect condition to true branch entry nodes
        if true_result.entry_nodes:
            for entry_id in true_result.entry_nodes:
                self._add_edge(cfg, ctx, condition_id, entry_id, "true", "true")

        # Build false branch
        if statement.orelse:
            false_result = self._build_suite(statement.orelse, cfg, ctx)
            # Connect condition to false branch entry nodes
            if false_result.entry_nodes:
                for entry_id in false_result.entry_nodes:
                    self._add_edge(cfg, ctx, condition_id, entry_id, "false", "false")
        else:
            # No else: false edge is a normal continuation
            false_result = FlowResult(entry_nodes=[], normal_exits=[condition_id], abrupt_exits=[])

        # Collect all abrupt completions from both branches
        all_abrupt_exits = true_result.abrupt_exits + false_result.abrupt_exits

        # Determine if there's a normal continuation (at least one branch has normal exits)
        has_normal_continuation = bool(true_result.normal_exits) or bool(false_result.normal_exits)

        if has_normal_continuation:
            # Create join node for branches that complete normally
            join_id = ctx.generate_node_id()
            join_node = CFGNode(
                id=join_id, kind='join', label='join',
                function_id=ctx.function_id, file=ctx.file,
                start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
                ast_kind='If',
            )
            cfg.add_node(join_node)

            # Connect true branch normal exits to join
            for exit_id in true_result.normal_exits:
                self._add_edge(cfg, ctx, exit_id, join_id, 'next')

            # Connect false branch normal exits to join
            for exit_id in false_result.normal_exits:
                self._add_edge(cfg, ctx, exit_id, join_id, 'next')

            # If no else, condition's false path goes directly to join
            if not statement.orelse:
                self._add_edge(cfg, ctx, condition_id, join_id, 'false', 'false')

            normal_exits = [join_id]
        else:
            # Both branches end abruptly (return, raise, break, continue)
            # No normal continuation
            normal_exits = []

        return FlowResult(entry_nodes=[condition_id], normal_exits=normal_exits, abrupt_exits=all_abrupt_exits)

    def _build_for(self, statement, cfg, ctx, is_async=False):
        # For async for, add suspension node before iteration
        if is_async:
            suspension_id = ctx.generate_node_id()
            suspension_node = CFGNode(
                id=suspension_id,
                kind='suspension',
                label='await iter',
                function_id=ctx.function_id,
                file=ctx.file,
                start_line=statement.lineno,
                end_line=statement.lineno,
                ast_kind='AsyncFor',
                metadata={'suspension_point': 'async_iteration'}
            )
            cfg.add_node(suspension_node)
            ctx.ast_node_map[id(statement)] = suspension_id
            ctx.ast_index.bind(statement, suspension_id, "async_for")
            entry_nodes = [suspension_id]
        else:
            entry_nodes = []

        header_id = ctx.generate_node_id()
        header_node = CFGNode(
            id=header_id, kind='loop_header', label='for loop',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='AsyncFor' if is_async else 'For',
        )
        cfg.add_node(header_node)
        ctx.ast_node_map[id(statement)] = header_id
        ctx.ast_index.bind(statement, header_id, "for_loop")
        # Bind iterator expression to header
        if statement.iter:
            ctx.ast_index.bind_expression_tree(statement.iter, header_id, "for_iterator")
        # Bind target to header
        if statement.target:
            ctx.ast_index.bind(statement.target, header_id, "for_target")

        # For async, connect suspension to header
        if is_async:
            self._add_edge(cfg, ctx, suspension_id, header_id, 'resume')
            entry_nodes.append(header_id)
        else:
            entry_nodes.append(header_id)

        # Loop context nodes
        loop_exit_id = ctx.generate_node_id()
        loop_exit_node = CFGNode(
            id=loop_exit_id, kind='join', label='loop exit',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='For',
        )
        cfg.add_node(loop_exit_node)

        # Push loop context BEFORE building else suite or body
        # so break/continue in the else suite or body can resolve correctly
        # break_target should bypass the else suite (natural exhaustion path)
        post_loop_id = ctx.generate_node_id()
        post_loop_node = CFGNode(
            id=post_loop_id, kind='join', label='post loop',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='For',
            metadata={'loop_id': header_id, 'is_post_loop': True}
        )
        cfg.add_node(post_loop_node)

        # Add loop metadata to header for validation
        header_node.metadata = {
            'loop_id': header_id,
            'break_target': post_loop_id,
            'continue_target': header_id,
            'is_for_loop': True
        }

        ctx.push_loop(header_id, post_loop_id, header_id)

        # Build loop body
        body_result = self._build_suite(statement.body, cfg, ctx)
        if body_result.entry_nodes:
            self._connect(cfg, ctx, [header_id], body_result.entry_nodes, kind="next")

        # Connect body exits back to header (loop back)
        for exit_id in body_result.normal_exits:
            self._add_edge(cfg, ctx, exit_id, header_id, 'loop_back')

        # Add loop_exhausted edge from header to loop_exit (natural exhaustion)
        self._add_edge(cfg, ctx, header_id, loop_exit_id, 'loop_exhausted')

        # Pop the loop context BEFORE building the else suite:
        # break/continue inside a loop's else suite belongs to the ENCLOSING loop,
        # not the loop whose else is executing.
        ctx.pop_loop()

        # Loop else (executes on natural exhaustion only, not on break)
        if statement.orelse:
            else_result = self._build_suite(statement.orelse, cfg, ctx)
            else_join_id = ctx.generate_node_id()
            else_join_node = CFGNode(
                id=else_join_id, kind='join', label='else join',
                function_id=ctx.function_id, file=ctx.file,
                start_line=statement.orelse[0].lineno,
                end_line=statement.orelse[-1].end_lineno or statement.orelse[0].lineno,
                ast_kind='For',
            )
            cfg.add_node(else_join_node)
            # Connect natural exhaustion to else entry
            if else_result.entry_nodes:
                self._connect(cfg, ctx, [loop_exit_id], else_result.entry_nodes, kind="next")
            # Connect else exits to post-loop only if else has normal exits
            if else_result.normal_exits:
                for exit_id in else_result.normal_exits:
                    self._add_edge(cfg, ctx, exit_id, post_loop_id, 'next')
                post_loop_exits = [post_loop_id]
            else:
                # Else suite ended abruptly (return, raise, break, continue)
                post_loop_exits = []
            # Abrupt exits from else branch
            all_abrupt_exits = body_result.abrupt_exits + else_result.abrupt_exits
        else:
            # No else: loop_exit goes directly to post_loop
            self._add_edge(cfg, ctx, loop_exit_id, post_loop_id, 'next')
            post_loop_exits = [post_loop_id]
            all_abrupt_exits = body_result.abrupt_exits

        return FlowResult(entry_nodes=entry_nodes, normal_exits=post_loop_exits, abrupt_exits=all_abrupt_exits)

    def _build_while(self, statement, cfg, ctx) -> FlowResult:
        header_id = ctx.generate_node_id()
        condition_expr = ast.unparse(statement.test) if hasattr(ast, 'unparse') else 'condition'
        header_node = CFGNode(
            id=header_id, kind='loop_header', label=condition_expr,
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='While', condition=condition_expr,
            metadata={
                "ast_span": [
                    statement.test.lineno, statement.test.col_offset,
                    getattr(statement.test, "end_lineno", statement.test.lineno),
                    getattr(statement.test, "end_col_offset", 0),
                ],
            },
        )
        cfg.add_node(header_node)
        ctx.ast_node_map[id(statement)] = header_id
        ctx.ast_index.bind(statement, header_id, "while_loop")
        # Bind expression tree to header node
        ctx.ast_index.bind_expression_tree(statement.test, header_id, "condition")

        # Add may_raise edge if condition can raise
        condition_effect = ctx.exception_classifier.classify(statement.test)
        if condition_effect.may_raise:
            exception_target = self._get_exception_target(cfg, ctx)
            self._add_edge(cfg, ctx, header_id, exception_target, 'may_raise', 'may_raise')

        # Node where loop naturally exits (condition false)
        loop_exit_id = ctx.generate_node_id()
        loop_exit_node = CFGNode(
            id=loop_exit_id, kind='join', label='loop exit',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='While',
        )
        cfg.add_node(loop_exit_node)

        # Node after the loop (where break should go, bypassing else)
        post_loop_id = ctx.generate_node_id()
        post_loop_node = CFGNode(
            id=post_loop_id, kind='join', label='post loop',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='While',
        )
        cfg.add_node(post_loop_node)

        # Add loop metadata to header for validation
        header_node.metadata = {
            'loop_id': header_id,
            'break_target': post_loop_id,
            'continue_target': header_id,
            'is_while_loop': True,
            'condition': condition_expr
        }

        # Push loop context with break target = post_loop (bypasses else)
        ctx.push_loop(header_id, post_loop_id, header_id)

        body_result = self._build_suite(statement.body, cfg, ctx)
        # Connect header to body entry nodes
        if body_result.entry_nodes:
            for entry_id in body_result.entry_nodes:
                self._add_edge(cfg, ctx, header_id, entry_id, 'next', 'true')
        for body_exit in body_result.normal_exits:
            self._add_edge(cfg, ctx, body_exit, header_id, 'loop_back')

        # Natural loop exit (condition false) goes to loop_exit
        self._add_edge(cfg, ctx, header_id, loop_exit_id, 'loop_exhausted', 'false')

        # Pop the loop context BEFORE building the else suite:
        # break/continue inside a loop's else suite belongs to the ENCLOSING loop.
        ctx.pop_loop()

        # Connect loop_exit to post_loop (unless there's an else block)
        if statement.orelse:
            # Else block is between loop_exit and post_loop
            else_result = self._build_suite(statement.orelse, cfg, ctx)
            # Connect loop_exit to else entry nodes
            if else_result.entry_nodes:
                for entry_id in else_result.entry_nodes:
                    self._add_edge(cfg, ctx, loop_exit_id, entry_id, 'next')
            # Connect else normal exits to post_loop
            for else_exit in else_result.normal_exits:
                self._add_edge(cfg, ctx, else_exit, post_loop_id, 'next')
            # Final exit is post_loop if else completes normally, else it's determined by else's abrupt exits
            if else_result.normal_exits:
                final_exit = [post_loop_id]
            else:
                # Else suite ended abruptly (return, raise, break, continue)
                final_exit = []
            # Abrupt exits from both body and else
            all_abrupt_exits = body_result.abrupt_exits + else_result.abrupt_exits
        else:
            # No else: loop_exit goes directly to post_loop
            self._add_edge(cfg, ctx, loop_exit_id, post_loop_id, 'next')
            final_exit = [post_loop_id]
            all_abrupt_exits = body_result.abrupt_exits

        abrupt_exits = [c for c in all_abrupt_exits if c.kind not in ('break', 'continue')]
        return FlowResult(entry_nodes=[header_id], normal_exits=final_exit, abrupt_exits=abrupt_exits)

    def _build_return(self, statement, cfg, ctx) -> FlowResult:
        return_id = ctx.generate_node_id()
        return_expr = ast.unparse(statement.value) if statement.value else 'None'
        return_node = CFGNode(
            id=return_id, kind='return', label=f'return {return_expr}',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Return', condition=return_expr,
        )
        cfg.add_node(return_node)
        ctx.ast_node_map[id(statement)] = return_id
        ctx.ast_index.bind(statement, return_id, "return")
        # Bind expression tree to return node
        if statement.value:
            ctx.ast_index.bind_expression_tree(statement.value, return_id, "return_value")

        # Add may_raise edge if return expression can raise
        if statement.value:
            return_effect = ctx.exception_classifier.classify(statement.value)
            if return_effect.may_raise:
                exception_target = self._get_exception_target(cfg, ctx)
                self._add_edge(cfg, ctx, return_id, exception_target, 'may_raise', 'may_raise')

        # Create completion with target (exit_node_id is now guaranteed to exist)
        completion = Completion(
            node_id=return_id,
            kind='return',
            intended_target=cfg.exit_node_id,
            source_metadata={'line': statement.lineno, 'file': ctx.file},
            completion_id=ctx.generate_completion_id()
        )
        # Check if there's a finally block to route through
        try_ctx = ctx.current_try()
        if try_ctx and try_ctx['finally']:
            ctx.add_abrupt_completion(completion)
            # Don't add direct edge - will be added through finally routing
            return FlowResult(entry_nodes=[return_id], normal_exits=[], abrupt_exits=[completion])
        else:
            # Add direct edge only when no finally is present
            self._add_edge(cfg, ctx, return_id, cfg.exit_node_id, 'return')
            return FlowResult(entry_nodes=[return_id], normal_exits=[], abrupt_exits=[completion])

    def _build_raise(self, statement, cfg, ctx) -> FlowResult:
        raise_id = ctx.generate_node_id()
        raise_expr = ast.unparse(statement.exc) if statement.exc else 'exception'
        raise_node = CFGNode(
            id=raise_id, kind='raise', label=f'raise {raise_expr}',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Raise', condition=raise_expr,
            metadata={
                'is_bare_raise': statement.exc is None,
                'has_cause': statement.cause is not None,
                'cause_expr': ast.unparse(statement.cause) if statement.cause else None,
                'suppress_context': statement.cause is not None and isinstance(statement.cause, ast.Constant) and statement.cause.value is None
            }
        )
        cfg.add_node(raise_node)
        ctx.ast_node_map[id(statement)] = raise_id
        ctx.ast_index.bind(statement, raise_id, "raise")
        # Bind expression tree to raise node
        if statement.exc:
            ctx.ast_index.bind_expression_tree(statement.exc, raise_id, "exception")
        if statement.cause:
            ctx.ast_index.bind_expression_tree(statement.cause, raise_id, "exception_cause")

        # Determine target: route through active exception dispatcher if one exists
        try_ctx = ctx.current_try()
        if try_ctx and try_ctx.get('exception_dispatch'):
            # Route through the active exception dispatcher
            intended_target = try_ctx['exception_dispatch']
        else:
            # No active dispatcher: go to function exception exit
            intended_target = cfg.exception_exit_node_id

        # Create completion with target
        completion = Completion(
            node_id=raise_id,
            kind='raise',
            exception_type=raise_expr,
            intended_target=intended_target,
            source_metadata={
                'line': statement.lineno,
                'file': ctx.file,
                'is_bare_raise': statement.exc is None,
                'has_cause': statement.cause is not None,
                'cause': ast.unparse(statement.cause) if statement.cause else None,
                'suppress_context': statement.cause is not None and isinstance(statement.cause, ast.Constant) and statement.cause.value is None
            },
            completion_id=ctx.generate_completion_id()
        )
        # For raise-from, add cause relationship metadata
        if statement.cause:
            completion.source_metadata['cause_expr'] = ast.unparse(statement.cause)
            if isinstance(statement.cause, ast.Constant) and statement.cause.value is None:
                completion.source_metadata['suppress_context'] = True

        # Check if there's a finally block to route through
        if try_ctx and try_ctx['finally']:
            ctx.add_abrupt_completion(completion)
            # Don't add direct edge - will be added through finally routing
            return FlowResult(entry_nodes=[raise_id], normal_exits=[], abrupt_exits=[completion])
        else:
            # Add direct edge to the dispatcher or exception exit
            self._add_edge(cfg, ctx, raise_id, intended_target, 'raise')
            return FlowResult(entry_nodes=[raise_id], normal_exits=[], abrupt_exits=[completion])

    def _build_await(self, statement: ast.Await, cfg, ctx) -> FlowResult:
        """Build CFG for await expressions with suspension node."""
        await_id = ctx.generate_node_id()
        await_node = CFGNode(
            id=await_id,
            kind='suspension',
            label='await',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='Await',
            metadata={'suspension_point': 'await_expression'}
        )
        cfg.add_node(await_node)
        ctx.ast_node_map[id(statement)] = await_id
        ctx.ast_index.bind(statement, await_id, "await")
        if statement.value:
            ctx.ast_index.bind_expression_tree(statement.value, await_id, "await_value")
        
        return FlowResult(entry_nodes=[await_id], normal_exits=[await_id], abrupt_exits=[])

    def _build_break(self, statement: ast.Break, cfg, ctx) -> FlowResult:
        loop_ctx = ctx.current_loop()
        if not loop_ctx:
            ctx.add_diagnostic("break_outside_loop", 0, "Break statement outside loop", "error")
            return FlowResult(entry_nodes=[], normal_exits=[])

        break_id = ctx.generate_node_id()
        break_node = CFGNode(
            id=break_id, kind='statement', label='break',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno, ast_kind='Break',
        )
        cfg.add_node(break_node)
        ctx.ast_node_map[id(statement)] = break_id
        ctx.ast_index.bind(statement, break_id, "break")

        completion = Completion(
            node_id=break_id,
            kind='break',
            target_loop_id=loop_ctx['header'],
            intended_target=loop_ctx['break_target'],
            source_metadata={'line': statement.lineno, 'file': ctx.file},
            completion_id=ctx.generate_completion_id()
        )
        # Check if there's a finally block to route through
        try_ctx = ctx.current_try()
        if try_ctx and try_ctx['finally']:
            ctx.add_abrupt_completion(completion)
            # Don't add direct edge - will be added through finally routing
            return FlowResult(entry_nodes=[break_id], normal_exits=[], abrupt_exits=[completion])
        else:
            # Add direct edge only when no finally is present
            self._add_edge(cfg, ctx, break_id, loop_ctx['break_target'], 'break')
            return FlowResult(entry_nodes=[break_id], normal_exits=[], abrupt_exits=[completion])

    def _build_continue(self, statement: ast.Continue, cfg, ctx) -> FlowResult:
        loop_ctx = ctx.current_loop()
        if not loop_ctx:
            ctx.add_diagnostic("continue_outside_loop", 0, "Continue statement outside loop", "error")
            return FlowResult(entry_nodes=[], normal_exits=[])

        continue_id = ctx.generate_node_id()
        continue_node = CFGNode(
            id=continue_id, kind='statement', label='continue',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno, ast_kind='Continue',
        )
        cfg.add_node(continue_node)
        ctx.ast_node_map[id(statement)] = continue_id
        ctx.ast_index.bind(statement, continue_id, "continue")

        completion = Completion(
            node_id=continue_id,
            kind='continue',
            target_loop_id=loop_ctx['header'],
            intended_target=loop_ctx['continue_target'],
            source_metadata={'line': statement.lineno, 'file': ctx.file},
            completion_id=ctx.generate_completion_id()
        )
        # Check if there's a finally block to route through
        try_ctx = ctx.current_try()
        if try_ctx and try_ctx['finally']:
            ctx.add_abrupt_completion(completion)
            # Don't add direct edge - will be added through finally routing
            return FlowResult(entry_nodes=[continue_id], normal_exits=[], abrupt_exits=[completion])
        else:
            # Add direct edge only when no finally is present
            self._add_edge(cfg, ctx, continue_id, loop_ctx['continue_target'], 'continue')
            return FlowResult(entry_nodes=[continue_id], normal_exits=[], abrupt_exits=[completion])

    def _build_try(self, statement, cfg, ctx) -> FlowResult:
        # Create nodes and establish try context BEFORE building try body
        # This ensures completions from the try body can be associated with the correct exception region

        # Capture parent exception context BEFORE pushing current try context
        # This prevents unmatched exceptions from looping back to their own dispatcher
        parent_try_ctx = ctx.current_try()
        parent_dispatch = parent_try_ctx.get('exception_dispatch') if parent_try_ctx else None

        # Create completion-specific finally nodes if finally exists
        finally_nodes = {}
        if statement.finalbody:
            # Create separate finalizer nodes for each completion type to prevent cross-routing
            for kind in ['normal', 'return', 'raise', 'break', 'continue']:
                finally_id = ctx.generate_node_id()
                finally_node = CFGNode(
                    id=finally_id, kind='finally', label=f'finally ({kind})',
                    function_id=ctx.function_id, file=ctx.file,
                    start_line=statement.finalbody[0].lineno,
                    end_line=statement.finalbody[-1].end_lineno or statement.finalbody[0].lineno,
                    ast_kind='Try',
                    metadata={'completion_kind': kind}
                )
                cfg.add_node(finally_node)
                finally_nodes[kind] = finally_id
            ctx.ast_index.bind(statement, finally_nodes['normal'], "finally")

        # Create exception dispatcher
        dispatch_id = ctx.generate_node_id()
        dispatch_node = CFGNode(
            id=dispatch_id, kind='exception_dispatch', label='exception dispatch',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Try',
        )
        cfg.add_node(dispatch_node)
        ctx.ast_node_map[id(statement)] = dispatch_id
        ctx.ast_index.bind(statement, dispatch_id, "try")

        # Push try context with exception dispatcher for nested handling
        ctx.push_try(None, finally_nodes if finally_nodes else None, dispatch_id)

        # Build try body now that try context is established
        try_result = self._build_suite(statement.body, cfg, ctx)

        # Connect raise completions from try body to dispatcher
        for completion in try_result.abrupt_exits:
            if completion.kind == 'raise':
                self._add_edge(cfg, ctx, completion.node_id, dispatch_id, 'exception')

        handler_join_id = ctx.generate_node_id()
        handler_join_node = CFGNode(
            id=handler_join_id, kind='join', label='handler join',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='Try',
        )
        cfg.add_node(handler_join_node)

        # Build handlers (build each handler once and preserve the result)
        # Handlers are tried in order; first matching handler catches the exception
        handler_results = []
        handler_types = []
        for handler_idx, handler in enumerate(statement.handlers):
            handler_id = ctx.generate_node_id()
            handler_type = ast.unparse(handler.type) if handler.type else 'Exception'
            handler_node = CFGNode(
                id=handler_id, kind='statement', label=f'except {handler_type}',
                function_id=ctx.function_id, file=ctx.file,
                start_line=handler.lineno, end_line=handler.end_lineno or handler.lineno,
                ast_kind='ExceptHandler',
                metadata={
                    'exception_type': handler_type,
                    'is_bare_except': handler.type is None,
                    'handler_order': handler_idx,
                    'exception_variable': handler.name,
                    'is_tuple_type': isinstance(handler.type, ast.Tuple) if handler.type else False,
                    'matched_types': self._extract_exception_types(handler.type) if handler.type else ['*']
                }
            )
            cfg.add_node(handler_node)
            ctx.ast_node_map[id(handler)] = handler_id
            ctx.ast_index.bind(handler, handler_id, "except_handler")
            # Bind exception type expression if present
            if handler.type:
                ctx.ast_index.bind_expression_tree(handler.type, handler_id, "exception_type")

            # Store handler type for matching logic
            handler_types.append({
                'type': handler_type,
                'is_bare': handler.type is None,
                'is_tuple': isinstance(handler.type, ast.Tuple) if handler.type else False,
                'node_id': handler_id,
                'matched_types': handler_node.metadata['matched_types']
            })

            # Edge from dispatcher to handler with ordered matching condition
            # First handler has priority, subsequent handlers only match if previous don't
            condition = f"handler_order_{handler_idx}_not_matched_by_previous"
            self._add_edge(cfg, ctx, dispatch_id, handler_id, 'exception', condition=condition)

            if handler.name:
                ctx.ast_node_map[id(handler)] = handler_id
                # Note: handler.name is a string, the variable binding is handled in DFG extraction
                ctx.ast_index.bind(handler.name, handler_id, "exception_variable")

            handler_result = self._build_suite(handler.body, cfg, ctx)
            handler_results.append(handler_result)
            # Connect handler to handler body entry nodes
            if handler_result.entry_nodes:
                for entry_id in handler_result.entry_nodes:
                    self._add_edge(cfg, ctx, handler_id, entry_id, 'next')
            for handler_exit in handler_result.normal_exits:
                self._add_edge(cfg, ctx, handler_exit, handler_join_id, 'next')

            # Add exception variable clearing node after handler
            # Python clears the exception variable at the end of the except block
            if handler.name:
                clear_id = ctx.generate_node_id()
                clear_node = CFGNode(
                    id=clear_id, kind='statement', label=f'clear {handler.name}',
                    function_id=ctx.function_id, file=ctx.file,
                    start_line=handler.lineno, end_line=handler.end_lineno or handler.lineno,
                    ast_kind='ExceptHandler',
                    metadata={'is_exception_clear': True, 'exception_variable': handler.name}
                )
                cfg.add_node(clear_node)
                # Connect handler exits to clear node, then to join
                for handler_exit in handler_result.normal_exits:
                    self._add_edge(cfg, ctx, handler_exit, clear_id, 'next')
                    self._add_edge(cfg, ctx, clear_id, handler_join_id, 'next')

        # Add edge from dispatcher to parent dispatch or exception exit for unmatched exceptions
        # This represents "no handler matched, propagate to outer scope"
        # The edge should go to the enclosing exception region or function exception exit,
        # NOT to handler_join which would allow normal continuation
        # Use the parent dispatch captured before pushing current try context to prevent self-loop
        unmatched_target = parent_dispatch if parent_dispatch else cfg.exception_exit_node_id
        self._add_edge(cfg, ctx, dispatch_id, unmatched_target, 'exception')

        # Build else suite (only executes on normal completion of try body)
        # Else does NOT execute on raise, return, break, or continue from try body
        if statement.orelse:
            else_result = self._build_suite(statement.orelse, cfg, ctx)
            # Connect try normal exits to else entry nodes (only normal completions)
            if else_result.entry_nodes:
                for entry_id in else_result.entry_nodes:
                    for try_exit in try_result.normal_exits:
                        self._add_edge(cfg, ctx, try_exit, entry_id, 'next')
            # Connect else normal exits to handler join
            for else_exit in else_result.normal_exits:
                self._add_edge(cfg, ctx, else_exit, handler_join_id, 'next')
            # Abrupt exits from else branch need to be preserved
            else_abrupt_exits = else_result.abrupt_exits
        else:
            # No else: connect try normal exits directly to handler join
            for try_exit in try_result.normal_exits:
                self._add_edge(cfg, ctx, try_exit, handler_join_id, 'next')
            else_abrupt_exits = []

        ctx.pop_try()

        # Handle finally routing with completion-specific finalizers
        if statement.finalbody:
            # Build finally body once and reuse for all completion types
            finally_result = self._build_suite(statement.finalbody, cfg, ctx)

            # Connect finally nodes to finally body entry nodes
            for finally_id in finally_nodes.values():
                if finally_result.entry_nodes:
                    for entry_id in finally_result.entry_nodes:
                        self._add_edge(cfg, ctx, finally_id, entry_id, 'next')

            # Route completions through their specific finalizer
            all_abrupt_exits = []

            # Collect all pending completions from try, handlers, and else
            pending_completions = try_result.abrupt_exits + [c for hr in handler_results for c in hr.abrupt_exits] + else_abrupt_exits

            # Route each completion through its specific finalizer
            for completion in pending_completions:
                kind = completion.kind
                if kind in finally_nodes:
                    finally_id = finally_nodes[kind]
                    self._add_edge(cfg, ctx, completion.node_id, finally_id, 'finally')
                    all_abrupt_exits.append(completion)

            # Determine if there are any normal completions from try/handlers/else
            # If not, the entire try statement has no normal exit (even if finally completes normally)
            has_normal_completion = bool(try_result.normal_exits) or any(hr.normal_exits for hr in handler_results)

            # Route normal completions through normal finalizer
            # Use 'next' edge kind to preserve normal completion identity
            if has_normal_completion:
                if handler_join_id in [e.target for e in cfg.edges if e.source in [n.id for n in cfg.nodes if n.kind == 'join']]:
                    # Only connect if there are actual normal flows to handler_join
                    self._add_edge(cfg, ctx, handler_join_id, finally_nodes['normal'], 'next')

                # Connect try normal exits to normal finalizer with 'next' to preserve normal completion
                for try_exit in try_result.normal_exits:
                    self._add_edge(cfg, ctx, try_exit, finally_nodes['normal'], 'next')

            # If finally has abrupt completions, they override the original ones
            if finally_result.abrupt_exits:
                all_abrupt_exits = finally_result.abrupt_exits
            else:
                # If finally completes normally, resume original completions
                if finally_result.normal_exits:
                    # Connect finally exits to the original completion targets
                    for completion in pending_completions:
                        kind = completion.kind
                        if kind in finally_nodes and completion.intended_target:
                            finally_id = finally_nodes[kind]
                            for exit_id in finally_result.normal_exits:
                                self._add_edge(cfg, ctx, exit_id, completion.intended_target, kind)

            # Normal completions after finally go to the next statement
            # Only if there was a normal completion AND finally completes normally
            if has_normal_completion and finally_result.normal_exits:
                final_exit = finally_result.normal_exits
            else:
                # No normal completion or finally ended abruptly, no normal exit
                final_exit = []
        else:
            final_exit = [handler_join_id]
            all_abrupt_exits = try_result.abrupt_exits + [c for hr in handler_results for c in hr.abrupt_exits] + else_abrupt_exits

        return FlowResult(entry_nodes=try_result.entry_nodes, normal_exits=final_exit, abrupt_exits=all_abrupt_exits)

    def _build_with(self, statement, cfg, ctx, is_async=False):
        # For async with, add suspension node for __aenter__
        if is_async:
            enter_suspension_id = ctx.generate_node_id()
            enter_suspension_node = CFGNode(
                id=enter_suspension_id,
                kind='suspension',
                label='await __aenter__',
                function_id=ctx.function_id,
                file=ctx.file,
                start_line=statement.lineno,
                end_line=statement.lineno,
                ast_kind='AsyncWith',
                metadata={'suspension_point': 'async_enter'}
            )
            cfg.add_node(enter_suspension_node)
            ctx.ast_index.bind(statement, enter_suspension_id, "async_with_enter")
            entry_nodes = [enter_suspension_id]
        else:
            entry_nodes = []

        with_id = ctx.generate_node_id()
        with_node = CFGNode(
            id=with_id, kind='statement', label='with',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='AsyncWith' if is_async else 'With',
            metadata={'is_async': is_async}
        )
        cfg.add_node(with_node)
        ctx.ast_node_map[id(statement)] = with_id
        ctx.ast_index.bind(statement, with_id, "with")
        # Bind expression trees to with node
        for item in statement.items:
            ctx.ast_index.bind_expression_tree(item.context_expr, with_id, "context")
            # Add may_raise edge if context expression can raise
            context_effect = ctx.exception_classifier.classify(item.context_expr)
            if context_effect.may_raise:
                exception_target = self._get_exception_target(cfg, ctx)
                self._add_edge(cfg, ctx, with_id, exception_target, 'may_raise', 'may_raise')

        # For async, connect enter suspension to with node
        if is_async:
            self._add_edge(cfg, ctx, enter_suspension_id, with_id, 'resume')
            entry_nodes.append(with_id)
        else:
            entry_nodes.append(with_id)

        body_result = self._build_suite(statement.body, cfg, ctx)

        # Create exit nodes for context manager cleanup (one per completion type)
        exit_nodes = {}
        for kind in ['normal', 'return', 'raise', 'break', 'continue']:
            exit_id = ctx.generate_node_id()
            exit_node = CFGNode(
                id=exit_id, kind='statement', label=f'with exit ({kind})',
                function_id=ctx.function_id, file=ctx.file,
                start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
                ast_kind='With',
                metadata={
                    'is_exit': True,
                    'is_async': is_async,
                    'completion_kind': kind,
                    'may_suppress_exception': kind == 'raise',  # __exit__ can suppress exceptions
                    'exit_method': '__aexit__' if is_async else '__exit__'
                }
            )
            cfg.add_node(exit_node)
            exit_nodes[kind] = exit_id
        ctx.ast_index.bind(statement, exit_nodes['normal'], "with_exit")

        # Connect with node to body entry nodes
        if body_result.entry_nodes:
            for entry_id in body_result.entry_nodes:
                self._add_edge(cfg, ctx, with_id, entry_id, 'next')

        # Connect body normal exits to normal exit node
        for body_exit in body_result.normal_exits:
            self._add_edge(cfg, ctx, body_exit, exit_nodes['normal'], 'next')

        # Route abrupt completions through their specific exit nodes
        # Remove any direct edges that bypass cleanup by not adding them in the first place
        all_abrupt_exits = []
        for completion in body_result.abrupt_exits:
            kind = completion.kind
            if kind in exit_nodes:
                exit_id = exit_nodes[kind]
                self._add_edge(cfg, ctx, completion.node_id, exit_id, 'finally')
                # Do NOT add direct edge to intended_target - must go through cleanup first
                all_abrupt_exits.append(completion)

        # Connect exit nodes to their appropriate destinations after cleanup
        # Normal exit continues to next statement
        # Abrupt exits resume their original completion targets
        for kind, exit_id in exit_nodes.items():
            if kind == 'normal':
                # Normal exit will be handled by the FlowResult
                pass
            else:
                # For abrupt completions, connect exit to the original target AFTER cleanup
                for completion in body_result.abrupt_exits:
                    if completion.kind == kind and completion.intended_target:
                        self._add_edge(cfg, ctx, exit_id, completion.intended_target, kind)

        # Determine if body has normal completions
        # If body ends abruptly (e.g., return), there's no normal exit from the with statement
        has_normal_completion = bool(body_result.normal_exits)

        # Normal exit only if body completed normally
        if has_normal_completion:
            normal_exits = [exit_nodes['normal']]
        else:
            # Body ended abruptly, no normal exit
            normal_exits = []

        return FlowResult(entry_nodes=[with_id], normal_exits=normal_exits, abrupt_exits=all_abrupt_exits)

    def _build_match(self, statement, cfg, ctx) -> FlowResult:
        match_id = ctx.generate_node_id()
        match_node = CFGNode(
            id=match_id, kind='statement', label='match',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Match',
        )
        cfg.add_node(match_node)
        ctx.ast_node_map[id(statement)] = match_id
        ctx.ast_index.bind(statement, match_id, "match")
        # Bind expression tree to match node
        ctx.ast_index.bind_expression_tree(statement.subject, match_id, "match_subject")

        join_id = ctx.generate_node_id()
        join_node = CFGNode(
            id=join_id, kind='join', label='match join',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='Match',
        )
        cfg.add_node(join_node)

        # Track if we have a wildcard pattern (unmatched continuation)
        has_wildcard = False
        all_abrupt_exits = []
        prev_failure_node = match_id  # Start with match as failure point

        # Process cases sequentially, connecting failures to next case
        for i, case in enumerate(statement.cases):
            case_id = ctx.generate_node_id()
            pattern = ast.unparse(case.pattern) if hasattr(ast, 'unparse') else 'pattern'
            
            # Determine pattern kind
            pattern_kind = self._get_pattern_kind(case.pattern)
            
            # Derive line number from pattern since case.lineno doesn't exist
            pattern_line = case.pattern.lineno if hasattr(case.pattern, 'lineno') else statement.lineno
            
            case_node = CFGNode(
                id=case_id, kind='condition', label=pattern,
                function_id=ctx.function_id, file=ctx.file,
                start_line=pattern_line, end_line=pattern_line,
                ast_kind='match_case', condition=pattern,
                metadata={'pattern_kind': pattern_kind}
            )
            cfg.add_node(case_node)
            ctx.ast_node_map[id(case)] = case_id
            ctx.ast_index.bind(case, case_id, "match_case")
            # Bind pattern expression tree
            ctx.ast_index.bind_expression_tree(case.pattern, case_id, "match_pattern")
            if case.guard:
                ctx.ast_index.bind_expression_tree(case.guard, case_id, "match_guard")
            
            # Connect from previous failure point to this case
            self._add_edge(cfg, ctx, prev_failure_node, case_id, 'next')
            
            # Guard evaluation if present
            if case.guard:
                guard_id = ctx.generate_node_id()
                guard_line = case.guard.lineno if hasattr(case.guard, 'lineno') else pattern_line
                guard_node = CFGNode(
                    id=guard_id, kind='condition', label='guard',
                    function_id=ctx.function_id, file=ctx.file,
                    start_line=guard_line, end_line=guard_line,
                    ast_kind='match_guard',
                )
                cfg.add_node(guard_node)
                ctx.ast_index.bind(case.guard, guard_id, "guard")
                self._add_edge(cfg, ctx, case_id, guard_id, 'next')

                # Add may_raise edge if guard can raise
                guard_effect = ctx.exception_classifier.classify(case.guard)
                if guard_effect.may_raise:
                    exception_target = self._get_exception_target(cfg, ctx)
                    self._add_edge(cfg, ctx, guard_id, exception_target, 'may_raise', 'may_raise')

                # Guard true -> case body
                case_result = self._build_suite(case.body, cfg, ctx)
                if case_result.entry_nodes:
                    for entry_id in case_result.entry_nodes:
                        self._add_edge(cfg, ctx, guard_id, entry_id, 'true')
                for case_exit in case_result.normal_exits:
                    self._add_edge(cfg, ctx, case_exit, join_id, 'next')
                all_abrupt_exits.extend(case_result.abrupt_exits)
                
                # Guard false -> next case or join
                if i < len(statement.cases) - 1:
                    # Connect to next case (update prev_failure_node for next iteration)
                    prev_failure_node = guard_id
                else:
                    # Last case, guard false -> join
                    self._add_edge(cfg, ctx, guard_id, join_id, 'false')
            else:
                # No guard, pattern match -> case body
                case_result = self._build_suite(case.body, cfg, ctx)
                if case_result.entry_nodes:
                    for entry_id in case_result.entry_nodes:
                        self._add_edge(cfg, ctx, case_id, entry_id, 'true')
                for case_exit in case_result.normal_exits:
                    self._add_edge(cfg, ctx, case_exit, join_id, 'next')
                all_abrupt_exits.extend(case_result.abrupt_exits)
                
                # Pattern failure -> next case or join (explicit false edge for pattern failure)
                if i < len(statement.cases) - 1:
                    # Connect to next case (update prev_failure_node for next iteration)
                    self._add_edge(cfg, ctx, case_id, case_id, 'false')  # Pattern failure edge
                    prev_failure_node = case_id
                else:
                    # Last case, pattern failure -> join
                    self._add_edge(cfg, ctx, case_id, join_id, 'false')

            # Check for wildcard pattern
            if pattern_kind == 'wildcard':
                has_wildcard = True

        # If no wildcard, add explicit unmatched path to join
        # Only add if there are actually case failures that reach this point
        if not has_wildcard and prev_failure_node != match_id:
            # All patterns failed, flow continues to join from last failure point
            self._add_edge(cfg, ctx, prev_failure_node, join_id, 'next')
        elif not has_wildcard and prev_failure_node == match_id and not statement.cases:
            # Empty match statement - no cases at all
            self._add_edge(cfg, ctx, match_id, join_id, 'next')

        # Determine if there's a normal continuation
        # If all cases end abruptly and no wildcard, there's no normal exit
        has_normal_continuation = has_wildcard or any(case.normal_exits for case in [FlowResult(entry_nodes=[], normal_exits=[join_id], abrupt_exits=[])])

        # Check if any case body completed normally (has normal exits to join)
        any_case_normal = False
        for case in statement.cases:
            # We need to track this during case processing - simplified check
            pass

        # For now, assume join is reachable if we have cases or wildcard
        normal_exits = [join_id] if (has_wildcard or statement.cases) else []

        return FlowResult(entry_nodes=[match_id], normal_exits=normal_exits, abrupt_exits=all_abrupt_exits)

    def _get_pattern_kind(self, pattern):
        """Determine the kind of pattern for semantic labeling."""
        if isinstance(pattern, ast.MatchValue):
            return 'literal'
        elif isinstance(pattern, ast.MatchSingleton):
            return 'singleton'
        elif isinstance(pattern, ast.MatchSequence):
            return 'sequence'
        elif isinstance(pattern, ast.MatchMapping):
            return 'mapping'
        elif isinstance(pattern, ast.MatchClass):
            return 'class'
        elif isinstance(pattern, ast.MatchStar):
            return 'star'
        elif isinstance(pattern, ast.MatchAs):
            if pattern.pattern is None:
                return 'wildcard'
            return 'capture'
        elif isinstance(pattern, ast.MatchOr):
            return 'or'
        else:
            return 'unknown'

    def _extract_exception_types(self, type_node) -> List[str]:
        """Extract exception types from handler type expression."""
        if type_node is None:
            return ['*']  # Bare except matches all
        elif isinstance(type_node, ast.Tuple):
            # Tuple of exception types: except (ValueError, TypeError)
            return [ast.unparse(elt) if hasattr(ast, 'unparse') else str(elt) for elt in type_node.elts]
        else:
            # Single exception type
            return [ast.unparse(type_node) if hasattr(ast, 'unparse') else str(type_node)]

    def _build_assert(self, statement, cfg, ctx) -> FlowResult:
        assert_id = ctx.generate_node_id()
        assert_expr = ast.unparse(statement.test) if hasattr(ast, 'unparse') else 'condition'
        assert_node = CFGNode(
            id=assert_id, kind='condition', label=f'assert {assert_expr}',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Assert', condition=assert_expr,
        )
        cfg.add_node(assert_node)
        ctx.ast_node_map[id(statement)] = assert_id
        ctx.ast_index.bind(statement, assert_id, "assert")
        # Bind expression tree to assert node
        ctx.ast_index.bind_expression_tree(statement.test, assert_id, "assert_condition")

        success_id = ctx.generate_node_id()
        success_node = CFGNode(
            id=success_id, kind='statement', label='assert pass',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Assert',
        )
        cfg.add_node(success_node)
        self._add_edge(cfg, ctx, assert_id, success_id, 'true', 'true')

        # False branch raises AssertionError - route through active exception dispatcher
        # Assertion failure should enter the active exception dispatcher, not bypass it
        active_dispatcher = ctx.current_try().get('exception_dispatch') if ctx.current_try() else None
        if active_dispatcher:
            self._add_edge(cfg, ctx, assert_id, active_dispatcher, 'false', 'false')
        else:
            # No active try context, go directly to exception exit
            self._add_edge(cfg, ctx, assert_id, cfg.exception_exit_node_id, 'false', 'false')

        # Create completion for tracking
        failure_completion = Completion(
            node_id=assert_id,
            kind='raise',
            exception_type='AssertionError',
            intended_target=cfg.exception_exit_node_id,
            source_metadata={'line': statement.lineno, 'file': ctx.file},
            completion_id=ctx.generate_completion_id()
        )

        return FlowResult(entry_nodes=[assert_id], normal_exits=[success_id], abrupt_exits=[failure_completion])

    def _build_yield(self, statement, cfg, ctx) -> FlowResult:
        """Handle yield statements for generator functions with suspension."""
        yield_id = ctx.generate_node_id()
        yield_expr = ast.unparse(statement.value) if statement.value else 'None'
        yield_node = CFGNode(
            id=yield_id, kind='suspension', label=f'yield {yield_expr}',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Yield',
            metadata={
                'suspension_point': 'yield',
                'yielded_value': yield_expr
            }
        )
        cfg.add_node(yield_node)
        ctx.ast_node_map[id(statement)] = yield_id
        ctx.ast_index.bind(statement, yield_id, "yield")
        if statement.value:
            ctx.ast_index.bind_expression_tree(statement.value, yield_id, "yield_value")

        # Yield is a suspension that may resume after the caller's next iteration
        return FlowResult(entry_nodes=[yield_id], normal_exits=[yield_id], abrupt_exits=[])

    def _build_yield_from(self, statement, cfg, ctx) -> FlowResult:
        """Handle yield from statements for generator functions with suspension."""
        yield_from_id = ctx.generate_node_id()
        yield_from_expr = ast.unparse(statement.value) if statement.value else 'None'
        yield_from_node = CFGNode(
            id=yield_from_id, kind='suspension', label=f'yield from {yield_from_expr}',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='YieldFrom',
            metadata={
                'suspension_point': 'yield_from',
                'delegated_generator': yield_from_expr
            }
        )
        cfg.add_node(yield_from_node)
        ctx.ast_node_map[id(statement)] = yield_from_id
        ctx.ast_index.bind(statement, yield_from_id, "yield_from")
        if statement.value:
            ctx.ast_index.bind_expression_tree(statement.value, yield_from_id, "yield_from_value")

        return FlowResult(entry_nodes=[yield_from_id], normal_exits=[yield_from_id], abrupt_exits=[])

    def _build_trystar(self, statement, cfg, ctx) -> FlowResult:
        """Build CFG for try* statements (exception groups)."""
        try_star_id = ctx.generate_node_id()
        try_star_node = CFGNode(
            id=try_star_id,
            kind='statement',
            label='try*',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='TryStar',
            metadata={'exception_group': True}
        )
        cfg.add_node(try_star_node)
        ctx.ast_node_map[id(statement)] = try_star_id
        ctx.ast_index.bind(statement, try_star_id, "trystar")
        
        # Build try body
        body_result = self._build_suite(statement.body, cfg, ctx)
        
        # Build except* handlers (exception group handlers)
        handler_join_id = ctx.generate_node_id()
        for handler in statement.excepthandlers:
            handler_id = ctx.generate_node_id()
            handler_node = CFGNode(
                id=handler_id,
                kind='exception_dispatch',
                label='except*',
                function_id=ctx.function_id,
                file=ctx.file,
                start_line=handler.lineno if hasattr(handler, 'lineno') else statement.lineno,
                end_line=handler.lineno if hasattr(handler, 'lineno') else statement.lineno,
                ast_kind='ExceptStar',
                metadata={'exception_group_handler': True}
            )
            cfg.add_node(handler_node)
            ctx.ast_index.bind(handler, handler_id, "except_star")
            
            # Connect try to handler
            self._add_edge(cfg, ctx, try_star_id, handler_id, 'exception_group')
            
            # Build handler body
            handler_result = self._build_suite(handler.body, cfg, ctx)
            for handler_exit in handler_result.normal_exits:
                self._add_edge(cfg, ctx, handler_exit, handler_join_id, 'next')
        
        return FlowResult(entry_nodes=[try_star_id], normal_exits=[handler_join_id], abrupt_exits=body_result.abrupt_exits)

    def _add_edge(self, cfg, ctx, source, target, kind, condition=None):
        edge_id = ctx.generate_edge_id()
        edge = CFGEdge(
            id=edge_id, source=source, target=target, kind=kind,
            condition=condition, evidence={'file': ctx.file},
        )
        cfg.add_edge(edge)
