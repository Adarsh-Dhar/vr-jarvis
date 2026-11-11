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

_FACTS_CACHE = {}


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
    if use_cache and function_id in _FACTS_CACHE:
        return _FACTS_CACHE[function_id], None
    ctx, err = _resolve_python_function(function_id)
    if err:
        return None, err
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
    if use_cache:
        _FACTS_CACHE[function_id] = ctx
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


def _caller_result_flows(ctx):
    """For every call site of this function in the repo, find what the caller
    does with the return value: the assigned variable and its later uses, or
    'unused'/'returned'/'unresolved'. Python only; other call shapes are
    reported unresolved rather than guessed."""
    from ._common import repo_root
    from .navigation_tools import _python_call_sites

    node = ctx['node']
    simple = node.get('name') or ctx['func_ast'].name
    sites = _python_call_sites(simple, repo_root())
    results = []
    unresolved = []
    for site in sites:
        entry = {'file': site['file'], 'line': site['line'], 'caller': site['caller']}
        caller = site['caller']
        if not caller or caller == '<module>':
            unresolved.append({**entry, 'reason': 'call site is at module level'})
            continue
        try:
            src = abs_repo_path(site['file']).read_text(encoding='utf-8')
            tree = ast.parse(src)
        except Exception:
            unresolved.append({**entry, 'reason': 'caller file could not be parsed'})
            continue
        target_fn = None
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == caller \
                    and n.lineno <= site['line'] <= (n.end_lineno or n.lineno):
                target_fn = n
                break
        if target_fn is None:
            unresolved.append({**entry, 'reason': 'caller function not found'})
            continue
        # Locate the Call node at the site line and the statement consuming it.
        call_node = None
        for n in ast.walk(target_fn):
            if isinstance(n, ast.Call) and n.lineno == site['line']:
                call_node = n
                break
        if call_node is None:
            unresolved.append({**entry, 'reason': 'call node not found at reported line'})
            continue
        assigned, disposition = [], 'expression_result_unused'
        for stmt in ast.walk(target_fn):
            if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                for t in targets:
                    for sub in ast.walk(t):
                        if sub is call_node:
                            for name in ast.walk(t):
                                if isinstance(name, ast.Name):
                                    assigned.append(name.id)
                # call inside the value, not the target
                val = stmt.value
                if any(sub is call_node for sub in ast.walk(val)):
                    for t in targets:
                        for name in ast.walk(t):
                            if isinstance(name, ast.Name):
                                assigned.append(name.id)
                    disposition = 'assigned'
            elif isinstance(stmt, ast.Return) and stmt.value is not None \
                    and any(sub is call_node for sub in ast.walk(stmt.value)):
                disposition = 'returned'
        entry['result'] = {'disposition': disposition,
                           'assigned_variables': sorted(set(assigned))}
        # Subsequent uses of each assigned variable inside the caller, from the
        # caller AST: Load-context Name nodes below the call line.
        for var in sorted(set(assigned)):
            later = [{'line': n.lineno}
                     for n in ast.walk(target_fn)
                     if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                     and n.id == var and n.lineno > site['line']]
            entry['result'].setdefault('subsequent_uses', {})[var] = later[:20]
        results.append(entry)
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

        return {
            'status': 'ok',
            'variable_id': variable_id,
            'function_id': ctx['function_id'],
            'is_parameter': is_parameter,
            'origin': origins[0] if origins else None,
            'origins': origins,
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


def _find_graph_function(graph, name):
    """Resolve a (possibly dotted) callee name to a codegraph node."""
    if not name:
        return None
    leaf = name.split('.')[-1]
    for nid, node in (graph.items() if hasattr(graph, 'items') else []):
        if not isinstance(node, dict):
            continue
        if node.get('name') == leaf or node.get('qualname') == name \
                or str(nid).endswith('::' + leaf) or str(nid).endswith('.' + name):
            return node
    return None


@safe
def trace_cross_function_flow(
    variable_id: str,
    tool_context: ToolContext
) -> dict:
    """Track data across function boundaries for Python.

    Outbound edges: uses of the variable inside Call operations become
    argument->parameter edges when the callee resolves in the code graph and
    the argument position maps to a formal parameter. Inbound edges: call
    sites of this function are followed to the caller's result assignment and
    its subsequent uses. Anything that cannot be established is reported in
    'unresolved' — a reference is never claimed as a confirmed flow edge."""
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

        from ..intelligence.graph_engine.codegraph import codegraph
        graph = codegraph.load_current_graph()
        facts = ctx['facts']
        use_by_id = _uses_by_id(ctx)
        var_use_ids = {u.id for u in facts.uses if u.variable == variable_name}

        outbound, unresolved = [], []
        for op in sorted(facts.operations, key=lambda o: (o.line, o.column)):
            if op.operation != 'Call':
                continue
            arg_uses = [use_by_id[i] for i in op.input_use_ids if i in use_by_id]
            hits = [u for u in arg_uses if u.id in var_use_ids]
            if not hits:
                continue
            callee_name = _callee_name(op.expression or '')
            entry = {'line': op.line, 'expression': op.expression,
                     'variable': variable_name, 'callee_name': callee_name,
                     'argument_uses': [_use_out(u) for u in hits]}
            callee_node = _find_graph_function(graph, callee_name)
            if callee_node is None:
                unresolved.append({**entry, 'reason': 'callee not resolved in graph'})
                continue
            callee_ctx, cerr = _function_facts(
                callee_node.get('id') or callee_node.get('name'))
            if cerr:
                unresolved.append({**entry, 'reason': 'callee analysis failed: %s' % cerr.get('error')})
                continue
            params = [d for d in callee_ctx['facts'].definitions if d.kind == 'parameter']
            # input_use_ids preserves argument order; kwargs are not separated,
            # so only positional indices are claimed as confirmed.
            arg_index = {uid: i for i, uid in enumerate(op.input_use_ids)}
            for u in hits:
                idx = arg_index.get(u.id)
                if idx is None or idx >= len(params):
                    unresolved.append({**entry, 'reason': 'argument position %s has no matching parameter' % idx})
                    continue
                outbound.append({
                    'caller_function': ctx['function_id'],
                    'argument': {'variable': variable_name, 'line': u.line},
                    'call_line': op.line,
                    'callee': callee_ctx['function_id'],
                    'parameter': {'name': params[idx].variable, 'line': params[idx].line},
                    'resolution': 'confirmed',
                })

        call_sites, ret_unresolved = _caller_result_flows(ctx)
        return {
            'status': 'ok',
            'variable_id': variable_id,
            'function_id': ctx['function_id'],
            'outbound_argument_edges': outbound,
            'inbound_return_edges': call_sites,
            'unresolved': unresolved + ret_unresolved,
            'evidence': 'def-use call operations + graph callee resolution + AST call-site tracking'
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


@safe
def trace_file_operations(
    file_path: str,
    tool_context: ToolContext
) -> dict:
    """Track data through file operations with AST evidence (Python files).

    Sources are calls that produce file content (open/read/readline(s)); sinks
    are calls that persist it (write/writelines). When a variable holding read
    content is used inside a write call in the same function, that source->sink
    relationship is reported as a confirmed data relationship. Non-Python files
    return not_applicable rather than pattern-search results."""
    try:
        from ._common import repo_root
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

        tree = ast.parse(p.read_text(encoding='utf-8', errors='replace'))
        rel = str(p.relative_to(repo_root())) if str(p).startswith(str(repo_root())) else str(p)

        operations, flows = [], []
        scopes = [n for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        scopes.append(tree)  # module level
        for scope in scopes:
            scope_name = getattr(scope, 'name', '<module>')
            scope_nodes = scope.body if hasattr(scope, 'body') else list(ast.iter_child_nodes(scope))
            read_vars = {}   # var -> line it was read at
            for stmt in ast.walk(scope):
                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                    value = stmt.value
                    if not isinstance(value, ast.Call):
                        continue
                    cname, _ = _call_name(value)
                    if cname in _FILE_READ_ATTRS or cname in _FILE_OPEN_NAMES:
                        for t in (stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]):
                            for name in _assigned_names(t):
                                read_vars[name] = stmt.lineno
                                operations.append({
                                    'kind': 'source', 'operation': cname,
                                    'function': scope_name, 'line': stmt.lineno,
                                    'variable': name})
                elif isinstance(stmt, ast.Call):
                    cname, _ = _call_name(stmt)
                    if cname in _FILE_WRITE_ATTRS:
                        used_reads = sorted({n.id for n in ast.walk(stmt)
                                             if isinstance(n, ast.Name) and n.id in read_vars})
                        operations.append({
                            'kind': 'sink', 'operation': cname,
                            'function': scope_name, 'line': stmt.lineno,
                            'uses_read_data': bool(used_reads)})
                        for var in used_reads:
                            flows.append({
                                'from': {'kind': 'source', 'variable': var,
                                         'line': read_vars[var], 'function': scope_name},
                                'to': {'kind': 'sink', 'operation': cname,
                                       'line': stmt.lineno, 'function': scope_name},
                                'resolution': 'confirmed'})
        return {
            'status': 'ok',
            'file_path': rel,
            'operations': operations,
            'data_relationships': flows,
            'source_count': sum(1 for o in operations if o['kind'] == 'source'),
            'sink_count': sum(1 for o in operations if o['kind'] == 'sink'),
            'evidence': 'AST call analysis; source->sink edges only when read data reaches a write'
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
        file_path = None
        graph = codegraph.load_current_graph()
        node = graph.get(component_id) if hasattr(graph, 'get') else None
        if node and node.get('file'):
            file_path = node['file']
        else:
            for nid, n in (graph.items() if hasattr(graph, 'items') else []):
                if isinstance(n, dict) and (nid == component_id or n.get('name') == component_id):
                    file_path = n.get('file')
                    break
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

        for node_ast in ast.walk(tree):
            scope = '<module>'
            for fn in ast.walk(tree):
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and fn.lineno <= node_ast.lineno <= (fn.end_lineno or fn.lineno):
                    scope = fn.name
                    break
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

