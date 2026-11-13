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
import os
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
    func_ast, amb = _select_function_ast(tree, node, file_path)
    if amb is not None:
        return None, amb
    if func_ast is None:
        return None, {'status': 'not_found', 'function_id': function_id,
                      'message': 'Function AST node not found'}
    return {'node': node, 'file': file_path, 'source': source, 'tree': tree,
            'func_ast': func_ast}, None


def _function_candidates(tree):
    """All function defs in the module as (qualified_name, node) pairs,
    where the qualified name includes enclosing class/function scopes."""
    out = []

    def visit(node, scope):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = '.'.join(scope + [ch.name])
                out.append((q, ch))
                visit(ch, scope + [ch.name])
            elif isinstance(ch, ast.ClassDef):
                visit(ch, scope + [ch.name])
            else:
                visit(ch, scope)

    visit(tree, [])
    return out


def _select_function_ast(tree, node, file_path):
    """Pick the AST node for a graph function node.

    Order: (1) find_function_ast exact match; (2) candidates whose qualified
    name equals the node's qualname; (3) among those, the one whose lineno
    equals node['start']. Exactly one survivor is returned; several yields an
    'ambiguous' error dict; none yields (None, None) -> not_found upstream.
    Returns (func_ast, error_dict_or_None)."""
    from ..intelligence.parsers.python_symbol_locator import find_function_ast

    symbol = {'id': node.get('id'), 'name': node.get('name'),
              'qualname': node.get('qualname'), 'file': file_path,
              'start': node.get('start'), 'end': node.get('end'),
              'kind': node.get('kind')}
    func_ast = find_function_ast(tree, symbol)
    if func_ast is not None:
        return func_ast, None

    qualname = node.get('qualname')
    candidates = _function_candidates(tree)
    matched = [(q, n) for q, n in candidates
               if qualname and q == qualname]
    if not matched:
        return None, None
    start = node.get('start')
    if start is not None:
        by_line = [(q, n) for q, n in matched
                   if getattr(n, 'lineno', None) == start]
        if by_line:
            matched = by_line
    if len(matched) == 1:
        return matched[0][1], None
    return None, {'status': 'ambiguous', 'function_id': node.get('id'),
                  'message': 'Multiple functions match %r in %s' % (
                      qualname, file_path),
                  'candidates': ['%s:%s' % (q, getattr(n, 'lineno', '?'))
                                 for q, n in matched]}


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


def _classify_targets(targets):
    """Split assignment targets into plain variables, attribute writes,
    subscript writes and anything unsupported. Only plain variables get
    downstream use tracing; attribute/subscript targets are reported as
    text because their base object or index is not the assigned value."""
    out = {'variables': [], 'attributes': [], 'subscripts': [], 'unsupported': []}

    def visit(t):
        if isinstance(t, ast.Name):
            out['variables'].append(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                visit(e)
        elif isinstance(t, ast.Starred):
            visit(t.value)
        elif isinstance(t, ast.Attribute):
            out['attributes'].append(ast.unparse(t))
        elif isinstance(t, ast.Subscript):
            out['subscripts'].append(ast.unparse(t))
        else:
            out['unsupported'].append(type(t).__name__)

    for t in targets:
        visit(t)
    return out


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
        # Only a statically confirmed call edge may produce a confirmed
        # return-flow edge; possible/ambiguous callers go to unresolved.
        if not _edge_is_confirmed(caller):
            unresolved.append({**entry,
                               'reason': 'caller edge is %s, not statically confirmed'
                                         % (caller.get('resolution') or caller.get('kind')),
                               'candidates': caller.get('candidates')})
            continue
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
        # Only an assignment whose value IS this call binds the return value.
        # `x = wrap(calc())` leaves calc()'s result nested inside wrap's
        # argument — that falls through to nested_in_expression below.
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)) \
                and getattr(stmt, 'value', None) is call_node:
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            cls = _classify_targets(targets)
            if cls['unsupported']:
                result = {'disposition': 'unresolved',
                          'reason': 'unsupported target: ' + ', '.join(cls['unsupported'])}
            else:
                unpacked = any(isinstance(t, (ast.Tuple, ast.List)) for t in targets)
                result = {'disposition': 'unpacked' if unpacked else 'assigned',
                          'assigned_variables': sorted(set(cls['variables'])),
                          'assigned_attributes': cls['attributes'],
                          'assigned_subscripts': cls['subscripts'],
                          'augmented': isinstance(stmt, ast.AugAssign)}
                notes = []
                if unpacked:
                    notes.append('return value is distributed across unpacked '
                                 'elements; each name possibly receives it')
                if cls['attributes'] or cls['subscripts']:
                    notes.append('downstream uses of attribute/subscript targets '
                                 'are not traced')
                if notes:
                    result['note'] = '; '.join(notes)
                # Subsequent uses: uses of the assigned plain variables, after
                # the call, reached by the definitions this statement created.
                def_line = stmt.lineno
                call_pos = (call_node.lineno, call_node.col_offset)
                var_set = set(cls['variables'])
                uses_by_var = {}
                for use, d in _reaching_pairs(caller_ctx):
                    if use.variable not in var_set:
                        continue
                    if (use.line, use.column) <= call_pos:
                        continue
                    if d.line != def_line:
                        continue
                    uses_by_var.setdefault(use.variable, []).append(_use_out(use))
                result['subsequent_uses'] = {
                    v: sorted(us, key=lambda x: (x['line'], x['column']))[:20]
                    for v, us in uses_by_var.items()}
                # Narrow attribute/subscript propagation (no alias analysis).
                attr_sub = _attribute_subscript_uses(
                    caller_ctx, cls['attributes'], cls['subscripts'],
                    call_pos)
                if attr_sub:
                    result['attribute_subscript_uses'] = attr_sub
        elif isinstance(stmt, ast.Return):
            result = {'disposition': 'returned'}
        elif isinstance(stmt, ast.Expr) and stmt.value is call_node:
            result = {'disposition': 'expression_result_unused'}
        elif stmt is not None:
            result = _expression_path_result(stmt, call_node,
                                             caller_ctx, MAX_EXPR_HOPS)
        entry['result'] = result
        (results if result['disposition'] != 'unresolved' else unresolved).append(entry)
    return results, unresolved


