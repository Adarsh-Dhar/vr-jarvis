"""
Agent 6 - Data Flow Intelligence Tools
Understand how data moves through the entire application.
"""

from typing import Optional, List, Dict, Any
from google.adk.tools import ToolContext
from ._common import heuristic
from ._safe import safe
from ._common import abs_repo_path, heuristic
import ast
import hashlib
import re
from pathlib import Path


def _is_python_file(file_path: str) -> bool:
    return file_path.endswith('.py')


def _parse_python_ast(file_path: str) -> Optional[ast.AST]:
    try:
        content = abs_repo_path(file_path).read_text(encoding='utf-8')
        return ast.parse(content)
    except Exception:
        return None


class DefUseAnalyzer(ast.NodeVisitor):
    """AST visitor to collect definition-use chains within a function."""
    
    def __init__(self):
        self.definitions = {}  # variable -> {line, type}
        self.uses = []  # list of {variable, line, type}
        self.def_use_edges = []  # list of {from_var, to_var, line, kind}
    
    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.definitions[target.id] = {'line': node.lineno, 'type': 'assignment'}
                # Check if RHS is a variable (creating a data flow edge)
                if isinstance(node.value, ast.Name):
                    self.def_use_edges.append({
                        'from': node.value.id,
                        'to': target.id,
                        'line': node.lineno,
                        'kind': 'assignment'
                    })
        self.generic_visit(node)
    
    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Name):
            self.definitions[node.target.id] = {'line': node.lineno, 'type': 'augmented_assignment'}
            if isinstance(node.value, ast.Name):
                self.def_use_edges.append({
                    'from': node.value.id,
                    'to': node.target.id,
                    'line': node.lineno,
                    'kind': 'augmented'
                })
        self.generic_visit(node)
    
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.uses.append({'variable': node.id, 'line': node.lineno, 'type': 'load'})
        self.generic_visit(node)
    
    def visit_Call(self, node):
        # Track arguments passed to function calls
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            for i, arg in enumerate(node.args):
                if isinstance(arg, ast.Name):
                    self.def_use_edges.append({
                        'from': arg.id,
                        'to': f'{func_name}_param_{i}',
                        'line': node.lineno,
                        'kind': 'call_argument'
                    })
        self.generic_visit(node)
    
    def visit_Return(self, node):
        if node.value and isinstance(node.value, ast.Name):
            self.def_use_edges.append({
                'from': node.value.id,
                'to': 'return_value',
                'line': node.lineno,
                'kind': 'return'
            })
        self.generic_visit(node)



def _split_variable_id(variable_id):
    vid = str(variable_id or '').strip()
    sep = '#' if '#' in vid else ':'
    function_name, _, variable_name = vid.rpartition(sep)
    if not function_name or not variable_name:
        return None
    return function_name, variable_name


# ---------------------------------------------------------------------------
# Canonical analysis pipeline
#
# Every trace_* tool below is built on the same evidence base as
# build_data_flow_graph: the Python CFG, the def-use extractor and the
# reaching-definitions analysis in intelligence/dataflow/. Nothing here is a
# text search or a name guess; unresolved relationships are reported as such.

# The facts cache is keyed by everything that can change the analysis result:
# repository root, graph path and mtime, function id, file and a sha256 of the
# source. A stale entry can therefore never be served after a re-index, a
# repository switch or an edit.
_FACTS_CACHE = {}
_FACTS_CACHE_LIMIT = 500


def clear_facts_cache():
    """Drop every cached per-function analysis. Called when the active
    repository or its graph changes (store.activate, re-index, promotion)."""
    _FACTS_CACHE.clear()


def _facts_cache_key(ctx):
    from .. import config
    graph_path = getattr(config, 'GRAPH_PATH', None)
    graph_path = Path(graph_path) if graph_path else None
    mtime = graph_path.stat().st_mtime if graph_path and graph_path.exists() else 0.0
    source = ctx.get('source') or ''
    return (str(config.REPO_ROOT), str(graph_path), mtime,
            ctx['node'].get('id'), ctx['file'],
            hashlib.sha256(source.encode('utf-8')).hexdigest())


def _resolve_python_function(function_id):
    """Resolve a graph function id to its AST node. Returns (ctx, error)."""
    from ..intelligence.graph_engine.codegraph import codegraph
    from ..intelligence.parsers.python_ast import parse_python_module
    from ..intelligence.parsers.python_symbol_locator import find_function_ast

    graph = codegraph.load_current_graph()
    node = graph.get(function_id)
    if not node:
        return None, {'status': 'not_found', 'function_id': function_id,
                      'message': 'Function not found in graph'}
    file_path = node.get('file', '')
    if not _is_python_file(file_path):
        return None, {'status': 'not_applicable', 'function_id': function_id,
                      'message': 'Data flow analysis only implemented for Python'}
    try:
        source = abs_repo_path(file_path).read_text(encoding='utf-8')
        tree = parse_python_module(source, file_path)
    except Exception as e:
        return None, {'status': 'error', 'function_id': function_id, 'error': str(e)}
    symbol = {'id': node.get('id'), 'name': node.get('name'),
              'qualname': node.get('qualname'), 'file': file_path,
              'start': node.get('start'), 'end': node.get('end'),
              'kind': node.get('kind')}
    func_ast = find_function_ast(tree, symbol)
    if func_ast is None:
        simple = node.get('name') or (node.get('id', '').split('.')[-1] if node.get('id') else '')
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == simple:
                func_ast = n
                break
    if func_ast is None:
        return None, {'status': 'not_found', 'function_id': function_id,
                      'message': 'Function AST node not found'}
    return {'node': node, 'file': file_path, 'source': source, 'tree': tree,
            'func_ast': func_ast}, None


