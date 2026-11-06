"""Recursive Python CFG builder with full control-flow support - FlowResult-based implementation."""
import ast
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from .models import CFGNode, CFGEdge, ControlFlowGraph


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
        self.try_stack.append({'try_body': try_body_id, 'finally': finally_node_id})

    def pop_try(self) -> Optional[Dict[str, str]]:
        return self.try_stack.pop() if self.try_stack else None

    def current_try(self) -> Optional[Dict[str, str]]:
        return self.try_stack[-1] if self.try_stack else None


class PythonCFGBuilder:
    """Build control-flow graphs from Python AST using FlowResult interface."""

    def build_function(
        self,
        function_ast: ast.FunctionDef,
        function_id: str,
        source: str,
        file_path: str
    ) -> ControlFlowGraph:
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

        # Build body
        result = self._build_suite(function_ast.body, [entry_id], cfg, ctx, entry_edge_kind="next")

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

        # Store AST node map in CFG for data-flow use
        cfg.ast_node_map = ctx.ast_node_map

        return cfg

    def _build_suite(self, statements, incoming_ids, cfg, ctx, entry_edge_kind="next") -> FlowResult:
        current_incoming = list(incoming_ids)
        abrupt_exits = []

        for index, statement in enumerate(statements):
            if not current_incoming:
                ctx.add_diagnostic("unreachable_statement", statement.lineno)
                continue

            edge_kind = entry_edge_kind if index == 0 else "next"
            result = self._build_statement(statement, current_incoming, cfg, ctx, incoming_edge_kind=edge_kind)
            abrupt_exits.extend(result.abrupt_exits)
            current_incoming = result.normal_exits

        return FlowResult(normal_exits=current_incoming, abrupt_exits=abrupt_exits)

    def _build_statement(self, statement, incoming_ids, cfg, ctx, incoming_edge_kind="next") -> FlowResult:
        if isinstance(statement, ast.If):
            return self._build_if(statement, incoming_ids, cfg, ctx)
        elif isinstance(statement, ast.For):
            return self._build_for(statement, incoming_ids, cfg, ctx)
        elif isinstance(statement, ast.While):
            return self._build_while(statement, incoming_ids, cfg, ctx)
        elif isinstance(statement, ast.Try):
            return self._build_try(statement, incoming_ids, cfg, ctx)
        elif isinstance(statement, ast.With):
            return self._build_with(statement, incoming_ids, cfg, ctx)
        elif isinstance(statement, ast.Match):
            return self._build_match(statement, incoming_ids, cfg, ctx)
        elif isinstance(statement, ast.Return):
            return self._build_return(statement, incoming_ids, cfg, ctx)
        elif isinstance(statement, ast.Raise):
            return self._build_raise(statement, incoming_ids, cfg, ctx)
        elif isinstance(statement, ast.Break):
            return self._build_break(statement, incoming_ids, cfg, ctx)
        elif isinstance(statement, ast.Continue):
            return self._build_continue(statement, incoming_ids, cfg, ctx)
        elif isinstance(statement, ast.Assert):
            return self._build_assert(statement, incoming_ids, cfg, ctx)
        else:
            return self._build_simple_statement(statement, incoming_ids, cfg, ctx, incoming_edge_kind)

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
        ctx.ast_node_map[id(statement)] = node_id
        return node_id

    def _connect(self, cfg, ctx, incoming_ids, target_id, kind="next", condition=None):
        for source_id in incoming_ids:
            self._add_edge(cfg, ctx, source_id, target_id, kind, condition)

    def _build_simple_statement(self, statement, incoming_ids, cfg, ctx, incoming_edge_kind="next") -> FlowResult:
        node_id = self._create_statement_node(
            statement, 'statement',
            ast.unparse(statement) if hasattr(ast, 'unparse') else 'statement',
            cfg, ctx,
        )
        self._connect(cfg, ctx, incoming_ids, node_id, incoming_edge_kind)
        return FlowResult(normal_exits=[node_id])

    def _build_if(self, statement, incoming_ids, cfg, ctx) -> FlowResult:
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
        self._connect(cfg, ctx, incoming_ids, condition_id)

        true_result = self._build_suite(statement.body, [condition_id], cfg, ctx, entry_edge_kind="true")
        self._connect(cfg, ctx, [condition_id], true_result.normal_exits[0] if true_result.normal_exits else condition_id, "true", "true")

        if statement.orelse:
            false_result = self._build_suite(statement.orelse, [condition_id], cfg, ctx, entry_edge_kind="false")
            self._connect(cfg, ctx, [condition_id], false_result.normal_exits[0] if false_result.normal_exits else condition_id, "false", "false")
        else:
            false_result = FlowResult(normal_exits=[condition_id])
            self._connect(cfg, ctx, [condition_id], condition_id, "false", "false")

        join_id = ctx.generate_node_id()
        join_node = CFGNode(
            id=join_id, kind='join', label='join',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='If',
        )
        cfg.add_node(join_node)

        all_normal_exits = true_result.normal_exits + false_result.normal_exits
        for exit_id in all_normal_exits:
            self._add_edge(cfg, ctx, exit_id, join_id, 'next')

        all_abrupt_exits = true_result.abrupt_exits + false_result.abrupt_exits
        return FlowResult(normal_exits=[join_id], abrupt_exits=all_abrupt_exits)

    def _build_for(self, statement, incoming_ids, cfg, ctx) -> FlowResult:
        header_id = ctx.generate_node_id()
        header_node = CFGNode(
            id=header_id, kind='loop_header', label='for loop',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='For',
        )
        cfg.add_node(header_node)
        ctx.ast_node_map[id(statement)] = header_id
        self._connect(cfg, ctx, incoming_ids, header_id)

        iter_id = ctx.generate_node_id()
        iter_node = CFGNode(
            id=iter_id, kind='statement',
            label=f'for {ast.unparse(statement.target) if hasattr(ast, 'unparse') else "for target"}',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='For',
        )
        cfg.add_node(iter_node)
        ctx.ast_node_map[id(statement.target)] = iter_id
        self._add_edge(cfg, ctx, header_id, iter_id, 'next')

        loop_exit_id = ctx.generate_node_id()
        loop_exit_node = CFGNode(
            id=loop_exit_id, kind='join', label='loop exit',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='For',
        )
        cfg.add_node(loop_exit_node)

        ctx.push_loop(header_id, loop_exit_id, header_id)

        body_result = self._build_suite(statement.body, [iter_id], cfg, ctx)
        for body_exit in body_result.normal_exits:
            self._add_edge(cfg, ctx, body_exit, header_id, 'loop_back')

        self._add_edge(cfg, ctx, header_id, loop_exit_id, 'loop_exit')

        if statement.orelse:
            else_result = self._build_suite(statement.orelse, [loop_exit_id], cfg, ctx)
            final_exit = else_result.normal_exits if else_result.normal_exits else [loop_exit_id]
        else:
            final_exit = [loop_exit_id]

        ctx.pop_loop()
        abrupt_exits = [c for c in body_result.abrupt_exits if c.kind not in ('break', 'continue')]
        return FlowResult(normal_exits=final_exit, abrupt_exits=abrupt_exits)

    def _build_while(self, statement, incoming_ids, cfg, ctx) -> FlowResult:
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
        ctx.ast_node_map[id(statement.test)] = header_id
        self._connect(cfg, ctx, incoming_ids, header_id)

        loop_exit_id = ctx.generate_node_id()
        loop_exit_node = CFGNode(
            id=loop_exit_id, kind='join', label='loop exit',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.end_lineno or statement.lineno,
            ast_kind='While',
        )
        cfg.add_node(loop_exit_node)

        ctx.push_loop(header_id, loop_exit_id, header_id)

        body_result = self._build_suite(statement.body, [header_id], cfg, ctx, entry_edge_kind="true")
        for body_exit in body_result.normal_exits:
            self._add_edge(cfg, ctx, body_exit, header_id, 'loop_back')

        self._add_edge(cfg, ctx, header_id, loop_exit_id, 'loop_exit', 'false')

        if statement.orelse:
            else_result = self._build_suite(statement.orelse, [loop_exit_id], cfg, ctx)
            final_exit = else_result.normal_exits if else_result.normal_exits else [loop_exit_id]
        else:
            final_exit = [loop_exit_id]

        ctx.pop_loop()
        abrupt_exits = [c for c in body_result.abrupt_exits if c.kind not in ('break', 'continue')]
        return FlowResult(normal_exits=final_exit, abrupt_exits=abrupt_exits)

    def _build_return(self, statement, incoming_ids, cfg, ctx) -> FlowResult:
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
        self._connect(cfg, ctx, incoming_ids, return_id)
        return FlowResult(normal_exits=[], abrupt_exits=[Completion(return_id, 'return')])

    def _build_raise(self, statement, incoming_ids, cfg, ctx) -> FlowResult:
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
        self._connect(cfg, ctx, incoming_ids, raise_id)
        return FlowResult(normal_exits=[], abrupt_exits=[Completion(raise_id, 'raise')])

    def _build_break(self, statement: ast.Break, incoming_ids, cfg, ctx) -> FlowResult:
        loop_ctx = ctx.current_loop()
        if not loop_ctx:
            ctx.add_diagnostic("break_outside_loop", 0, "Break statement outside loop", "error")
            return FlowResult(normal_exits=[])

        break_id = ctx.generate_node_id()
        break_node = CFGNode(
            id=break_id, kind='statement', label='break',
            function_id=ctx.function_id, file=ctx.file,
            start_line=0, end_line=0, ast_kind='Break',
        )
        cfg.add_node(break_node)
        self._connect(cfg, ctx, incoming_ids, break_id)
        self._add_edge(cfg, ctx, break_id, loop_ctx['break_target'], 'break')
        return FlowResult(normal_exits=[], abrupt_exits=[Completion(break_id, 'break', target_loop_id=loop_ctx['header'])])

    def _build_continue(self, statement: ast.Continue, incoming_ids, cfg, ctx) -> FlowResult:
        loop_ctx = ctx.current_loop()
        if not loop_ctx:
            ctx.add_diagnostic("continue_outside_loop", 0, "Continue statement outside loop", "error")
            return FlowResult(normal_exits=[])

        continue_id = ctx.generate_node_id()
        continue_node = CFGNode(
            id=continue_id, kind='statement', label='continue',
            function_id=ctx.function_id, file=ctx.file,
            start_line=0, end_line=0, ast_kind='Continue',
        )
        cfg.add_node(continue_node)
        self._connect(cfg, ctx, incoming_ids, continue_id)
        self._add_edge(cfg, ctx, continue_id, loop_ctx['continue_target'], 'continue')
        return FlowResult(normal_exits=[], abrupt_exits=[Completion(continue_id, 'continue', target_loop_id=loop_ctx['header'])])

    def _build_try(self, statement, incoming_ids, cfg, ctx) -> FlowResult:
        try_result = self._build_suite(statement.body, incoming_ids, cfg, ctx)

        dispatch_id = ctx.generate_node_id()
        dispatch_node = CFGNode(
            id=dispatch_id, kind='exception_dispatch', label='exception dispatch',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Try',
        )
        cfg.add_node(dispatch_node)

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

            handler_result = self._build_suite(handler.body, [handler_id], cfg, ctx)
            for handler_exit in handler_result.normal_exits:
                self._add_edge(cfg, ctx, handler_exit, handler_join_id, 'next')

        if statement.orelse:
            else_result = self._build_suite(statement.orelse, try_result.normal_exits, cfg, ctx)
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
            self._connect(cfg, ctx, [handler_join_id], finally_id, 'finally')

            finally_result = self._build_suite(statement.finalbody, [finally_id], cfg, ctx)
            final_exit = finally_result.normal_exits if finally_result.normal_exits else [finally_id]
        else:
            final_exit = [handler_join_id]

        abrupt_exits = [c for c in try_result.abrupt_exits if c.kind in ('return', 'raise')]
        return FlowResult(normal_exits=final_exit, abrupt_exits=abrupt_exits)

    def _build_with(self, statement, incoming_ids, cfg, ctx) -> FlowResult:
        with_id = ctx.generate_node_id()
        with_node = CFGNode(
            id=with_id, kind='statement', label='with',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='With',
        )
        cfg.add_node(with_node)
        ctx.ast_node_map[id(statement)] = with_id
        self._connect(cfg, ctx, incoming_ids, with_id)

        body_result = self._build_suite(statement.body, [with_id], cfg, ctx)
        return body_result

    def _build_match(self, statement, incoming_ids, cfg, ctx) -> FlowResult:
        match_id = ctx.generate_node_id()
        match_node = CFGNode(
            id=match_id, kind='condition', label='match',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Match',
        )
        cfg.add_node(match_node)
        ctx.ast_node_map[id(statement)] = match_id
        self._connect(cfg, ctx, incoming_ids, match_id)

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
            self._add_edge(cfg, ctx, match_id, case_id, 'next')

            case_result = self._build_suite(case.body, [case_id], cfg, ctx)
            for case_exit in case_result.normal_exits:
                self._add_edge(cfg, ctx, case_exit, join_id, 'next')

        return FlowResult(normal_exits=[join_id], abrupt_exits=[])

    def _build_assert(self, statement, incoming_ids, cfg, ctx) -> FlowResult:
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
        self._connect(cfg, ctx, incoming_ids, assert_id)

        success_id = ctx.generate_node_id()
        success_node = CFGNode(
            id=success_id, kind='statement', label='assert pass',
            function_id=ctx.function_id, file=ctx.file,
            start_line=statement.lineno, end_line=statement.lineno,
            ast_kind='Assert',
        )
        cfg.add_node(success_node)
        self._add_edge(cfg, ctx, assert_id, success_id, 'next', 'true')

        return FlowResult(normal_exits=[success_id], abrupt_exits=[Completion(assert_id, 'raise', exception_type='AssertionError')])

    def _add_edge(self, cfg, ctx, source, target, kind, condition=None):
        edge_id = ctx.generate_edge_id()
        edge = CFGEdge(
            id=edge_id, source=source, target=target, kind=kind,
            condition=condition, evidence={'file': ctx.file},
        )
        cfg.add_edge(edge)