def _access_path(target):
    """Access-path string for an attribute/subscript target, or None when it
    is not a plain Name base with at most constant subscripts (depth <= 2)."""
    try:
        parts = []
        node = target
        depth = 0
        while isinstance(node, (ast.Attribute, ast.Subscript)):
            depth += 1
            if depth > 2:
                return None
            if isinstance(node, ast.Attribute):
                parts.append('.' + node.attr)
                node = node.value
            else:
                sl = node.slice
                if isinstance(sl, ast.Constant) and isinstance(
                        sl.value, (str, int)):
                    parts.append('[%r]' % sl.value)
                else:
                    return None
                node = node.value
        if isinstance(node, ast.Name):
            return node.id + ''.join(reversed(parts))
    except Exception:
        return None
    return None


def _attribute_subscript_uses(ctx, attributes, subscripts, after_pos):
    """Scan later uses of recorded attribute/subscript targets.

    Reports {'precision': 'partial', 'access_path', 'uses',
    'stopped_because'} per resolvable path; unresolved paths get a reason.
    Stops at a reassignment of the base name or a call receiving the base
    object (possible mutation)."""
    out = []
    uses = sorted(ctx['facts'].uses,
                   key=lambda u: (u.line, u.column))
    defs = ctx['facts'].definitions
    ops = ctx['facts'].operations
    for raw in list(attributes) + list(subscripts):
        try:
            target = ast.parse(raw, mode='eval').body \
                if isinstance(raw, str) else raw
        except Exception:
            target = None
        path = _access_path(target) if target is not None else None
        if path is None:
            out.append({'access_path': None, 'precision': 'unresolved',
                        'reason': 'non-constant or deep access path'})
            continue
        base = path.split('.')[0].split('[')[0]
        is_param = any(d.variable == base and d.kind == 'parameter'
                       for d in defs)
        is_global = any((d.metadata or {}).get('is_global')
                        and d.variable == base for d in defs)
        if is_param or is_global:
            out.append({'access_path': path, 'precision': 'unresolved',
                        'reason': 'base is a parameter or global'})
            continue
        hits, stopped = [], None
        for u in uses:
            if (u.line, u.column) <= after_pos:
                continue
            if u.variable != path:
                continue
            # Reassignment of the base name kills the path.
            if any(d.variable == base and d.kind != 'parameter'
                   and (d.line, d.column) > after_pos
                   and (d.line, d.column) < (u.line, u.column)
                   for d in defs):
                stopped = 'base_reassigned'
                break
            # A call receiving the base object may mutate it.
            if any(o.operation == 'Call' and o.line <= u.line
                   for o in ops):
                # conservative: any later call in the function stops the scan
                stopped = 'possible_mutation'
                break
            hits.append(_use_out(u))
        entry = {'access_path': path, 'precision': 'partial',
                 'uses': hits[:20]}
        if stopped:
            entry['stopped_because'] = stopped
        out.append(entry)
    return out


