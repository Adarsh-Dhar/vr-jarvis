"""Recursive Python CFG builder with full control-flow support - FlowResult-based implementation."""
import ast
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from .models import CFGNode, CFGEdge, ControlFlowGraph, CFGBuildArtifact
from .ast_cfg_index import ASTCFGIndex


@dataclass
class Completion:
    """Represents an abrupt completion (return, raise, break, continue)."""
    node_id: str
    kind: str
    target_loop_id: Optional[str] = None
    exception_type: Optional[str] = None


@dataclass
class FlowResult:
    """Result of processing a statement or suite."""
    entry_nodes: List[str] = field(default_factory=list)
    normal_exits: List[str] = field(default_factory=list)
    abrupt_exits: List[Completion] = field(default_factory=list)


class BuildContext:
    """Context for CFG construction, tracking loops and control structures."""

    def __init__(self, function_id: str, file: str):
        self.function_id = function_id
        self.file = file
        self.node_counter = 0
        self.edge_counter = 0
        self.loop_stack: List[Dict[str, str]] = []
        self.try_stack: List[Dict[str, str]] = []
        self.ast_node_map: Dict[int, str] = {}
        self.ast_index = ASTCFGIndex()
        self.diagnostics: List[Dict[str, Any]] = []

    def generate_node_id(self) -> str:
        node_id = f"{self.function_id}_N{self.node_counter}"
        self.node_counter += 1
        return node_id

    def generate_edge_id(self) -> str:
        edge_id = f"{self.function_id}_E{self.edge_counter}"
        self.edge_counter += 1
        return edge_id

    def add_diagnostic(self, code: str, line: int, message: str = "", severity: str = "warning"):
        self.diagnostics.append({'code': code, 'line': line, 'message': message, 'severity': severity})

    def push_loop(self, header_id: str, break_target: str, continue_target: str):
        self.loop_stack.append({'header': header_id, 'break_target': break_target, 'continue_target': continue_target})

    def pop_loop(self) -> Optional[Dict[str, str]]:
        return self.loop_stack.pop() if self.loop_stack else None

    def current_loop(self) -> Optional[Dict[str, str]]:
        return self.loop_stack[-1] if self.loop_stack else None

    def push_try(self, try_body_id: str, finally_node_id: Optional[str] = None):
        self.try_stack.append({'try_body': try_body_id, 'finally': finally_node_id, 'original_completions': []})

    def pop_try(self) -> Optional[Dict[str, str]]:
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
        function_ast: ast.FunctionDef,
        function_id: str,
        source: str,
        file_path: str
    ) -> CFGBuildArtifact:
        cfg = ControlFlowGraph(function_id=function_id, file=file_path)
        ctx = BuildContext(function_id, file_path)

        # Entry node
        entry_id = ctx.generate_node_id()
        entry_node = CFGNode(
            id=entry_id, kind='entry', label='entry',
            function_id=function_id, file=file_path,
            start_line=function_ast.lineno, end_line=function_ast.lineno,
            ast_kind='FunctionDef',
        )
        cfg.add_node(entry_node)
        cfg.entry_node_id = entry_id
        ctx.ast_node_map[id(function_ast)] = entry_id
        ctx.ast_index.bind(function_ast, entry_id, "function_entry")

        # Build body
        result = self._build_suite(function_ast.body, cfg, ctx)
        if result.entry_nodes:
            self._add_edge(cfg, ctx, entry_id, result.entry_nodes[0], 'next')

        # Exit node
        exit_id = ctx.generate_node_id()
        exit_node = CFGNode(
            id=exit_id, kind='exit', label='exit',
            function_id=function_id, file=file_path,
            start_line=function_ast.end_lineno or function_ast.lineno,
            end_line=function_ast.end_lineno or function_ast.lineno,
            ast_kind='FunctionDef',
        )
        cfg.add_node(exit_node)
        cfg.exit_node_id = exit_id

        for normal_exit in result.normal_exits:
            self._add_edge(cfg, ctx, normal_exit, exit_id, 'next')

        for completion in result.abrupt_exits:
            if completion.kind == 'return':
                self._add_edge(cfg, ctx, completion.node_id, exit_id, 'return')

        # Exception exit
        exception_exit_id = ctx.generate_node_id()
        exception_exit_node = CFGNode(
            id=exception_exit_id, kind='exception_exit', label='exception_exit',
            function_id=function_id, file=file_path,
            start_line=function_ast.end_lineno or function_ast.lineno,
            end_line=function_ast.end_lineno or function_ast.lineno,
            ast_kind='FunctionDef',
        )
        cfg.add_node(exception_exit_node)
        cfg.exception_exit_node_id = exception_exit_id

        for completion in result.abrupt_exits:
            if completion.kind == 'raise':
                self._add_edge(cfg, ctx, completion.node_id, exception_exit_id, 'raise')

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
        """Build a suite of statements, connecting fragments sequentially."""
        if not statements:
            return FlowResult(entry_nodes=[], normal_exits=[], abrupt_exits=[])

        # Build each statement fragment
        fragments = [self._build_statement(stmt, cfg, ctx) for stmt in statements]

        # Connect fragments: previous normal exits to next entry nodes
        for previous, current in zip(fragments, fragments[1:]):
            if previous.normal_exits and current.entry_nodes:
                self._connect(cfg, ctx, previous.normal_exits, current.entry_nodes, kind="next")
            if not previous.normal_exits:
                # Mark current as unreachable
                for entry_id in current.entry_nodes:
                    ctx.add_diagnostic("unreachable_statement", 0, "Statement unreachable due to abrupt completion", "warning")

        # Collect all entry nodes (for the first statement)
        entry_nodes = fragments[0].entry_nodes if fragments else []

        # Last normal exits
        normal_exits = fragments[-1].normal_exits if fragments else []

        # Collect all abrupt completions
        abrupt_exits = [
            completion
            for fragment in fragments
            for completion in fragment.abrupt_exits
        ]

        return FlowResult(entry_nodes=entry_nodes, normal_exits=normal_exits, abrupt_exits=abrupt_exits)

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
        return FlowResult(entry_nodes=[node_id], normal_exits=[node_id], abrupt_exits=[])

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
            },
        )
        cfg.add_node(condition_node)
        ctx.ast_node_map[id(statement.test)] = condition_id
        # Bind expression tree to condition node
        ctx.ast_index.bind_expression_tree(statement.test, condition_id, "condition")

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
            # No else: false edge goes directly from condition to join
            false_result = FlowResult(entry_nodes=[], normal_exits=[], abrupt_exits=[])

        join_id = ctx.generate_node_id()
        join_node = CFGNode(
            id=join_id, kind='join', label='join',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='If',
        )
        cfg.add_node(join_node)

        # Connect true branch exits to join
        for exit_id in true_result.normal_exits:
            self._add_edge(cfg, ctx, exit_id, join_id, 'next')

        # Connect false branch exits to join
        if statement.orelse:
            for exit_id in false_result.normal_exits:
                self._add_edge(cfg, ctx, exit_id, join_id, 'next')
        else:
            # No else: false edge goes directly from condition to join
            self._add_edge(cfg, ctx, condition_id, join_id, 'false', 'false')

        all_abrupt_exits = true_result.abrupt_exits + false_result.abrupt_exits
        return FlowResult(entry_nodes=[condition_id], normal_exits=[join_id], abrupt_exits=all_abrupt_exits)

    def _build_for(self, statement, cfg, ctx) -> FlowResult:
        header_id = ctx.generate_node_id()
        header_node = CFGNode(
            id=header_id, kind='loop_header', label='for loop',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='For',
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

        # Loop context
        loop_exit_id = ctx.generate_node_id()
        loop_exit_node = CFGNode(
            id=loop_exit_id, kind='join', label='loop exit',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='For',
        )
        cfg.add_node(loop_exit_node)

        # Loop else (executes on natural exhaustion)
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
            if else_result.entry_nodes:
                self._connect(cfg, ctx, [loop_exit_id], else_result.entry_nodes, kind="next")
            for exit_id in else_result.normal_exits:
                self._add_edge(cfg, ctx, exit_id, else_join_id, 'next')
            post_loop_exits = [else_join_id]
        else:
            post_loop_exits = [loop_exit_id]

        ctx.push_loop(header_id, loop_exit_id, header_id)

        # Build loop body
        body_result = self._build_suite(statement.body, cfg, ctx)
        if body_result.entry_nodes:
            self._connect(cfg, ctx, [header_id], body_result.entry_nodes, kind="next")

        # Connect body exits back to header (loop back)
        for exit_id in body_result.normal_exits:
            self._add_edge(cfg, ctx, exit_id, header_id, 'loop_back')

        # Add loop_exit edge from header to loop_exit
        self._add_edge(cfg, ctx, header_id, loop_exit_id, 'loop_exit')

        # Connect body abrupt exits (break/continue) handled in their builders

        ctx.pop_loop()

        return FlowResult(entry_nodes=[header_id], normal_exits=post_loop_exits, abrupt_exits=body_result.abrupt_exits)

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
        self._add_edge(cfg, ctx, header_id, loop_exit_id, 'loop_exit', 'false')

        # Connect loop_exit to post_loop (unless there's an else block)
        if statement.orelse:
            # Else block is between loop_exit and post_loop
            else_result = self._build_suite(statement.orelse, cfg, ctx)
            # Connect loop_exit to else entry nodes
            if else_result.entry_nodes:
                for entry_id in else_result.entry_nodes:
                    self._add_edge(cfg, ctx, loop_exit_id, entry_id, 'next')
            for else_exit in else_result.normal_exits:
                self._add_edge(cfg, ctx, else_exit, post_loop_id, 'next')
            final_exit = else_result.normal_exits if else_result.normal_exits else [loop_exit_id]
        else:
            # No else: loop_exit goes directly to post_loop
            self._add_edge(cfg, ctx, loop_exit_id, post_loop_id, 'next')
            final_exit = [post_loop_id]

        ctx.pop_loop()
        abrupt_exits = [c for c in body_result.abrupt_exits if c.kind not in ('break', 'continue')]
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

        completion = Completion(return_id, 'return')
        # Check if there's a finally block to route through
        try_ctx = ctx.current_try()
        if try_ctx and try_ctx['finally']:
            ctx.add_abrupt_completion(completion)
            # Normal exits from finally will handle the original completion
            return FlowResult(entry_nodes=[return_id], normal_exits=[], abrupt_exits=[completion])
        else:
            return FlowResult(entry_nodes=[return_id], normal_exits=[], abrupt_exits=[completion])

    def _build_raise(self, statement, cfg, ctx) -> FlowResult:
        raise_id = ctx.generate_node_id()
        raise_expr = ast.unparse(statement.exc) if statement.exc else 'exception'
        raise_node = CFGNode(
            id=raise_id, kind='raise', label=f'raise {raise_expr}',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Raise', condition=raise_expr,
        )
        cfg.add_node(raise_node)
        ctx.ast_node_map[id(statement)] = raise_id
        ctx.ast_index.bind(statement, raise_id, "raise")
        # Bind expression tree to raise node
        if statement.exc:
            ctx.ast_index.bind_expression_tree(statement.exc, raise_id, "exception")

        completion = Completion(raise_id, 'raise')
        # Check if there's a finally block to route through
        try_ctx = ctx.current_try()
        if try_ctx and try_ctx['finally']:
            ctx.add_abrupt_completion(completion)
            return FlowResult(entry_nodes=[raise_id], normal_exits=[], abrupt_exits=[completion])
        else:
            return FlowResult(entry_nodes=[raise_id], normal_exits=[], abrupt_exits=[completion])

    def _build_break(self, statement: ast.Break, cfg, ctx) -> FlowResult:
        loop_ctx = ctx.current_loop()
        if not loop_ctx:
            ctx.add_diagnostic("break_outside_loop", 0, "Break statement outside loop", "error")
            return FlowResult(entry_nodes=[], normal_exits=[])

        break_id = ctx.generate_node_id()
        break_node = CFGNode(
            id=break_id, kind='statement', label='break',
            function_id=ctx.function_id, file=ctx.file,
            start_line=0, end_line=0, ast_kind='Break',
        )
        cfg.add_node(break_node)
        ctx.ast_node_map[id(statement)] = break_id
        ctx.ast_index.bind(statement, break_id, "break")
        self._add_edge(cfg, ctx, break_id, loop_ctx['break_target'], 'break')

        completion = Completion(break_id, 'break', target_loop_id=loop_ctx['header'])
        # Check if there's a finally block to route through
        try_ctx = ctx.current_try()
        if try_ctx and try_ctx['finally']:
            ctx.add_abrupt_completion(completion)
            return FlowResult(entry_nodes=[break_id], normal_exits=[], abrupt_exits=[completion])
        else:
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
            start_line=0, end_line=0, ast_kind='Continue',
        )
        cfg.add_node(continue_node)
        ctx.ast_node_map[id(statement)] = continue_id
        ctx.ast_index.bind(statement, continue_id, "continue")
        self._add_edge(cfg, ctx, continue_id, loop_ctx['continue_target'], 'continue')

        completion = Completion(continue_id, 'continue', target_loop_id=loop_ctx['header'])
        # Check if there's a finally block to route through
        try_ctx = ctx.current_try()
        if try_ctx and try_ctx['finally']:
            ctx.add_abrupt_completion(completion)
            return FlowResult(entry_nodes=[continue_id], normal_exits=[], abrupt_exits=[completion])
        else:
            return FlowResult(entry_nodes=[continue_id], normal_exits=[], abrupt_exits=[completion])

    def _build_try(self, statement, cfg, ctx) -> FlowResult:
        try_result = self._build_suite(statement.body, cfg, ctx)

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

        for handler in statement.handlers:
            handler_id = ctx.generate_node_id()
            handler_type = ast.unparse(handler.type) if handler.type else 'Exception'
            handler_node = CFGNode(
                id=handler_id, kind='statement', label=f'except {handler_type}',
                function_id=ctx.function_id, file=ctx.file,
                start_line=handler.lineno, end_line=handler.end_lineno or handler.lineno,
                ast_kind='ExceptHandler',
            )
            cfg.add_node(handler_node)
            ctx.ast_node_map[id(handler)] = handler_id
            self._add_edge(cfg, ctx, dispatch_id, handler_id, 'exception')

            if handler.name:
                ctx.ast_node_map[id(handler)] = handler_id

            handler_result = self._build_suite(handler.body, cfg, ctx)
            # Connect handler to handler body entry nodes
            if handler_result.entry_nodes:
                for entry_id in handler_result.entry_nodes:
                    self._add_edge(cfg, ctx, handler_id, entry_id, 'next')
            for handler_exit in handler_result.normal_exits:
                self._add_edge(cfg, ctx, handler_exit, handler_join_id, 'next')

        if statement.orelse:
            else_result = self._build_suite(statement.orelse, cfg, ctx)
            # Connect try exits to else entry nodes
            if else_result.entry_nodes:
                for entry_id in else_result.entry_nodes:
                    for try_exit in try_result.normal_exits:
                        self._add_edge(cfg, ctx, try_exit, entry_id, 'next')
            for else_exit in else_result.normal_exits:
                self._add_edge(cfg, ctx, else_exit, handler_join_id, 'next')
        else:
            for try_exit in try_result.normal_exits:
                self._add_edge(cfg, ctx, try_exit, handler_join_id, 'next')

        if statement.finalbody:
            finally_id = ctx.generate_node_id()
            finally_node = CFGNode(
                id=finally_id, kind='finally', label='finally',
                function_id=ctx.function_id, file=ctx.file,
                start_line=statement.finalbody[0].lineno,
                end_line=statement.finalbody[-1].end_lineno or statement.finalbody[0].lineno,
                ast_kind='Try',
            )
            cfg.add_node(finally_node)
            self._add_edge(cfg, ctx, handler_join_id, finally_id, 'finally')

            # Push try context with finally node
            ctx.push_try(handler_join_id, finally_id)

            finally_result = self._build_suite(statement.finalbody, cfg, ctx)
            # Connect finally node to finally body entry nodes
            if finally_result.entry_nodes:
                for entry_id in finally_result.entry_nodes:
                    self._add_edge(cfg, ctx, finally_id, entry_id, 'next')
            final_exit = finally_result.normal_exits if finally_result.normal_exits else [finally_id]

            # Pop try context and get stored abrupt completions
            try_ctx = ctx.pop_try()
            abrupt_exits = try_ctx['original_completions'] if try_ctx.get('original_completions') else []

            # Route stored abrupt completions through finally
            for completion in abrupt_exits:
                # Connect completion node to finally
                self._add_edge(cfg, ctx, completion.node_id, finally_id, 'finally')
                # The completion will be re-emitted after finally
        else:
            final_exit = [handler_join_id]
            abrupt_exits = try_result.abrupt_exits
        return FlowResult(entry_nodes=try_result.entry_nodes, normal_exits=final_exit, abrupt_exits=abrupt_exits)

    def _build_with(self, statement, cfg, ctx) -> FlowResult:
        with_id = ctx.generate_node_id()
        with_node = CFGNode(
            id=with_id, kind='statement', label='with',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='With',
        )
        cfg.add_node(with_node)
        ctx.ast_node_map[id(statement)] = with_id
        ctx.ast_index.bind(statement, with_id, "with")
        # Bind expression trees to with node
        for item in statement.items:
            ctx.ast_index.bind_expression_tree(item.context_expr, with_id, "context")

        body_result = self._build_suite(statement.body, cfg, ctx)
        # Connect with node to body entry nodes
        if body_result.entry_nodes:
            for entry_id in body_result.entry_nodes:
                self._add_edge(cfg, ctx, with_id, entry_id, 'next')
        return FlowResult(entry_nodes=[with_id], normal_exits=body_result.normal_exits, abrupt_exits=body_result.abrupt_exits)

    def _build_match(self, statement, cfg, ctx) -> FlowResult:
        match_id = ctx.generate_node_id()
        match_node = CFGNode(
            id=match_id, kind='condition', label='match',
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

        for case in statement.cases:
            case_id = ctx.generate_node_id()
            pattern = ast.unparse(case.pattern) if hasattr(ast, 'unparse') else 'pattern'
            case_node = CFGNode(
                id=case_id, kind='condition', label=pattern,
                function_id=ctx.function_id, file=ctx.file,
                start_line=case.lineno, end_line=case.lineno,
                ast_kind='match_case', condition=pattern,
            )
            cfg.add_node(case_node)
            ctx.ast_node_map[id(case)] = case_id
            ctx.ast_index.bind(case, case_id, "match_case")
            if case.guard:
                ctx.ast_index.bind_expression_tree(case.guard, case_id, "match_guard")
            self._add_edge(cfg, ctx, match_id, case_id, 'next')

            case_result = self._build_suite(case.body, cfg, ctx)
            # Connect case node to case body entry nodes
            if case_result.entry_nodes:
                for entry_id in case_result.entry_nodes:
                    self._add_edge(cfg, ctx, case_id, entry_id, 'next')
            for case_exit in case_result.normal_exits:
                self._add_edge(cfg, ctx, case_exit, join_id, 'next')

        return FlowResult(entry_nodes=[match_id], normal_exits=[join_id], abrupt_exits=[])

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
        self._add_edge(cfg, ctx, assert_id, success_id, 'next', 'true')

        return FlowResult(entry_nodes=[assert_id], normal_exits=[success_id], abrupt_exits=[Completion(assert_id, 'raise', exception_type='AssertionError')])

    def _add_edge(self, cfg, ctx, source, target, kind, condition=None):
        edge_id = ctx.generate_edge_id()
        edge = CFGEdge(
            id=edge_id, source=source, target=target, kind=kind,
            condition=condition, evidence={'file': ctx.file},
        )
        cfg.add_edge(edge)