def _function_facts(function_id, use_cache=True):
    """Run CFG -> def/use extraction -> reaching definitions for one function.

    Returns (ctx, error). ctx carries facts, analysis, cfg, func_ast, file,
    source, node and function_id.
    """
    ctx, err = _resolve_python_function(function_id)
    if err:
        return None, err
    cache_key = _facts_cache_key(ctx) if use_cache else None
    if cache_key is not None and cache_key in _FACTS_CACHE:
        return _FACTS_CACHE[cache_key], None
    from ..intelligence.controlflow.python_cfg import PythonCFGBuilder
    from ..intelligence.dataflow.python_extractor import PythonDefUseExtractor
    from ..intelligence.dataflow.reaching_definitions import ReachingDefinitionsAnalyzer

    fid = ctx['node'].get('id') or '%s::%s' % (ctx['file'], ctx['func_ast'].name)
    artifact = PythonCFGBuilder().build_function(
        function_ast=ctx['func_ast'], function_id=fid,
        source=ctx['source'], file_path=ctx['file'])
    facts = PythonDefUseExtractor().extract_function(
        artifact=artifact, source=ctx['source'], file_path=ctx['file'])
    analysis = ReachingDefinitionsAnalyzer().analyze(artifact.graph, facts)
    if 'error' in analysis:
        return None, {'status': 'error', 'function_id': function_id,
                      'error': analysis['error']}
    ctx.update({'facts': facts, 'analysis': analysis, 'cfg': artifact.graph,
                'function_id': fid})
    if cache_key is not None:
        if len(_FACTS_CACHE) >= _FACTS_CACHE_LIMIT:
            _FACTS_CACHE.clear()
        _FACTS_CACHE[cache_key] = ctx
    return ctx, None


def _defs_by_id(ctx):
    return {d.id: d for d in ctx['facts'].definitions}


def _uses_by_id(ctx):
    return {u.id: u for u in ctx['facts'].uses}


def _reaching_pairs(ctx, variable=None):
    """(use, reaching definition) pairs from the reaching-definitions result,
    filtered to one binding. Same rule the DFG builder uses: a definition only
    reaches a use when their binding_key matches."""
    facts, analysis = ctx['facts'], ctx['analysis']
    defs = _defs_by_id(ctx)
    pairs = []
    for cfg_node_id, use_list in (analysis.get('node_uses') or {}).items():
        reaching = analysis.get('in_sets', {}).get(cfg_node_id, set())
        for use in use_list:
            if variable is not None and use.variable != variable:
                continue
            for def_id in reaching:
                d = defs.get(def_id)
                if d and d.binding_key == use.binding_key:
                    pairs.append((use, d))
    return pairs


def _def_out(d):
    return {'line': d.line, 'column': d.column, 'kind': d.kind,
            'expression': d.expression}


def _use_out(u):
    return {'line': u.line, 'column': u.column, 'expression': u.expression}


def _return_flows(ctx):
    """Definitions that reach each return statement, per the CFG return nodes."""
    cfg, analysis = ctx['cfg'], ctx['analysis']
    return_ids = {n.id for n in cfg.nodes if getattr(n, 'kind', None) == 'return'}
    defs = _defs_by_id(ctx)
    out = []
    for cfg_node_id, use_list in (analysis.get('node_uses') or {}).items():
        if cfg_node_id not in return_ids:
            continue
        reaching = analysis.get('in_sets', {}).get(cfg_node_id, set())
        for use in use_list:
            ds = [defs[i] for i in reaching
                  if i in defs and defs[i].binding_key == use.binding_key]
            out.append({'line': use.line, 'variable': use.variable,
                        'definitions': [_def_out(d) for d in ds]})
    return out


def _find_call_node(func_ast, line, column=None):
    """The ast.Call node at (line, column) inside a function AST, or None."""
    candidates = [n for n in ast.walk(func_ast)
                  if isinstance(n, ast.Call) and n.lineno == line]
    if not candidates:
        return None
    if column is not None:
        exact = [n for n in candidates if n.col_offset == column]
        if exact:
            return exact[0]
    return candidates[0] if len(candidates) == 1 else None


def _innermost_statement(func_ast, call_node):
    """The innermost statement (Assign/AnnAssign/AugAssign/Return/Expr/...) that
    contains call_node, or None."""
    best = None
    for node in ast.walk(func_ast):
        if node is call_node:
            continue
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign,
                                 ast.Return, ast.Expr, ast.If, ast.While,
                                 ast.For, ast.With, ast.Assert, ast.Raise)):
            continue
        if call_node in set(ast.walk(node)):
            span = (getattr(node, 'end_lineno', node.lineno) or node.lineno) - node.lineno
            key = (span, -(node.col_offset or 0))
            if best is None or key < best[0]:
                best = (key, node)
    return best[1] if best else None


def _caller_result_flows(ctx):
    """For every recorded call site of this function, find what the caller does
    with the return value. Built on the index's caller edges (graph.callers)
    plus the caller's own def-use facts and reaching definitions — no name
    search. Unresolvable call shapes are reported, never guessed."""
    from ..intelligence.graph_engine.codegraph import codegraph
    graph = codegraph.load_current_graph()

    callers = graph.callers(ctx['function_id'], depth=1,
                            include_possible=True, include_ambiguous=True)
    results, unresolved = [], []
    for caller in callers:
        entry = {'file': caller.get('file'), 'line': caller.get('line'),
                 'caller': caller.get('from'),
                 'edge_resolution': caller.get('resolution'),
                 'callsite_id': caller.get('callsite_id')}
        caller_id = caller.get('from')
        node = graph.get(caller_id) if caller_id else None
        if not node or not _is_python_file(node.get('file') or ''):
            unresolved.append({**entry, 'reason': 'caller is not a Python function'})
            continue
        caller_ctx, cerr = _function_facts(caller_id)
        if cerr:
            unresolved.append({**entry, 'reason': 'caller analysis failed: %s' % cerr.get('error')})
            continue
        call_node = _find_call_node(caller_ctx['func_ast'], caller.get('line'),
                                    caller.get('column'))
        if call_node is None:
            unresolved.append({**entry, 'reason': 'call node not found at recorded position'})
            continue
        stmt = _innermost_statement(caller_ctx['func_ast'], call_node)
        result = {'disposition': 'unresolved'}
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            assigned = sorted({n.id for t in targets for n in ast.walk(t)
                               if isinstance(n, ast.Name)})
            result = {'disposition': 'assigned', 'assigned_variables': assigned}
            # Subsequent uses: uses of the assigned variables, after the call,
            # reached by the definitions this statement created.
            def_line = stmt.lineno
            call_pos = (call_node.lineno, call_node.col_offset)
            uses_by_var = {}
            for use, d in _reaching_pairs(caller_ctx):
                if use.variable not in assigned:
                    continue
                if (use.line, use.column) <= call_pos:
                    continue
                if d.line != def_line:
                    continue
                uses_by_var.setdefault(use.variable, []).append(_use_out(use))
            result['subsequent_uses'] = {
                v: sorted(us, key=lambda x: (x['line'], x['column']))[:20]
                for v, us in uses_by_var.items()}
        elif isinstance(stmt, ast.Return):
            result = {'disposition': 'returned'}
        elif isinstance(stmt, ast.Expr) and stmt.value is call_node:
            result = {'disposition': 'expression_result_unused'}
        elif stmt is not None:
            result = {'disposition': 'nested_in_expression',
                      'context': ast.unparse(stmt)[:200] if hasattr(ast, 'unparse') else None}
        entry['result'] = result
        (results if result['disposition'] != 'unresolved' else unresolved).append(entry)
    return results, unresolved