MAX_EXPR_HOPS = 8


def _describe_hop(parent, child):
    """Describe one step from a parent AST node to the child on the path
    from a nested call up to its statement."""
    if isinstance(parent, ast.Call):
        if child is parent.func:
            return {'kind': 'call_callee',
                    'callee': ast.unparse(parent.func)[:120]
                    if hasattr(ast, 'unparse') else None}
        for i, a in enumerate(parent.args):
            if a is child:
                return {'kind': 'call_arg', 'position': i}
        for kw in parent.keywords:
            if kw.value is child:
                return {'kind': 'call_keyword', 'name': kw.arg}
        return {'kind': 'call'}
    if isinstance(parent, ast.keyword):
        return {'kind': 'keyword', 'name': parent.arg}
    if isinstance(parent, ast.Attribute):
        return {'kind': 'attribute', 'name': parent.attr}
    if isinstance(parent, ast.Subscript):
        return {'kind': 'subscript'}
    if isinstance(parent, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        return {'kind': 'assign_value'}
    if isinstance(parent, ast.Return):
        return {'kind': 'return'}
    if isinstance(parent, ast.Expr):
        return {'kind': 'expr'}
    if isinstance(parent, ast.BoolOp):
        return {'kind': 'boolop', 'op': type(parent.op).__name__}
    if isinstance(parent, ast.BinOp):
        return {'kind': 'binop', 'op': type(parent.op).__name__}
    if isinstance(parent, ast.UnaryOp):
        return {'kind': 'unaryop', 'op': type(parent.op).__name__}
    if isinstance(parent, ast.Compare):
        return {'kind': 'compare'}
    if isinstance(parent, ast.IfExp):
        return {'kind': 'ifexp'}
    if isinstance(parent, (ast.Tuple, ast.List, ast.Set)):
        return {'kind': 'collection'}
    if isinstance(parent, ast.Starred):
        return {'kind': 'starred'}
    if isinstance(parent, ast.JoinedStr):
        return {'kind': 'fstring'}
    if isinstance(parent, ast.FormattedValue):
        return {'kind': 'format'}
    return {'kind': type(parent).__name__.lower()}


def _expression_path_result(stmt, call_node, ctx, max_hops):
    """Walk from a nested call node up to its statement and describe the
    consumption path. Pure expression structure is 'confirmed'; a hop
    through another call is 'possible' unless that call resolves to a
    confirmed target (checked via the shared call resolver)."""
    # Parent map over the statement (bounded by max_hops anyway).
    parents = {}
    stack = [stmt]
    seen = set()
    while stack:
        n = stack.pop()
        if id(n) in seen:
            continue
        seen.add(id(n))
        for ch in ast.iter_child_nodes(n):
            parents[ch] = n
            stack.append(ch)

    path = []
    cur = call_node
    truncated = False
    while cur is not stmt:
        parent = parents.get(cur)
        if parent is None:
            break
        hop = _describe_hop(parent, cur)
        # Resolution: structural hops are confirmed; a hop into another
        # call's arguments is only 'possible' (we do not claim the outer
        # call propagates this value without interprocedural evidence).
        if hop['kind'] in ('call_arg', 'call_keyword', 'call_callee',
                           'call', 'keyword'):
            hop['resolution'] = 'possible'
            hop['reason'] = 'value consumed by an outer call; propagation ' \
                            'into its result is not statically confirmed'
        else:
            hop['resolution'] = 'confirmed'
        path.append(hop)
        cur = parent
        if len(path) >= max_hops:
            if cur is not stmt:
                truncated = True
            break

    if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)) \
            and getattr(stmt, 'value', None) is not None:
        final = 'assigned'
    elif isinstance(stmt, ast.Return):
        final = 'returned'
    elif isinstance(stmt, ast.Expr):
        final = 'unused'
    else:
        final = 'expression'

    out = {'disposition': 'consumed_by_expression',
           'path': path,
           'final': final,
           'precision': 'expression'}
    if truncated:
        out['truncated'] = True
    if final == 'assigned':
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        cls = _classify_targets(targets)
        if cls['variables'] or cls['attributes'] or cls['subscripts']:
            out['assigned_variables'] = sorted(set(cls['variables']))
            out['assigned_attributes'] = cls['attributes']
            out['assigned_subscripts'] = cls['subscripts']
    return out


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


