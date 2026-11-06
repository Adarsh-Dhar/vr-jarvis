"""Recursive Python CFG builder with full control-flow support."""
import ast
from typing import Optional, List, Tuple, Dict, Any
from .models import CFGNode, CFGEdge, ControlFlowGraph


class BuildContext:
    """Context for CFG construction, tracking loops and control structures."""

    def __init__(self, function_id: str, file: str):
        self.function_id = function_id
        self.file = file
        self.node_counter = 0
        self.edge_counter = 0
        self.loop_stack: List[Dict[str, str]] = []  # Stack of loop contexts
        self.try_stack: List[Dict[str, str]] = []  # Stack of try contexts

    def generate_node_id(self) -> str:
        """Generate a unique node ID."""
        node_id = f"{self.function_id}_N{self.node_counter}"
        self.node_counter += 1
        return node_id

    def generate_edge_id(self) -> str:
        """Generate a unique edge ID."""
        edge_id = f"{self.function_id}_E{self.edge_counter}"
        self.edge_counter += 1
        return edge_id

    def push_loop(self, header_id: str, break_target: str, continue_target: str):
        """Push a loop context onto the stack."""
        self.loop_stack.append({
            'header': header_id,
            'break_target': break_target,
            'continue_target': continue_target,
        })

    def pop_loop(self) -> Optional[Dict[str, str]]:
        """Pop a loop context from the stack."""
        return self.loop_stack.pop() if self.loop_stack else None

    def current_loop(self) -> Optional[Dict[str, str]]:
        """Get the current loop context."""
        return self.loop_stack[-1] if self.loop_stack else None

    def push_try(self, try_body_id: str, finally_node_id: Optional[str] = None):
        """Push a try context onto the stack."""
        self.try_stack.append({
            'try_body': try_body_id,
            'finally': finally_node_id,
        })

    def pop_try(self) -> Optional[Dict[str, str]]:
        """Pop a try context from the stack."""
        return self.try_stack.pop() if self.try_stack else None

    def current_try(self) -> Optional[Dict[str, str]]:
        """Get the current try context."""
        return self.try_stack[-1] if self.try_stack else None