@safe
def trace_variable_origin(variable_id: str, tool_context: ToolContext) -> dict:
    """Find where a variable's value originates, using CFG def-use facts and
    reaching definitions: the definitions that actually reach the variable's
    uses, plus whether the variable is a parameter."""
    try:
        parts = _split_variable_id(variable_id)
        if parts is None:
            return {
                'status': 'error',
                'error': 'Variable ID must be in format function:variable'
            }
        function_name, variable_name = parts

        ctx, err = _function_facts(function_name)
        if err:
            err['variable_id'] = variable_id
            return err

        facts = ctx['facts']
        defs = [d for d in facts.definitions if d.variable == variable_name]
        uses = [u for u in facts.uses if u.variable == variable_name]
        pairs = _reaching_pairs(ctx, variable_name)

        # Definitions that reach at least one use are the confirmed origins.
        pairs = _reaching_pairs(ctx, variable_name)
        reached_def_ids = {d.id for _u, d in pairs}
        origins = []
        seen = set()
        for d in defs:
            if d.id in seen:
                continue
            seen.add(d.id)
            origins.append({
                'file': d.file, 'line': d.line, 'column': d.column,
                'kind': d.kind, 'expression': d.expression,
                'reaches_use': d.id in reached_def_ids,
            })

        is_parameter = any(d.kind == 'parameter' for d in defs)
        if not defs and not uses:
            return {
                'status': 'not_found',
                'variable_id': variable_id,
                'message': 'Variable %s not found in function %s' % (variable_name, function_name)
            }

        # 'origin' is claimed only when exactly one definition reaches the
        # variable's uses. Multiple reaching definitions or none at all are
        # reported explicitly instead of silently picking the first.
        reaching = sorted(reached_def_ids)
        if len(reaching) == 1:
            origin_status = 'single'
            d0 = next((d for d in defs if d.id == reaching[0]), None)
            origin = ({'file': d0.file, 'line': d0.line, 'column': d0.column,
                       'kind': d0.kind, 'expression': d0.expression,
                       'reaches_use': True} if d0 else None)
        elif len(reaching) > 1:
            origin_status = 'multiple'
            origin = None
        else:
            origin_status = 'none'
            origin = None
        affected_uses = []
        if origin_status == 'multiple':
            by_use = {}
            for u, d in pairs:
                by_use.setdefault(u.id, set()).add(d.id)
            uses_by_id = _uses_by_id(ctx)
            for uid, dids in by_use.items():
                if len(dids) > 1:
                    u = uses_by_id.get(uid)
                    if u is not None:
                        affected_uses.append(_use_out(u))

        return {
            'status': 'ok',
            'variable_id': variable_id,
            'function_id': ctx['function_id'],
            'is_parameter': is_parameter,
            'origin': origin,
            'origin_status': origin_status,
            'origins': origins,
            'affected_uses': affected_uses,
            'use_count': len(uses),
            'evidence': 'CFG def-use facts + reaching definitions',
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_variable_usage(variable_id: str, tool_context: ToolContext) -> dict:
    """Find where a variable is used, with the definitions that reach each use
    (reaching-definitions analysis over the Python CFG)."""
    try:
        parts = _split_variable_id(variable_id)
        if parts is None:
            return {
                'status': 'error',
                'error': 'Variable ID must be in format function:variable'
            }
        function_name, variable_name = parts

        ctx, err = _function_facts(function_name)
        if err:
            err['variable_id'] = variable_id
            return err

        facts = ctx['facts']
        uses = [u for u in facts.uses if u.variable == variable_name]
        if not uses and not any(d.variable == variable_name for d in facts.definitions):
            return {
                'status': 'not_found',
                'variable_id': variable_id,
                'message': 'Variable %s not found in function %s' % (variable_name, function_name)
            }

        pairs = _reaching_pairs(ctx, variable_name)
        reaching_by_use = {}
        for use, d in pairs:
            reaching_by_use.setdefault(use.id, []).append(_def_out(d))

        use_list = []
        for u in sorted(uses, key=lambda x: (x.line, x.column)):
            entry = _use_out(u)
            entry['reached_by'] = reaching_by_use.get(u.id, [])
            use_list.append(entry)

        return {
            'status': 'ok',
            'variable_id': variable_id,
            'function_id': ctx['function_id'],
            'uses': use_list,
            'use_count': len(use_list),
            'evidence': 'CFG use nodes + reaching definitions'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_data_flow(function_id: str, tool_context: ToolContext) -> dict:
    """Visualize data flow using graph emission."""
    try:
        from .visualization_spatial_tools import _emit_command
        from ..intelligence.dataflow import dfg_to_unity_format

        # Build data-flow graph
        dfg_result = build_data_flow_graph(function_id, tool_context)

        if dfg_result.get('status') != 'ok':
            return dfg_result

        # Convert to Unity format
        from ..intelligence.dataflow.models import DataFlowGraph
        dfg_dict = dfg_result['graph']
        dfg = DataFlowGraph(
            function_id=dfg_dict['function_id'],
            file=dfg_dict['file'],
        )
        # Reconstruct nodes and edges from dict
        from ..intelligence.dataflow.models import DataFlowNode, DataFlowEdge
        for node_dict in dfg_dict['nodes']:
            node = DataFlowNode(**node_dict)
            dfg.add_node(node)
        for edge_dict in dfg_dict['edges']:
            edge = DataFlowEdge(**edge_dict)
            dfg.add_edge(edge)

        unity_graph = dfg_to_unity_format(dfg)

        # Emit the graph to Unity
        _emit_command(tool_context, 'show_graph',
                     nodes=unity_graph['nodes'],
                     edges=unity_graph['edges'],
                     title=f'Data Flow: {function_id}',
                     graph_type='data_flow')

        return {
            'status': 'ok',
            'function_id': function_id,
            'node_count': len(unity_graph['nodes']),
            'edge_count': len(unity_graph['edges']),
            'graph_type': 'data_flow'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_variable_modifications(
    variable_id: str,
    tool_context: ToolContext
) -> dict:
    """Track where a variable is modified. Writes are the def-use 'definition'
    facts for the variable (assignments, augmented assignments, for/with
    bindings, deletions); reads are its 'use' facts. Writes and reads are
    reported separately — a reference is never claimed as a write."""
    try:
        parts = _split_variable_id(variable_id)
        if parts is None:
            return {
                'status': 'error',
                'error': 'Variable ID must be in format function:variable'
            }
        function_name, variable_name = parts

        ctx, err = _function_facts(function_name)
        if err:
            err['variable_id'] = variable_id
            return err

        facts = ctx['facts']
        writes = sorted(
            (_def_out(d) for d in facts.definitions if d.variable == variable_name),
            key=lambda x: (x['line'], x['column']))
        reads = sorted(
            (_use_out(u) for u in facts.uses if u.variable == variable_name),
            key=lambda x: (x['line'], x['column']))

        if not writes and not reads:
            return {
                'status': 'not_found',
                'variable_id': variable_id,
                'message': 'Variable %s not found in function %s' % (variable_name, function_name)
            }

        return {
            'status': 'ok',
            'variable_id': variable_id,
            'function_id': ctx['function_id'],
            'writes': writes,
            'write_count': len(writes),
            'reads': reads,
            'read_count': len(reads),
            'evidence': 'AST-verified definition/use facts (writes vs reads distinguished)'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_parameter_flow(
    function_id: str,
    parameter: str,
    tool_context: ToolContext
) -> dict:
    """Track how a parameter flows through a function using def-use facts:
    every use of the parameter, the definitions that reach it, and the
    operations that consume it — ordered by source line."""
    try:
        ctx, err = _function_facts(function_id)
        if err:
            err['parameter'] = parameter
            return err

        facts = ctx['facts']
        param_defs = [d for d in facts.definitions
                      if d.kind == 'parameter' and d.variable == parameter]
        if not param_defs:
            return {
                'status': 'not_found',
                'function_id': function_id,
                'parameter': parameter,
                'message': 'Parameter %s not found in function' % parameter
            }

        binding_keys = {d.binding_key for d in param_defs}
        uses = [u for u in facts.uses if u.binding_key in binding_keys]
        use_ids = {u.id for u in uses}
        ops = [op for op in facts.operations
               if any(uid in use_ids for uid in op.input_use_ids)]
        uses_by_id = _uses_by_id(ctx)
        defs_by_id = _defs_by_id(ctx)

        flow = []
        for u in sorted(uses, key=lambda x: (x.line, x.column)):
            reached = []
            for cfg_node_id, use_list in (ctx['analysis'].get('node_uses') or {}).items():
                if u not in use_list:
                    continue
                for def_id in ctx['analysis'].get('in_sets', {}).get(cfg_node_id, set()):
                    d = defs_by_id.get(def_id)
                    if d and d.binding_key == u.binding_key:
                        reached.append(_def_out(d))
            consumers = []
            for op in ops:
                if u.id in op.input_use_ids:
                    consumers.append({
                        'line': op.line,
                        'operation': op.operation,
                        'expression': op.expression,
                        'produces': [defs_by_id[i].variable
                                     for i in op.output_definition_ids if i in defs_by_id],
                    })
            flow.append({'use': _use_out(u), 'reached_by': reached,
                         'consumed_by': consumers})

        return {
            'status': 'ok',
            'function_id': ctx['function_id'],
            'parameter': parameter,
            'parameter_definitions': [_def_out(d) for d in param_defs],
            'flow': flow,
            'use_count': len(uses),
            'evidence': 'def-use facts bound to the parameter binding_key'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_return_value_flow(
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Track where return values flow: which definitions reach each return
    statement (CFG return nodes + reaching definitions), then for every Python
    call site what the caller does with the result — assignment target and its
    subsequent uses. Unresolvable call shapes are reported as unresolved."""
    try:
        ctx, err = _function_facts(function_id)
        if err:
            return err

        call_sites, unresolved = _caller_result_flows(ctx)
        return {
            'status': 'ok',
            'function_id': ctx['function_id'],
            'return_flows': _return_flows(ctx),
            'call_sites': call_sites,
            'call_count': len(call_sites),
            'unresolved': unresolved,
            'evidence': 'CFG return nodes + AST call-site result tracking'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_transformations(
    variable_id: str,
    tool_context: ToolContext
) -> dict:
    """Track data transformations: the expression operations that consume the
    variable (def-use 'operation' facts), in source order, with the variables
    each operation produces."""
    try:
        parts = _split_variable_id(variable_id)
        if parts is None:
            return {
                'status': 'error',
                'error': 'Variable ID must be in format function:variable'
            }
        function_name, variable_name = parts

        ctx, err = _function_facts(function_name)
        if err:
            err['variable_id'] = variable_id
            return err

        facts = ctx['facts']
        use_ids = {u.id for u in facts.uses if u.variable == variable_name}
        defs_by_id = _defs_by_id(ctx)
        transformations = []
        for op in sorted(facts.operations, key=lambda o: (o.line, o.column)):
            if not any(uid in use_ids for uid in op.input_use_ids):
                continue
            transformations.append({
                'line': op.line,
                'column': op.column,
                'operation': op.operation,
                'expression': op.expression,
                'produces': [defs_by_id[i].variable
                             for i in op.output_definition_ids if i in defs_by_id],
            })

        return {
            'status': 'ok',
            'variable_id': variable_id,
            'function_id': ctx['function_id'],
            'transformations': transformations,
            'count': len(transformations),
            'evidence': 'def-use operation facts consuming the variable'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def _callee_name(expression):
    """Extract the dotted callee name from a call expression string."""
    try:
        tree = ast.parse(expression.strip(), mode='eval')
        node = tree.body
        if isinstance(node, ast.Call):
            node = node.func
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return '.'.join(reversed(parts)) if parts else None
    except Exception:
        m = re.match(r'\s*([A-Za-z_][\w.]*)\s*\(', expression or '')
        return m.group(1) if m else None


def _resolve_call_target(graph, ctx, op):
    """Resolve the callee of a Call operation through the index's call-site
    edges, matched on file, line and column. Never picks a first match:

    - exactly one target          -> {'status': 'resolved', 'node', 'node_id', 'edge'}
    - several candidate targets   -> {'status': 'ambiguous', 'candidates': [ids]}
    - no usable call-site edge    -> {'status': 'unresolved', 'reason': ...}
    """
    try:
        entries = graph.callees(ctx['function_id'], depth=1,
                                include_possible=True, include_ambiguous=True)
    except Exception:
        entries = []
    candidates = [e for e in entries
                  if e.get('file') == ctx['file'] and e.get('line') == op.line]
    if not candidates:
        return {'status': 'unresolved',
                'reason': 'no call-site edge recorded at %s:%s' % (ctx['file'], op.line)}
    col = getattr(op, 'column', None)
    exact = [e for e in candidates if col is not None and e.get('column') == col]
    if exact:
        candidates = exact
    elif len(candidates) > 1:
        return {'status': 'ambiguous',
                'candidates': sorted({e.get('to') for e in candidates if e.get('to')})}
    targets = []
    for e in candidates:
        t = e.get('to')
        if t and t not in targets:
            targets.append(t)
    if len(targets) > 1:
        return {'status': 'ambiguous', 'candidates': targets}
    if not targets:
        return {'status': 'unresolved', 'reason': 'call-site edge has no target'}
    node = graph.get(targets[0])
    if not node:
        return {'status': 'unresolved',
                'reason': 'call target %s not present in graph' % targets[0]}
    return {'status': 'resolved', 'node': node, 'node_id': targets[0],
            'edge': candidates[0]}


def _ops_by_id(ctx):
    return {o.id: o for o in ctx['facts'].operations}


def _expand_arg_uses(ctx, arg):
    """Every leaf use id contributed by one call_shape argument, following
    nested operation ids transitively (e.g. ``f(g(x))`` still finds ``x``)."""
    ops = _ops_by_id(ctx)
    use_ids = set(arg.get('use_ids') or [])
    seen, stack = set(), [arg.get('operation_id')]
    while stack:
        oid = stack.pop()
        if not oid or oid in seen:
            continue
        seen.add(oid)
        op = ops.get(oid)
        if op is None:
            continue
        use_ids.update(op.input_use_ids)
        stack.extend(op.input_operation_ids)
    return use_ids


@safe
def trace_cross_function_flow(
    variable_id: str,
    tool_context: ToolContext
) -> dict:
    """Track data across function boundaries for Python.

    Outbound edges: uses of the variable inside Call operations become
    argument->parameter edges. The callee is resolved through the index's
    call-site edges (file+line+column) and arguments are bound to formal
    parameters with call_binding — never by guessing a position. Inbound
    edges: call sites of this function are followed to the caller's result
    assignment and its subsequent uses. Anything that cannot be established
    is reported in 'unresolved' — a reference is never claimed as a confirmed
    flow edge."""
    try:
        from ..intelligence.dataflow.call_binding import bind_call
        parts = _split_variable_id(variable_id)
        if parts is None:
            return {
                'status': 'error',
                'error': 'Variable ID must be in format function:variable'
            }
        function_name, variable_name = parts

        ctx, err = _function_facts(function_name)
        if err:
            err['variable_id'] = variable_id
            return err

        from ..intelligence.graph_engine.codegraph import codegraph
        graph = codegraph.load_current_graph()
        facts = ctx['facts']
        var_use_ids = {u.id for u in facts.uses if u.variable == variable_name}

        outbound, unresolved = [], []
        for op in sorted(facts.operations, key=lambda o: (o.line, o.column)):
            if op.operation != 'Call':
                continue
            shape = (op.metadata or {}).get('call_shape') or {}
            # Uses of the variable contributed by any argument (the callee and
            # receiver are children of the Call op, not arguments, so their
            # uses never appear here).
            arg_use_sets = []
            for arg in (shape.get('positional') or []) + (shape.get('keywords') or []):
                arg_use_sets.append(_expand_arg_uses(ctx, arg))
            hits = [u for u in (_uses_by_id(ctx)[i] for i in sorted(var_use_ids))
                    if any(u.id in s for s in arg_use_sets)]
            if not hits:
                continue
            entry = {'line': op.line, 'expression': op.expression,
                     'variable': variable_name,
                     'callee_name': shape.get('callee') or _callee_name(op.expression or ''),
                     'argument_uses': [_use_out(u) for u in hits]}
            resolution = _resolve_call_target(graph, ctx, op)
            if resolution['status'] == 'ambiguous':
                unresolved.append({**entry, 'reason': 'ambiguous callee',
                                   'candidates': resolution['candidates']})
                continue
            if resolution['status'] != 'resolved':
                unresolved.append({**entry,
                                   'reason': resolution.get('reason') or 'callee unresolved'})
                continue
            callee_node = resolution['node']
            callee_ctx, cerr = _function_facts(callee_node.get('id'))
            if cerr:
                unresolved.append({**entry,
                                   'reason': 'callee analysis failed: %s' % cerr.get('error')})
                continue
            is_method = callee_node.get('kind') == 'method'
            binding = bind_call(shape, callee_ctx['func_ast'], is_method=is_method)
            param_defs = {d.variable: d for d in callee_ctx['facts'].definitions
                          if d.kind == 'parameter'}
            hit_ids = {u.id for u in hits}
            bound_hit_ids = set()
            for b in binding['bindings']:
                if b['status'] != 'bound':
                    continue
                b_uses = _expand_arg_uses(
                    ctx, {'use_ids': b.get('use_ids'), 'operation_id': b.get('operation_id')})
                matched = [u for u in hits if u.id in b_uses]
                if not matched:
                    continue
                pd = param_defs.get(b['param'])
                for u in matched:
                    bound_hit_ids.add(u.id)
                    outbound.append({
                        'caller_function': ctx['function_id'],
                        'argument': {'variable': variable_name, 'line': u.line},
                        'call_line': op.line,
                        'callee': callee_ctx['function_id'],
                        'parameter': {'name': b['param'],
                                      'line': pd.line if pd else None},
                        'resolution': 'confirmed',
                    })
            for u in hits:
                if u.id not in bound_hit_ids:
                    unresolved.append({**entry,
                                       'reason': 'argument use %s did not bind to a parameter' % u.id,
                                       'argument_uses': [_use_out(u)]})

        call_sites, ret_unresolved = _caller_result_flows(ctx)
        return {
            'status': 'ok',
            'variable_id': variable_id,
            'function_id': ctx['function_id'],
            'outbound_argument_edges': outbound,
            'inbound_return_edges': call_sites,
            'unresolved': unresolved + ret_unresolved,
            'evidence': 'def-use call operations + call-site edge callee resolution + call_shape binding'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


_FILE_READ_ATTRS = {'read', 'readline', 'readlines'}
_FILE_WRITE_ATTRS = {'write', 'writelines'}
_FILE_OPEN_NAMES = {'open'}


def _call_name(node):
    f = node.func
    if isinstance(f, ast.Name):
        return f.id, None
    if isinstance(f, ast.Attribute):
        return f.attr, f
    return None, None


def _assigned_names(target):
    return [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]


_FILE_READ_ATTRS = {'read', 'readline', 'readlines'}
_FILE_WRITE_ATTRS = {'write', 'writelines'}
_FILE_OPEN_NAMES = {'open', 'io.open'}


def _call_attr(op):
    """(receiver, attr) for a Call operation's callee, from its expression."""
    expr = op.expression or ''
    try:
        tree = ast.parse(expr.strip(), mode='eval')
        node = tree.body
        if isinstance(node, ast.Call):
            node = node.func
        if isinstance(node, ast.Attribute):
            recv = ast.unparse(node.value) if hasattr(ast, 'unparse') else ''
            return recv, node.attr
        if isinstance(node, ast.Name):
            return '', node.id
    except Exception:
        pass
    m = re.match(r'\s*([A-Za-z_][\w.]*)\s*\(', expr)
    if m:
        name = m.group(1)
        if '.' in name:
            recv, _, attr = name.rpartition('.')
            return recv, attr
        return '', name
    return '', None


def _reaching_defs_by_use(ctx):
    """use_id -> [Definition] reaching it (binding-key matched)."""
    out = {}
    for use, d in _reaching_pairs(ctx):
        out.setdefault(use.id, []).append(d)
    return out


def _def_producing_op(ctx):
    """definition_id -> ExpressionFact that produced it (via output_definition_ids)."""
    out = {}
    for op in ctx['facts'].operations:
        for did in op.output_definition_ids:
            out[did] = op
    return out


def _is_open_call(ctx, op):
    _recv, attr = _call_attr(op)
    if attr in _FILE_OPEN_NAMES:
        return True
    return (op.expression or '').strip().startswith('open(')


def _is_read_call(op):
    _recv, attr = _call_attr(op)
    return attr in _FILE_READ_ATTRS


def _is_write_call(op):
    _recv, attr = _call_attr(op)
    return attr in _FILE_WRITE_ATTRS


def _receiver_use(ctx, op, receiver):
    """The VariableUse inside op that reads the call receiver.

    Receiver uses live inside the func/attribute operation, not necessarily in
    the Call op's own input_use_ids, so the operation closure is searched."""
    if not receiver:
        return None
    uses_by_id = _uses_by_id(ctx)
    ops = _ops_by_id(ctx)
    candidate_ids = list(op.input_use_ids)
    seen, stack = set(), list(op.input_operation_ids)
    while stack:
        oid = stack.pop()
        if oid in seen:
            continue
        seen.add(oid)
        inner = ops.get(oid)
        if inner is None:
            continue
        candidate_ids.extend(inner.input_use_ids)
        stack.extend(inner.input_operation_ids)
    for uid in candidate_ids:
        u = uses_by_id.get(uid)
        if u is not None and u.variable == receiver:
            return u
    # attribute receivers show up as 'obj.attr' uses
    for uid in candidate_ids:
        u = uses_by_id.get(uid)
        if u is not None and u.variable.endswith('.' + receiver):
            return u
    return None


def _file_op_sources(ctx):
    """Per-function file-operation facts.

    Returns (handles, reads, sinks, notes):
    - handles: definition ids bound to open() results (reported as handles,
      never as data sources)
    - reads:   {'def_id', 'op', 'variable'} read-call results and handle
      iterations
    - sinks:   write/writelines Call ops
    """
    ops = ctx['facts'].operations
    defs = _defs_by_id(ctx)
    prod = _def_producing_op(ctx)
    reaching = _reaching_defs_by_use(ctx)

    handles, reads, sinks = set(), [], []
    handle_expr = {}

    for op in ops:
        if op.operation != 'Call':
            continue
        if _is_open_call(ctx, op):
            for did in op.output_definition_ids:
                handles.add(did)
                handle_expr[did] = op
            # `with open(...) as f` / `for x in open(...)`: the binding def is
            # created by the with/for statement on the same line, not linked
            # through output_definition_ids.
            for d in ctx['facts'].definitions:
                if d.id in handles or d.line != op.line:
                    continue
                if d.kind in ('with_binding', 'for_loop', 'for_loop_unpack',
                              'assignment', 'annotated_assignment',
                              'named_expression'):
                    # only claim the binding when the open call is part of the
                    # same statement's expression
                    if op.expression and op.expression.split('(')[0] in ('open', 'io.open'):
                        handles.add(d.id)
                        handle_expr[d.id] = op
        elif _is_read_call(op):
            reads.append({'op': op, 'def_ids': list(op.output_definition_ids)})
        elif _is_write_call(op):
            sinks.append(op)

    # Handle iteration: `for line in handle:` — the for-target definition is a
    # read source when the iterated expression reaches a handle definition.
    for d in ctx['facts'].definitions:
        if not d.kind.startswith('for_loop'):
            continue
        for uid, rdefs in reaching.items():
            u = _uses_by_id(ctx).get(uid)
            if u is None or u.line != d.line:
                continue
            if any(rd.id in handles for rd in rdefs):
                reads.append({'op': None, 'def_ids': [d.id],
                              'iteration': True,
                              'variable': d.variable, 'line': d.line})
                break

    return handles, reads, sinks, prod, reaching


def _def_file_sources(ctx, def_id, handles, reads_by_def, prod, reaching,
                      _seen=None, _depth=0):
    """The read-sources that reach a definition, following copies and
    intermediate expressions through reaching definitions. Returns a list of
    source descriptors; empty when the definition is not file-derived."""
    if _seen is None:
        _seen = set()
    if def_id in _seen or _depth > 6:
        return []
    _seen.add(def_id)
    if def_id in handles:
        return []  # a handle is not file content
    sources = []
    if def_id in reads_by_def:
        r = reads_by_def[def_id]
        sources.append({'kind': 'source', 'operation': 'read',
                        'line': r.get('line') or (r['op'].line if r.get('op') else None),
                        'expression': (r['op'].expression if r.get('op') else None),
                        'variable': r.get('variable')})
    op = prod.get(def_id)
    if op is not None and op.operation == 'Call' and _is_read_call(op):
        if not sources:
            sources.append({'kind': 'source', 'operation': 'read',
                            'line': op.line, 'expression': op.expression,
                            'variable': None})
    # Propagate through whatever produced the definition: the operation's
    # input uses (e.g. `b = a`) or an explicit copy link.
    next_use_ids = []
    if op is not None:
        next_use_ids.extend(op.input_use_ids)
    d = _defs_by_id(ctx).get(def_id)
    if d is not None:
        meta = d.metadata or {}
        if meta.get('source_use_id'):
            next_use_ids.append(meta['source_use_id'])
    for uid in next_use_ids:
        for rd in reaching.get(uid, []):
            sources.extend(_def_file_sources(ctx, rd.id, handles, reads_by_def,
                                             prod, reaching, _seen, _depth + 1))
    # de-dup
    uniq, seen = [], set()
    for s in sources:
        key = (s.get('operation'), s.get('line'), s.get('variable'))
        if key not in seen:
            seen.add(key)
            uniq.append(s)
    return uniq


@safe
def trace_file_operations(
    file_path: str,
    tool_context: ToolContext
) -> dict:
    """Track data through file operations on the canonical CFG + reaching
    definitions (Python files).

    open() results are reported as handles, never as data sources. Read calls
    (read/readline/readlines) and handle iteration are sources; write calls
    (write/writelines) are sinks. A source->sink relationship is reported only
    when reaching definitions prove read content reaches the write — including
    propagation through intermediate variables and inline ``f.write(g.read())``.
    Overwritten variables produce no flow because reaching definitions kill the
    earlier definition. Non-Python files return not_applicable."""
    try:
        from ._common import repo_root
        from ..intelligence.graph_engine.codegraph import codegraph
        p = Path(str(file_path))
        if not p.is_absolute():
            p = repo_root() / p
        if not _is_python_file(str(p)):
            return {
                'status': 'not_applicable',
                'file_path': str(file_path),
                'message': 'File-operation data-flow analysis is implemented for Python only'
            }
        if not p.is_file():
            return {'status': 'not_found', 'file_path': str(file_path),
                    'message': 'File not found'}

        graph = codegraph.load_current_graph()
        rel = str(p.relative_to(repo_root())) if str(p).startswith(str(repo_root())) else str(p)
        nodes = [n for n in graph.nodes_in_file(rel)
                 if n.get('kind') in ('function', 'method')]
        if not nodes:
            return {'status': 'not_found', 'file_path': rel,
                    'message': 'No functions found for this file in the graph'}

        operations, flows = [], []
        skipped = []
        for node in sorted(nodes, key=lambda n: (n.get('start') or 0)):
            scope = node.get('qualname') or node.get('name') or node.get('id')
            ctx, err = _function_facts(node.get('id'))
            if err:
                skipped.append({'function': scope, 'reason': err.get('error') or err.get('message')})
                continue
            handles, reads, sinks, prod, reaching = _file_op_sources(ctx)
            defs = _defs_by_id(ctx)
            reads_by_def = {}
            for r in reads:
                for did in r['def_ids']:
                    reads_by_def[did] = r

            for did in sorted(handles):
                d = defs.get(did)
                operations.append({
                    'kind': 'handle', 'operation': 'open',
                    'function': scope, 'line': d.line if d else None,
                    'variable': d.variable if d else None})
            for r in reads:
                d = defs.get(r['def_ids'][0]) if r['def_ids'] else None
                operations.append({
                    'kind': 'source', 'operation': 'read',
                    'function': scope,
                    'line': r.get('line') or (r['op'].line if r.get('op') else (d.line if d else None)),
                    'variable': r.get('variable') or (d.variable if d else None),
                    'iteration': bool(r.get('iteration'))})
            for op in sinks:
                recv, attr = _call_attr(op)
                operations.append({
                    'kind': 'sink', 'operation': attr or 'write',
                    'function': scope, 'line': op.line,
                    'receiver': recv or None})
                # Uses contributed by each argument (receiver excluded).
                shape = (op.metadata or {}).get('call_shape') or {}
                arg_uses = []
                for arg in (shape.get('positional') or []) + (shape.get('keywords') or []):
                    arg_uses.extend(_expand_arg_uses(ctx, arg))
                # Inline read inside the write call: f.write(g.read()).
                inline_reads = []
                for arg in (shape.get('positional') or []) + (shape.get('keywords') or []):
                    seen_ops, stack = set(), [arg.get('operation_id')]
                    while stack:
                        oid = stack.pop()
                        if not oid or oid in seen_ops:
                            continue
                        seen_ops.add(oid)
                        inner = _ops_by_id(ctx).get(oid)
                        if inner is None:
                            continue
                        if inner.operation == 'Call' and _is_read_call(inner):
                            inline_reads.append(inner)
                        stack.extend(inner.input_operation_ids)
                found = set()
                for inner in inline_reads:
                    irecv, _ = _call_attr(inner)
                    iuse = _receiver_use(ctx, inner, irecv)
                    idefs = reaching.get(iuse.id, []) if iuse else []
                    if any(d.id in handles for d in idefs):
                        key = ('inline', inner.line, inner.expression)
                        found.add(key)
                        flows.append({
                            'from': {'kind': 'source', 'operation': 'read',
                                     'line': inner.line, 'expression': inner.expression,
                                     'function': scope},
                            'to': {'kind': 'sink', 'operation': attr or 'write',
                                   'line': op.line, 'function': scope},
                            'resolution': 'confirmed'})
                for uid in arg_uses:
                    for d in reaching.get(uid, []):
                        for s in _def_file_sources(ctx, d.id, handles, reads_by_def,
                                                   prod, reaching):
                            key = (s.get('operation'), s.get('line'), s.get('variable'), uid)
                            if key in found:
                                continue
                            found.add(key)
                            flows.append({
                                'from': {'kind': 'source', **{k: v for k, v in s.items() if v is not None},
                                         'function': scope},
                                'to': {'kind': 'sink', 'operation': attr or 'write',
                                       'line': op.line, 'function': scope},
                                'resolution': 'confirmed'})

        return {
            'status': 'ok',
            'file_path': rel,
            'operations': operations,
            'data_relationships': flows,
            'source_count': sum(1 for o in operations if o['kind'] == 'source'),
            'sink_count': sum(1 for o in operations if o['kind'] == 'sink'),
            'handle_count': sum(1 for o in operations if o['kind'] == 'handle'),
            'skipped_functions': skipped,
            'evidence': 'canonical CFG + reaching definitions; open() reported as handle, '
                        'source->sink only when read data provably reaches a write'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


_MUTATING_METHODS = {'append', 'extend', 'update', 'add', 'pop', 'remove',
                     'discard', 'clear', 'setdefault', 'push', 'splice',
                     'dispatch', 'emit', 'setState', 'assign'}


@safe
def trace_state_changes(
    component_id: str,
    tool_context: ToolContext
) -> dict:
    """Track state mutations with AST evidence (Python files).

    Mutations are attribute/subscript writes, deletions of attributes or
    subscripts, and calls to known mutating methods. Each entry names the
    target expression, the enclosing function and the affected base variable.
    Non-Python targets return not_applicable — no pattern-search claims."""
    try:
        from ._common import repo_root
        from ..intelligence.graph_engine.codegraph import codegraph

        # Resolve component_id to a file: graph node first, then a repo path.
        # CodeGraph has no items(); resolve() handles id/name/qualname lookups.
        file_path = None
        graph = codegraph.load_current_graph()
        node = None
        try:
            res = graph.resolve(component_id)
            if res.get('status') == 'ok':
                node = res.get('node')
        except Exception:
            node = None
        if node is None:
            node = graph.get(component_id)
        if node and node.get('file'):
            file_path = node['file']
        if not file_path:
            p = Path(str(component_id))
            if not p.is_absolute():
                p = repo_root() / p
            if p.is_file():
                file_path = str(p)
        if not file_path:
            return {'status': 'not_found', 'component_id': component_id,
                    'message': 'Component or file not found'}
        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'component_id': component_id,
                'file': file_path,
                'message': 'State-change analysis is implemented for Python only'
            }

        tree = ast.parse(abs_repo_path(file_path).read_text(encoding='utf-8', errors='replace'))
        mutations = []

        def _target_info(t):
            if isinstance(t, ast.Attribute):
                base = t.value.id if isinstance(t.value, ast.Name) else None
                return 'attribute_write', ast.unparse(t), base
            if isinstance(t, ast.Subscript):
                base = t.value.id if isinstance(t.value, ast.Name) else None
                return 'subscript_write', ast.unparse(t), base
            return None, None, None

        def _record(node_ast, scope):
            if isinstance(node_ast, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node_ast.targets if isinstance(node_ast, ast.Assign) else [node_ast.target]
                for t in targets:
                    kind, expr, base = _target_info(t)
                    if kind:
                        mutations.append({'kind': kind, 'target': expr,
                                          'affected_variable': base,
                                          'function': scope, 'line': node_ast.lineno})
            elif isinstance(node_ast, ast.Delete):
                for t in node_ast.targets:
                    kind, expr, base = _target_info(t)
                    if kind:
                        mutations.append({'kind': 'delete', 'target': expr,
                                          'affected_variable': base,
                                          'function': scope, 'line': node_ast.lineno})
            elif isinstance(node_ast, ast.Call):
                cname, _ = _call_name(node_ast)
                if cname in _MUTATING_METHODS:
                    recv = ast.unparse(node_ast.func.value) if isinstance(node_ast.func, ast.Attribute) else ''
                    mutations.append({'kind': 'method_mutation', 'method': cname,
                                      'target': recv, 'affected_variable': recv.split('.')[0] or None,
                                      'function': scope, 'line': node_ast.lineno})

        def _walk_scope(body, qualname):
            """Collect mutations in one scope without entering nested function
            or class bodies, then recurse so each operation is attributed once
            to the innermost (dotted-qualname) scope."""
            for stmt in body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    _walk_scope(stmt.body,
                                '%s.%s' % (qualname, stmt.name) if qualname else stmt.name)
                    continue
                stack = [stmt]
                while stack:
                    node_ast = stack.pop()
                    if isinstance(node_ast, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        continue
                    _record(node_ast, qualname or '<module>')
                    stack.extend(ast.iter_child_nodes(node_ast))

        _walk_scope(tree.body, '')
        mutations.sort(key=lambda m: (m['function'], m['line']))
        return {
            'status': 'ok',
            'component_id': component_id,
            'file': file_path,
            'state_changes': mutations,
            'count': len(mutations),
            'evidence': 'AST mutation analysis (attribute/subscript writes, deletes, mutating calls)'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def build_data_flow_graph(
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Build data flow graphs using the new data-flow engine."""
    try:
        from ..intelligence.graph_engine.codegraph import codegraph
        from ..intelligence.dataflow.service import analyze_python_data_flow

        # Resolve the function
        graph = codegraph.load_current_graph()
        node = graph.get(function_id)

        if not node:
            return {
                'status': 'not_found',
                'function_id': function_id,
                'message': 'Function not found in graph'
            }

        file_path = node.get('file', '')
        if not file_path:
            return {
                'status': 'error',
                'error': 'Node has no file path'
            }

        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'function_id': function_id,
                'message': 'Data flow analysis only implemented for Python'
            }

        # Read source code
        with open(abs_repo_path(file_path), 'r', encoding='utf-8') as f:
            source = f.read()

        # Call the data-flow service
        symbol = {
            'id': node.get('id'),
            'name': node.get('name'),
            'qualname': node.get('qualname'),
            'file': file_path,
            'source': source,
            'start': node.get('start'),
            'end': node.get('end'),
            'kind': node.get('kind'),
        }

        result = analyze_python_data_flow(graph, symbol)

        if 'error' in result:
            return {
                'status': 'error',
                'error': result['error'],
                'function_id': function_id,
            }

        return {
            'status': 'ok',
            'function_id': function_id,
            'graph': result['graph'].to_dict(),
            'validation': result['validation'],
            'diagnostics': result['diagnostics'],
            'metadata': result['metadata'],
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'function_id': function_id,
        }


        # Read source
        with open(abs_repo_path(file_path), 'r', encoding='utf-8') as f:
            source = f.read()

        # Build CFG
        cfg_builder = PythonCFGBuilder()
        cfg = cfg_builder.build_function(
            function_ast=func_node,
            function_id=node.get('id', function_id),
            source=source,
            file_path=file_path
        )

        # Extract definition/use facts
        def_use_extractor = PythonDefUseExtractor()
        facts = def_use_extractor.extract_function(
            function_ast=func_node,
            function_id=node.get('id', function_id),
            source=source
        )

        # Perform reaching definitions analysis
        reaching_analyzer = ReachingDefinitionsAnalyzer()
        analysis_result = reaching_analyzer.analyze(cfg, facts)

        # Build data-flow graph
        dfg_builder = DataFlowGraphBuilder()
        dfg = dfg_builder.build(cfg, facts, analysis_result)

        return {
            'status': 'ok',
            'function_id': function_id,
            'graph': dfg.to_dict(),
            'definition_count': len(facts.definitions),
            'use_count': len(facts.uses),
            'node_count': len(dfg.nodes),
            'edge_count': len(dfg.edges),
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