def _edge_is_confirmed(e):
    from ..intelligence.dataflow.call_target import edge_is_confirmed
    return edge_is_confirmed(e)


def _resolve_call_target(graph, ctx, op):
    """Thin wrapper over the shared resolver in
    intelligence.dataflow.call_target; adds the resolved graph node."""
    from ..intelligence.dataflow.call_target import resolve_call_target
    res = resolve_call_target(graph, ctx['function_id'], ctx['file'],
                              op.line, getattr(op, 'column', None))
    if res['status'] == 'resolved':
        node = graph.get(res['target_id'])
        if not node:
            return {'status': 'unresolved',
                    'reason': 'call target %s not present in graph'
                              % res['target_id']}
        res['node'] = node
        res['node_id'] = res['target_id']
    return res


def _cross_function_chain(graph, start_function_id, max_depth):
    """Cross-file flow chain from the repository DFG pipeline.

    Directed by data flow: 'argument' edges go caller -> callee, 'return'
    edges go callee -> caller (a returned value feeding the next call).
    'global' edges connect a module-level definition to each use inside a
    function; they are traversable in both directions so a chain starting
    at a function reaches the module definitions feeding it (marked
    direction='inbound') and a chain starting at a definition reaches its
    consumers. BFS from ``start_function_id`` up to ``max_depth`` hops;
    each hop is {source, target, kind, resolution, file, line}. Returns
    [] when the pipeline cannot run — the one-hop edges above remain the
    evidence."""
    try:
        from ..intelligence.dataflow.repository_dfg import build_repository_dfg
        repo_dfg = build_repository_dfg(graph)
    except NotImplementedError as exc:
        return {'status': 'unsupported', 'chain': [], 'diagnostics': [str(exc)]}
    except Exception as exc:
        return {'status': 'failed', 'chain': [],
                'diagnostics': [type(exc).__name__ + ': ' + str(exc)]}

    # function_id -> ordered list of (next_function, edge-dict) hops
    adj: Dict[str, list] = {}
    for e in repo_dfg.edges:
        if e.source_kind == 'argument':
            src, dst = e.caller_function_id, e.callee_function_id
        else:
            src, dst = e.callee_function_id, e.caller_function_id
        if not src or not dst or src == dst:
            continue
        adj.setdefault(src, []).append((dst, {
            'source': src, 'target': dst, 'kind': e.source_kind,
            'resolution': e.resolution, 'file': e.source_file,
            'line': e.source_line}))

    # Global (cross-module) edges: a module-level definition flows into a
    # use inside a function. The hop is keyed by the definition id so a
    # chain can start at a module-level definition and continue into the
    # consuming function.
    for g in repo_dfg.global_edges or []:
        tf = g.get('target_function')
        src_def = g.get('source')
        if not tf or not src_def:
            continue
        hop = {
            'source': src_def, 'target': g.get('target'),
            'kind': 'global', 'resolution': g.get('resolution'),
            'source_function': None, 'target_function': tf,
            'source_file': g.get('source_file') or g.get('target_file'),
            'source_line': g.get('source_line'),
            'target_file': g.get('target_file') or g.get('file'),
            'target_line': g.get('target_line'),
            'file': g.get('file'), 'line': g.get('line')}
        adj.setdefault(src_def, []).append((tf, hop))
        # Reverse hop: a chain starting at the consuming function can
        # traverse into the module-level definition feeding it (and onward
        # to that definition's other consumers). The hop keeps its
        # data-flow direction (source=definition, target=use) so callers
        # can still tell which way the value moves.
        adj.setdefault(tf, []).append(
            (src_def, dict(hop, direction='inbound')))

    # Each emitted path is one chain: a list of hop dicts from the queried
    # function outward, up to max_depth.
    chains = []
    # Visited sets track node ids (function ids and module-definition ids),
    # not hop targets: global hops target a use id, so target comparison
    # alone cannot detect cycles through module definitions.
    frontier = [(start_function_id, [], frozenset([start_function_id]))]
    while frontier and len(chains) < 50:
        cur, hops, visited = frontier.pop(0)
        if len(hops) >= max_depth:
            continue
        for nxt, hop in adj.get(cur, []):
            if nxt in visited:
                continue
            new_hops = hops + [hop]
            chains.append(new_hops)
            if len(new_hops) < max_depth:
                frontier.append((nxt, new_hops, visited | {nxt}))
    status = 'completed' if chains else 'no_chain_found'
    flat = [h for chain in chains for h in chain]
    if any(h.get('resolution') != 'confirmed' for h in flat):
        status = 'partial'
    return {'status': status, 'chain': chains, 'diagnostics': []}