class PythonCFGBuilder:
    """Build control-flow graphs from Python AST."""

    def build_function(
        self,
        function_ast: ast.FunctionDef,
        function_id: str,
        source: str,
        file_path: str
    ) -> ControlFlowGraph:
        """Build a CFG for a function."""
        cfg = ControlFlowGraph(function_id=function_id, file=file_path)
        ctx = BuildContext(function_id, file_path)

        # Create entry node
        entry_id = ctx.generate_node_id()
        entry_node = CFGNode(
            id=entry_id,
            kind='entry',
            label='entry',
            function_id=function_id,
            file=file_path,
            start_line=function_ast.lineno,
            end_line=function_ast.lineno,
            ast_kind='FunctionDef',
        )
        cfg.add_node(entry_node)

        # Build function body
        exit_node_id = self._build_suite(
            function_ast.body,
            entry_id,
            cfg,
            ctx,
            function_ast.lineno,
            function_ast.end_lineno or function_ast.lineno,
        )

        # Create exit node if we don't have one
        if exit_node_id is None:
            exit_node_id = ctx.generate_node_id()
            exit_node = CFGNode(
                id=exit_node_id,
                kind='exit',
                label='exit',
                function_id=function_id,
                file=file_path,
                start_line=function_ast.end_lineno or function_ast.lineno,
                end_line=function_ast.end_lineno or function_ast.lineno,
                ast_kind='FunctionDef',
            )
            cfg.add_node(exit_node)
            # Connect entry to exit for empty functions
            self._add_edge(cfg, ctx, entry_id, exit_node_id, 'next')

        cfg.metadata = {
            'function_name': function_ast.name,
            'parameters': [arg.arg for arg in function_ast.args.args],
            'source_file': file_path,
        }

        return cfg

    def _build_suite(
        self,
        statements: List[ast.stmt],
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
        start_line: int,
        end_line: int,
    ) -> Optional[str]:
        """Build CFG for a sequence of statements."""
        current_id = incoming_id

        for i, stmt in enumerate(statements):
            next_id = None
            if i < len(statements) - 1:
                # Create a placeholder for the next statement
                next_id = ctx.generate_node_id()

            # Build this statement
            outgoing_id = self._build_statement(stmt, current_id, cfg, ctx, next_id)

            if outgoing_id is None:
                # Statement doesn't have outgoing edge (e.g., return)
                # Continue with next statement if exists
                if next_id is not None:
                    current_id = next_id
                else:
                    return None
            else:
                current_id = outgoing_id

        return current_id

    def _build_statement(
        self,
        statement: ast.stmt,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
        fallthrough_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build CFG for a single statement."""
        if isinstance(statement, ast.If):
            return self._build_if(statement, incoming_id, cfg, ctx, fallthrough_id)
        elif isinstance(statement, ast.For):
            return self._build_for(statement, incoming_id, cfg, ctx, fallthrough_id)
        elif isinstance(statement, ast.While):
            return self._build_while(statement, incoming_id, cfg, ctx, fallthrough_id)
        elif isinstance(statement, ast.Try):
            return self._build_try(statement, incoming_id, cfg, ctx, fallthrough_id)
        elif isinstance(statement, ast.With):
            return self._build_with(statement, incoming_id, cfg, ctx, fallthrough_id)
        elif isinstance(statement, ast.Match):
            return self._build_match(statement, incoming_id, cfg, ctx, fallthrough_id)
        elif isinstance(statement, ast.Return):
            return self._build_return(statement, incoming_id, cfg, ctx)
        elif isinstance(statement, ast.Raise):
            return self._build_raise(statement, incoming_id, cfg, ctx)
        elif isinstance(statement, ast.Break):
            return self._build_break(incoming_id, cfg, ctx)
        elif isinstance(statement, ast.Continue):
            return self._build_continue(incoming_id, cfg, ctx)
        else:
            # Simple statement
            return self._build_simple_statement(statement, incoming_id, cfg, ctx, fallthrough_id)

    def _build_simple_statement(
        self,
        statement: ast.stmt,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
        fallthrough_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build CFG for a simple statement."""
        node_id = ctx.generate_node_id()
        node = CFGNode(
            id=node_id,
            kind='statement',
            label=ast.unparse(statement) if hasattr(ast, 'unparse') else 'statement',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.end_lineno or statement.lineno,
            ast_kind=statement.__class__.__name__,
        )
        cfg.add_node(node)

        self._add_edge(cfg, ctx, incoming_id, node_id, 'next')

        if fallthrough_id:
            self._add_edge(cfg, ctx, node_id, fallthrough_id, 'next')
            return fallthrough_id
        return node_id

    def _build_if(
        self,
        statement: ast.If,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
        fallthrough_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build CFG for an if-else statement."""
        # Create condition node
        condition_id = ctx.generate_node_id()
        condition_expr = ast.unparse(statement.test) if hasattr(ast, 'unparse') else 'condition'
        condition_node = CFGNode(
            id=condition_id,
            kind='condition',
            label=condition_expr,
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='If',
            condition=condition_expr,
        )
        cfg.add_node(condition_node)
        self._add_edge(cfg, ctx, incoming_id, condition_id, 'next')

        # Create join node
        join_id = ctx.generate_node_id()
        join_node = CFGNode(
            id=join_id,
            kind='join',
            label='join',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.end_lineno or statement.lineno,
            ast_kind='If',
        )
        cfg.add_node(join_node)

        # Build true branch
        if statement.body:
            true_end = self._build_suite(
                statement.body,
                condition_id,
                cfg,
                ctx,
                statement.body[0].lineno,
                statement.body[-1].end_lineno or statement.body[0].lineno,
            )
            # Edge from condition to true branch is true
            if statement.body:
                first_body_node = self._get_last_added_node(cfg, ctx)
                if first_body_node and first_body_node.id != condition_id:
                    # Update the edge from condition to be true
                    for edge in cfg.edges:
                        if edge.source == condition_id and edge.target == first_body_node.id:
                            edge.kind = 'true'
                            edge.condition = 'true'
                            break
            if true_end:
                self._add_edge(cfg, ctx, true_end, join_id, 'next')

        # Build false branch (else)
        if statement.orelse:
            # Edge from condition to else is false
            else_end = self._build_suite(
                statement.orelse,
                condition_id,
                cfg,
                ctx,
                statement.orelse[0].lineno,
                statement.orelse[-1].end_lineno or statement.orelse[0].lineno,
            )
            # Update the edge to be false
            if statement.orelse:
                first_else_node = self._get_last_added_node(cfg, ctx)
                if first_else_node and first_else_node.id != condition_id:
                    for edge in cfg.edges:
                        if edge.source == condition_id and edge.target == first_else_node.id:
                            edge.kind = 'false'
                            edge.condition = 'false'
                            break
            if else_end:
                self._add_edge(cfg, ctx, else_end, join_id, 'next')
        else:
            # No else branch: direct false edge to join
            self._add_edge(cfg, ctx, condition_id, join_id, 'false', 'false')

        # Connect join to fallthrough
        if fallthrough_id:
            self._add_edge(cfg, ctx, join_id, fallthrough_id, 'next')
            return fallthrough_id
        return join_id

    def _build_for(
        self,
        statement: ast.For,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
        fallthrough_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build CFG for a for loop."""
        # Create loop header
        header_id = ctx.generate_node_id()
        header_node = CFGNode(
            id=header_id,
            kind='loop_header',
            label='for loop',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='For',
        )
        cfg.add_node(header_node)
        self._add_edge(cfg, ctx, incoming_id, header_id, 'next')

        # Create exit node for the loop
        loop_exit_id = ctx.generate_node_id()
        loop_exit_node = CFGNode(
            id=loop_exit_id,
            kind='join',
            label='loop exit',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.end_lineno or statement.lineno,
            ast_kind='For',
        )
        cfg.add_node(loop_exit_node)

        # Push loop context
        ctx.push_loop(header_id, loop_exit_id, header_id)

        # Build loop body
        if statement.body:
            body_end = self._build_suite(
                statement.body,
                header_id,
                cfg,
                ctx,
                statement.body[0].lineno,
                statement.body[-1].end_lineno or statement.body[0].lineno,
            )
            # Add loop-back edge from body end to header
            if body_end:
                self._add_edge(cfg, ctx, body_end, header_id, 'loop_back')

        # Add loop-exit edge from header to exit
        self._add_edge(cfg, ctx, header_id, loop_exit_id, 'loop_exit')

        # Build else clause (executed if loop completes without break)
        if statement.orelse:
            else_end = self._build_suite(
                statement.orelse,
                loop_exit_id,
                cfg,
                ctx,
                statement.orelse[0].lineno,
                statement.orelse[-1].end_lineno or statement.orelse[0].lineno,
            )
            final_exit = else_end if else_end else loop_exit_id
        else:
            final_exit = loop_exit_id

        # Pop loop context
        ctx.pop_loop()

        # Connect to fallthrough
        if fallthrough_id:
            self._add_edge(cfg, ctx, final_exit, fallthrough_id, 'next')
            return fallthrough_id
        return final_exit

    def _build_while(
        self,
        statement: ast.While,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
        fallthrough_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build CFG for a while loop."""
        # Create loop header (condition)
        header_id = ctx.generate_node_id()
        condition_expr = ast.unparse(statement.test) if hasattr(ast, 'unparse') else 'condition'
        header_node = CFGNode(
            id=header_id,
            kind='loop_header',
            label=condition_expr,
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='While',
            condition=condition_expr,
        )
        cfg.add_node(header_node)
        self._add_edge(cfg, ctx, incoming_id, header_id, 'next')

        # Create exit node
        loop_exit_id = ctx.generate_node_id()
        loop_exit_node = CFGNode(
            id=loop_exit_id,
            kind='join',
            label='loop exit',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.end_lineno or statement.lineno,
            ast_kind='While',
        )
        cfg.add_node(loop_exit_node)

        # Push loop context
        ctx.push_loop(header_id, loop_exit_id, header_id)

        # Build loop body
        if statement.body:
            body_end = self._build_suite(
                statement.body,
                header_id,
                cfg,
                ctx,
                statement.body[0].lineno,
                statement.body[-1].end_lineno or statement.body[0].lineno,
            )
            # Add loop-back edge
            if body_end:
                self._add_edge(cfg, ctx, body_end, header_id, 'loop_back')

        # Add loop-exit edge (false branch)
        self._add_edge(cfg, ctx, header_id, loop_exit_id, 'loop_exit', 'false')

        # Build else clause
        if statement.orelse:
            else_end = self._build_suite(
                statement.orelse,
                loop_exit_id,
                cfg,
                ctx,
                statement.orelse[0].lineno,
                statement.orelse[-1].end_lineno or statement.orelse[0].lineno,
            )
            final_exit = else_end if else_end else loop_exit_id
        else:
            final_exit = loop_exit_id

        # Pop loop context
        ctx.pop_loop()

        # Connect to fallthrough
        if fallthrough_id:
            self._add_edge(cfg, ctx, final_exit, fallthrough_id, 'next')
            return fallthrough_id
        return final_exit

    def _build_try(
        self,
        statement: ast.Try,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
        fallthrough_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build CFG for a try-except-finally statement."""
        # Create try body node
        try_body_id = ctx.generate_node_id()
        try_node = CFGNode(
            id=try_body_id,
            kind='statement',
            label='try',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='Try',
        )
        cfg.add_node(try_node)
        self._add_edge(cfg, ctx, incoming_id, try_body_id, 'next')

        # Create exception dispatch node
        dispatch_id = ctx.generate_node_id()
        dispatch_node = CFGNode(
            id=dispatch_id,
            kind='exception_dispatch',
            label='exception dispatch',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='Try',
        )
        cfg.add_node(dispatch_node)

        # Build try body
        if statement.body:
            body_end = self._build_suite(
                statement.body,
                try_body_id,
                cfg,
                ctx,
                statement.body[0].lineno,
                statement.body[-1].end_lineno or statement.body[0].lineno,
            )
            # Normal completion goes to dispatch
            if body_end:
                self._add_edge(cfg, ctx, body_end, dispatch_id, 'next')

        # Build exception handlers
        handler_join_id = ctx.generate_node_id()
        handler_join_node = CFGNode(
            id=handler_join_id,
            kind='join',
            label='handler join',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.end_lineno or statement.lineno,
            ast_kind='Try',
        )
        cfg.add_node(handler_join_node)

        for handler in statement.handlers:
            handler_id = ctx.generate_node_id()
            handler_type = ast.unparse(handler.type) if handler.type else 'Exception'
            handler_node = CFGNode(
                id=handler_id,
                kind='statement',
                label=f'except {handler_type}',
                function_id=ctx.function_id,
                file=ctx.file,
                start_line=handler.lineno,
                end_line=handler.end_lineno or handler.lineno,
                ast_kind='ExceptHandler',
            )
            cfg.add_node(handler_node)
            self._add_edge(cfg, ctx, dispatch_id, handler_id, 'exception')

            if handler.body:
                handler_end = self._build_suite(
                    handler.body,
                    handler_id,
                    cfg,
                    ctx,
                    handler.body[0].lineno,
                    handler.body[-1].end_lineno or handler.body[0].lineno,
                )
                if handler_end:
                    self._add_edge(cfg, ctx, handler_end, handler_join_id, 'next')

        # Build else clause (executed if no exception)
        if statement.orelse:
            else_end = self._build_suite(
                statement.orelse,
                dispatch_id,
                cfg,
                ctx,
                statement.orelse[0].lineno,
                statement.orelse[-1].end_lineno or statement.orelse[0].lineno,
            )
            if else_end:
                self._add_edge(cfg, ctx, else_end, handler_join_id, 'next')
        else:
            # No else: dispatch goes directly to join
            self._add_edge(cfg, ctx, dispatch_id, handler_join_id, 'next')

        # Build finally clause
        if statement.finalbody:
            finally_id = ctx.generate_node_id()
            finally_node = CFGNode(
                id=finally_id,
                kind='finally',
                label='finally',
                function_id=ctx.function_id,
                file=ctx.file,
                start_line=statement.finalbody[0].lineno,
                end_line=statement.finalbody[-1].end_lineno or statement.finalbody[0].lineno,
                ast_kind='Try',
            )
            cfg.add_node(finally_node)
            self._add_edge(cfg, ctx, handler_join_id, finally_id, 'finally')

            finally_end = self._build_suite(
                statement.finalbody,
                finally_id,
                cfg,
                ctx,
                statement.finalbody[0].lineno,
                statement.finalbody[-1].end_lineno or statement.finalbody[0].lineno,
            )
            final_exit = finally_end if finally_end else finally_id
        else:
            final_exit = handler_join_id

        # Connect to fallthrough
        if fallthrough_id:
            self._add_edge(cfg, ctx, final_exit, fallthrough_id, 'next')
            return fallthrough_id
        return final_exit

    def _build_with(
        self,
        statement: ast.With,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
        fallthrough_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build CFG for a with statement."""
        # Create with entry node
        with_id = ctx.generate_node_id()
        with_node = CFGNode(
            id=with_id,
            kind='statement',
            label='with',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='With',
        )
        cfg.add_node(with_node)
        self._add_edge(cfg, ctx, incoming_id, with_id, 'next')

        # Build with body
        if statement.body:
            body_end = self._build_suite(
                statement.body,
                with_id,
                cfg,
                ctx,
                statement.body[0].lineno,
                statement.body[-1].end_lineno or statement.body[0].lineno,
            )
            if fallthrough_id and body_end:
                self._add_edge(cfg, ctx, body_end, fallthrough_id, 'next')
                return fallthrough_id
            return body_end

        if fallthrough_id:
            self._add_edge(cfg, ctx, with_id, fallthrough_id, 'next')
            return fallthrough_id
        return with_id

    def _build_match(
        self,
        statement: ast.Match,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
        fallthrough_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build CFG for a match statement."""
        # Create match node
        match_id = ctx.generate_node_id()
        match_node = CFGNode(
            id=match_id,
            kind='condition',
            label='match',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='Match',
        )
        cfg.add_node(match_node)
        self._add_edge(cfg, ctx, incoming_id, match_id, 'next')

        # Create join node
        join_id = ctx.generate_node_id()
        join_node = CFGNode(
            id=join_id,
            kind='join',
            label='match join',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.end_lineno or statement.lineno,
            ast_kind='Match',
        )
        cfg.add_node(join_node)

        # Build each case
        for case in statement.cases:
            case_id = ctx.generate_node_id()
            pattern = ast.unparse(case.pattern) if hasattr(ast, 'unparse') else 'pattern'
            case_node = CFGNode(
                id=case_id,
                kind='condition',
                label=pattern,
                function_id=ctx.function_id,
                file=ctx.file,
                start_line=case.lineno,
                end_line=case.lineno,
                ast_kind='match_case',
                condition=pattern,
            )
            cfg.add_node(case_node)
            self._add_edge(cfg, ctx, match_id, case_id, 'next')

            if case.body:
                body_end = self._build_suite(
                    case.body,
                    case_id,
                    cfg,
                    ctx,
                    case.body[0].lineno,
                    case.body[-1].end_lineno or case.body[0].lineno,
                )
                if body_end:
                    self._add_edge(cfg, ctx, body_end, join_id, 'next')

        # Connect join to fallthrough
        if fallthrough_id:
            self._add_edge(cfg, ctx, join_id, fallthrough_id, 'next')
            return fallthrough_id
        return join_id

    def _build_return(
        self,
        statement: ast.Return,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
    ) -> Optional[str]:
        """Build CFG for a return statement."""
        return_id = ctx.generate_node_id()
        return_expr = ast.unparse(statement.value) if statement.value else 'None'
        return_node = CFGNode(
            id=return_id,
            kind='return',
            label=f'return {return_expr}',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='Return',
            condition=return_expr,
        )
        cfg.add_node(return_node)
        self._add_edge(cfg, ctx, incoming_id, return_id, 'return')
        # Return has no fallthrough
        return None

    def _build_raise(
        self,
        statement: ast.Raise,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
    ) -> Optional[str]:
        """Build CFG for a raise statement."""
        raise_id = ctx.generate_node_id()
        raise_expr = ast.unparse(statement.exc) if statement.exc else 'exception'
        raise_node = CFGNode(
            id=raise_id,
            kind='raise',
            label=f'raise {raise_expr}',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=statement.lineno,
            end_line=statement.lineno,
            ast_kind='Raise',
            condition=raise_expr,
        )
        cfg.add_node(raise_node)
        self._add_edge(cfg, ctx, incoming_id, raise_id, 'raise')
        # Raise has no fallthrough
        return None

    def _build_break(
        self,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
    ) -> Optional[str]:
        """Build CFG for a break statement."""
        loop_ctx = ctx.current_loop()
        if not loop_ctx:
            # Break outside loop - treat as statement
            break_id = ctx.generate_node_id()
            break_node = CFGNode(
                id=break_id,
                kind='statement',
                label='break',
                function_id=ctx.function_id,
                file=ctx.file,
                start_line=0,
                end_line=0,
                ast_kind='Break',
            )
            cfg.add_node(break_node)
            self._add_edge(cfg, ctx, incoming_id, break_id, 'next')
            return break_id

        break_id = ctx.generate_node_id()
        break_node = CFGNode(
            id=break_id,
            kind='statement',
            label='break',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=0,
            end_line=0,
            ast_kind='Break',
        )
        cfg.add_node(break_node)
        self._add_edge(cfg, ctx, incoming_id, break_id, 'next')
        self._add_edge(cfg, ctx, break_id, loop_ctx['break_target'], 'break')
        # Break has no fallthrough
        return None

    def _build_continue(
        self,
        incoming_id: str,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
    ) -> Optional[str]:
        """Build CFG for a continue statement."""
        loop_ctx = ctx.current_loop()
        if not loop_ctx:
            # Continue outside loop - treat as statement
            continue_id = ctx.generate_node_id()
            continue_node = CFGNode(
                id=continue_id,
                kind='statement',
                label='continue',
                function_id=ctx.function_id,
                file=ctx.file,
                start_line=0,
                end_line=0,
                ast_kind='Continue',
            )
            cfg.add_node(continue_node)
            self._add_edge(cfg, ctx, incoming_id, continue_id, 'next')
            return continue_id

        continue_id = ctx.generate_node_id()
        continue_node = CFGNode(
            id=continue_id,
            kind='statement',
            label='continue',
            function_id=ctx.function_id,
            file=ctx.file,
            start_line=0,
            end_line=0,
            ast_kind='Continue',
        )
        cfg.add_node(continue_node)
        self._add_edge(cfg, ctx, incoming_id, continue_id, 'next')
        self._add_edge(cfg, ctx, continue_id, loop_ctx['continue_target'], 'continue')
        # Continue has no fallthrough
        return None

    def _add_edge(
        self,
        cfg: ControlFlowGraph,
        ctx: BuildContext,
        source: str,
        target: str,
        kind: str,
        condition: Optional[str] = None,
    ) -> None:
        """Add an edge to the CFG."""
        edge_id = ctx.generate_edge_id()
        edge = CFGEdge(
            id=edge_id,
            source=source,
            target=target,
            kind=kind,
            condition=condition,
            evidence={'file': ctx.file},
        )
        cfg.add_edge(edge)

    def _get_last_added_node(self, cfg: ControlFlowGraph, ctx: BuildContext) -> Optional[CFGNode]:
        """Get the most recently added node."""
        if cfg.nodes:
            return cfg.nodes[-1]
        return None