def _ops_by_id(ctx):
    return {o.id: o for o in ctx['facts'].operations if hasattr(o, 'id')}


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
    tool_context: ToolContext,
    max_depth: int = 3
) -> dict:
    """Track data across function boundaries for Python.

    Outbound edges: uses of the variable inside Call operations become
    argument->parameter edges. The callee is resolved through the index's
    call-site edges (file+line+column) and arguments are bound to formal
    parameters with call_binding — never by guessing a position. Inbound
    edges: call sites of this function are followed to the caller's result
    assignment and its subsequent uses. Anything that cannot be established
    is reported in 'unresolved' — a reference is never claimed as a confirmed
    flow edge.

    'chain' follows the repository-wide interprocedural edges produced by
    build_repository_dfg (argument edges caller->callee, return edges
    callee->caller) up to max_depth hops, so a value crossing three or more
    files comes back as a chain list rather than a single hop. The one-hop
    variable edges above keep their existing shape.

    Returns {'status', 'chain', 'diagnostics'} so DFG failures are visible
    instead of silently looking like 'no chain found'."""
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
            if resolution['status'] in ('ambiguous', 'possible'):
                unresolved.append({**entry,
                                   'reason': ('ambiguous callee'
                                              if resolution['status'] == 'ambiguous'
                                              else resolution.get('reason')
                                              or 'call edge is not statically resolved'),
                                   'candidates': resolution.get('candidates'),
                                   'edges': resolution.get('edges')})
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
                aggregate = b.get('precision') == 'aggregate' \
                    or b.get('param_kind') in ('vararg', 'kwarg')
                for u in matched:
                    bound_hit_ids.add(u.id)
                    outbound.append({
                        'caller_function': ctx['function_id'],
                        'argument': {'variable': variable_name, 'line': u.line},
                        'call_line': op.line,
                        'callee': callee_ctx['function_id'],
                        'parameter': {'name': b['param'],
                                      'line': pd.line if pd else None},
                        'resolution': 'possible' if aggregate else 'confirmed',
                        'aggregate': aggregate,
                        'source': ctx['function_id'],
                        'target': callee_ctx['function_id'],
                        'file': ctx['file'],
                        'line': op.line,
                    })
            for u in hits:
                if u.id not in bound_hit_ids:
                    unresolved.append({**entry,
                                       'reason': 'argument use %s did not bind to a parameter' % u.id,
                                       'argument_uses': [_use_out(u)]})

        call_sites, ret_unresolved = _caller_result_flows(ctx)
        for cs in call_sites:
            cs.setdefault('source', cs.get('caller'))
            cs.setdefault('target', ctx['function_id'])
            cs.setdefault('resolution',
                          (cs.get('result') or {}).get('disposition'))
            cs.setdefault('file', cs.get('file'))
            cs.setdefault('line', cs.get('line'))
        res = _cross_function_chain(graph, ctx['function_id'], max_depth)
        chain_status = res['status']
        return {
            'status': 'partial' if chain_status in ('partial', 'failed')
                      else ('unsupported' if chain_status == 'unsupported'
                            else 'ok'),
            'variable_id': variable_id,
            'function_id': ctx['function_id'],
            'outbound_argument_edges': outbound,
            'inbound_return_edges': call_sites,
            'chain': res['chain'],
            'chain_status': chain_status,
            'diagnostics': res['diagnostics'],
            'max_depth': max_depth,
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


def _call_nested_in_call(func_ast, call_node):
    """True when call_node is an argument or receiver of another Call —
    e.g. the ``open(p)`` inside ``data = open(p).read()`` or ``f(open(p))``."""
    parent = {}
    for n in ast.walk(func_ast):
        for c in ast.iter_child_nodes(n):
            parent[c] = n
    node = call_node
    while node in parent:
        p = parent[node]
        if isinstance(p, ast.Call):
            return True
        if isinstance(p, ast.Attribute) and isinstance(parent.get(p), ast.Call):
            return True
        node = p
    return False


def _find_call_node_expr(func_ast, line, column, expression):
    """Like _find_call_node but disambiguates calls that share a line and
    column (``open(p)`` nested in ``open(p).read()``) by preferring the
    candidate whose source text matches the recorded operation expression."""
    call = _find_call_node(func_ast, line, column)
    if call is None or not expression:
        return call
    expr = expression.strip()
    candidates = [n for n in ast.walk(func_ast)
                  if isinstance(n, ast.Call) and n.lineno == line]
    if column is not None:
        exact = [n for n in candidates if n.col_offset == column]
        if exact:
            candidates = exact
    matched = [n for n in candidates
               if hasattr(ast, 'unparse') and ast.unparse(n) == expr]
    return matched[0] if matched else call


def _open_binding_names(func_ast, op):
    """Names bound to THIS open() call's result, or an empty set.

    Binds only when the open call is the assigned value, a with-item context
    expression, or a for-iter — never when it is nested inside another
    expression (``data = open(p).read()`` binds file *content*, not a handle).
    Returns (names, reason)."""
    call = _find_call_node_expr(func_ast, op.line, getattr(op, 'column', None),
                                getattr(op, 'expression', None))
    if call is None:
        return set(), 'call node not found'
    stmt = _innermost_statement(func_ast, call)
    names = set()

    def tnames(t):
        if isinstance(t, ast.Name):
            names.add(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                tnames(e)

    if isinstance(stmt, ast.With):
        for item in stmt.items:
            if item.context_expr is call and item.optional_vars is not None:
                tnames(item.optional_vars)
    elif isinstance(stmt, (ast.Assign, ast.AnnAssign)) and stmt.value is call:
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        for t in targets:
            tnames(t)
    elif isinstance(stmt, ast.For) and stmt.iter is call:
        tnames(stmt.target)
    return names, None


def _open_call_name(call):
    """'open' for ``open(...)`` and ``io.open(...)`` call nodes, else None."""
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _is_open_call(ctx, op):
    _recv, attr = _call_attr(op)
    if attr in _FILE_OPEN_NAMES:
        return True
    return (op.expression or '').strip().startswith('open(')


def _dotted_callee(func):
    """Dotted name of a call func node, e.g. 'io.open', 'Path'."""
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    return '.'.join(reversed(parts)) if parts else None


def _path_receiver_names(func_ast):
    """Names established as pathlib.Path inside this function: assigned from
    a Path(...) call or annotated as Path."""
    names = set()
    for node in ast.walk(func_ast):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) \
                else [node.target]
            value = node.value
            is_path_ctor = isinstance(value, ast.Call) and \
                _dotted_callee(value.func) in ('Path', 'PurePath',
                                               'pathlib.Path',
                                               'pathlib.PurePath')
            ann = getattr(node, 'annotation', None)
            ann_is_path = ann is not None and \
                'Path' in (ast.unparse(ann) if hasattr(ast, 'unparse')
                           else str(ann))
            if is_path_ctor or ann_is_path:
                for t in targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
    return names


def _open_call_confidence(ctx, op, call_node):
    """'confirmed' for builtin open/io.open/os.fdopen and .open() on a
    receiver established as pathlib.Path; 'possible' for any other name
    match."""
    expr = (op.expression or '').strip()
    if expr.startswith(('open(', 'io.open(', 'os.fdopen(')):
        return 'confirmed'
    _recv, attr = _call_attr(op)
    if attr in _FILE_OPEN_NAMES:
        if _recv and _recv in _path_receiver_names(ctx['func_ast']):
            return 'confirmed'
        return 'possible'
    return 'possible'


def _handle_op_confidence(ctx, op, call_node, confirmed_handles, reaching):
    """Confidence for a read/write call: confirmed only when the receiver's
    reaching definition is a confirmed handle."""
    recv, _attr = _call_attr(op)
    if not recv:
        return 'possible'
    use = _receiver_use(ctx, op, recv)
    if use is None:
        return 'possible'
    if any(d.id in confirmed_handles for d in reaching.get(use.id, [])):
        return 'confirmed'
    return 'possible'


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
    handle_conf = {}
    sink_conf = {}

    for op in ops:
        if op.operation != 'Call':
            continue
        is_open = _is_open_call(ctx, op)
        call_node = None
        open_conf = 'possible'
        if is_open:
            call_node = _find_call_node_expr(ctx['func_ast'], op.line,
                                             getattr(op, 'column', None),
                                             getattr(op, 'expression', None))
            # The expression heuristic also fires on ``open(p).read()``; when
            # the AST call resolves to something else it is not an open call.
            if call_node is not None and _open_call_name(call_node) != 'open':
                is_open = False
            else:
                open_conf = _open_call_confidence(ctx, op, call_node)
        if is_open:
            nested = call_node is not None and _call_nested_in_call(
                ctx['func_ast'], call_node)
            if not nested:
                for did in op.output_definition_ids:
                    handles.add(did)
                    handle_expr[did] = op
                    handle_conf[did] = open_conf
            # `with open(...) as f` / `for x in open(...)` / `f = open(...)`:
            # bind only the names THIS open call produces, matched to the
            # definition on the same line — never every definition on the line.
            names, _ = _open_binding_names(ctx['func_ast'], op)
            col = getattr(op, 'column', None)
            by_var = {}
            for d in ctx['facts'].definitions:
                if d.id in handles or d.line != op.line or d.variable not in names:
                    continue
                if d.kind in ('with_binding', 'for_loop', 'for_loop_unpack',
                              'assignment', 'annotated_assignment',
                              'named_expression'):
                    by_var.setdefault(d.variable, []).append(d)
            for var, ds in by_var.items():
                if len(ds) > 1 and col is not None:
                    # Same variable bound twice on one line (e.g. two opens in
                    # one statement): keep the definition nearest before the
                    # call's column.
                    preceding = [d for d in ds
                                 if getattr(d, 'column', 0) <= col]
                    if preceding:
                        ds = [max(preceding,
                                  key=lambda d: getattr(d, 'column', 0))]
                for d in ds:
                    handles.add(d.id)
                    handle_expr[d.id] = op
                    handle_conf[d.id] = open_conf
        elif _is_read_call(op) or _is_write_call(op):
            # Receiver verification needs the confirmed-handle set, which is
            # only complete after this loop; store ops now, classify below.
            if _is_read_call(op):
                reads.append({'op': op, 'def_ids': list(op.output_definition_ids)})
            else:
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

    # Receiver verification for read/write calls: confirmed only when the
    # receiver's reaching definition is a confirmed handle.
    confirmed_handles = {did for did, c in handle_conf.items()
                         if c == 'confirmed'}
    for r in reads:
        op = r.get('op')
        if op is not None:
            r['confidence'] = _handle_op_confidence(
                ctx, op, None, confirmed_handles, reaching)
            if r['confidence'] == 'possible':
                r['receiver_unverified'] = True
        else:
            r['confidence'] = 'confirmed'  # handle iteration reads a handle
    for op in sinks:
        sink_conf[op.id] = _handle_op_confidence(
            ctx, op, None, confirmed_handles, reaching)

    ctx['file_op_conf'] = {'handles': handle_conf, 'sinks': sink_conf}
    return handles, reads, sinks, prod, reaching


# Bound on reaching-definition traversal in _def_file_sources. Hitting it is
# reported as truncation, never silently swallowed.
MAX_FILE_FLOW_STEPS = int(os.environ.get('JARVIS_DFG_MAX_STEPS', '200'))


def _def_file_sources(ctx, def_id, handles, reads_by_def, prod, reaching):
    """The read-sources that reach a definition, following copies and
    intermediate expressions through reaching definitions. Iterative with a
    step bound so deep copy chains cannot recurse forever or silently stop.

    Returns (sources, truncated): sources is a deduped list of source
    descriptors; truncated is True when the step bound cut the traversal
    short, meaning the list may be incomplete."""
    sources, seen, stack, truncated, steps = [], set(), [def_id], False, 0
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue            # cycle detection preserved
        seen.add(cur)
        steps += 1
        if steps > MAX_FILE_FLOW_STEPS:
            truncated = True
            break
        if cur in handles:
            continue
        if cur in reads_by_def:
            r = reads_by_def[cur]
            sources.append({'kind': 'source', 'operation': 'read',
                            'line': r.get('line') or (r['op'].line if r.get('op') else None),
                            'expression': (r['op'].expression if r.get('op') else None),
                            'variable': r.get('variable')})
        op = prod.get(cur)
        if cur not in reads_by_def and op is not None \
                and op.operation == 'Call' and _is_read_call(op):
            sources.append({'kind': 'source', 'operation': 'read',
                            'line': op.line, 'expression': op.expression,
                            'variable': None})
        # Propagate through whatever produced the definition: the operation's
        # input uses (e.g. `b = a`) or an explicit copy link.
        next_use_ids = []
        if op is not None:
            next_use_ids.extend(op.input_use_ids)
        d = _defs_by_id(ctx).get(cur)
        if d is not None:
            meta = d.metadata or {}
            if meta.get('source_use_id'):
                next_use_ids.append(meta['source_use_id'])
        for uid in next_use_ids:
            stack.extend(rd.id for rd in reaching.get(uid, []))
    # de-dup
    uniq, seen_keys = [], set()
    for s in sources:
        key = (s.get('operation'), s.get('line'), s.get('variable'))
        if key not in seen_keys:
            seen_keys.add(key)
            uniq.append(s)
    return uniq, truncated


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
            handle_conf = (ctx.get('file_op_conf') or {}).get('handles', {})
            sink_conf = (ctx.get('file_op_conf') or {}).get('sinks', {})
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
                    'variable': d.variable if d else None,
                    'confidence': handle_conf.get(did, 'possible')})
            for r in reads:
                d = defs.get(r['def_ids'][0]) if r['def_ids'] else None
                operations.append({
                    'kind': 'source', 'operation': 'read',
                    'function': scope,
                    'line': r.get('line') or (r['op'].line if r.get('op') else (d.line if d else None)),
                    'variable': r.get('variable') or (d.variable if d else None),
                    'iteration': bool(r.get('iteration')),
                    'confidence': r.get('confidence', 'possible'),
                    **({'receiver_unverified': True}
                       if r.get('receiver_unverified') else {})})
            for op in sinks:
                recv, attr = _call_attr(op)
                operations.append({
                    'kind': 'sink', 'operation': attr or 'write',
                    'function': scope, 'line': op.line,
                    'receiver': recv or None,
                    'confidence': sink_conf.get(op.id, 'possible')})
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
                        sources, truncated = _def_file_sources(
                            ctx, d.id, handles, reads_by_def, prod, reaching)
                        if truncated and not sources:
                            key = ('truncated', uid)
                            if key not in found:
                                found.add(key)
                                flows.append({
                                    'from': {'kind': 'source',
                                             'operation': 'read',
                                             'function': scope},
                                    'to': {'kind': 'sink',
                                           'operation': attr or 'write',
                                           'line': op.line, 'function': scope},
                                    'resolution': 'unresolved',
                                    'reason': 'analysis_truncated',
                                    'limit': MAX_FILE_FLOW_STEPS})
                            continue
                        for s in sources:
                            key = (s.get('operation'), s.get('line'), s.get('variable'), uid)
                            if key in found:
                                continue
                            found.add(key)
                            flow = {
                                'from': {'kind': 'source', **{k: v for k, v in s.items() if v is not None},
                                         'function': scope},
                                'to': {'kind': 'sink', 'operation': attr or 'write',
                                       'line': op.line, 'function': scope},
                                'resolution': 'confirmed'}
                            if truncated:
                                flow['analysis_truncated'] = True
                            flows.append(flow)

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
                        mutations.append({'kind': kind, 'confidence': 'confirmed',
                                          'target': expr,
                                          'affected_variable': base,
                                          'function': scope, 'line': node_ast.lineno})
            elif isinstance(node_ast, ast.Delete):
                for t in node_ast.targets:
                    kind, expr, base = _target_info(t)
                    if kind:
                        mutations.append({'kind': 'delete', 'confidence': 'confirmed',
                                          'target': expr,
                                          'affected_variable': base,
                                          'function': scope, 'line': node_ast.lineno})
            elif isinstance(node_ast, ast.Call):
                cname, _ = _call_name(node_ast)
                if cname in _MUTATING_METHODS:
                    # A matching method name is only a *possible* mutation:
                    # the receiver's behaviour is not verified statically.
                    recv = ast.unparse(node_ast.func.value) if isinstance(node_ast.func, ast.Attribute) else ''
                    mutations.append({'kind': 'possible_mutation',
                                      'confidence': 'possible',
                                      'method': cname,
                                      'target': recv,
                                      'affected_variable': recv.split('.')[0] or None,
                                      'function': scope, 'line': node_ast.lineno,
                                      'reason': 'method name matches a mutating pattern; receiver behavior not verified'})

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

