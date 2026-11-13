"""Repository-wide interprocedural data-flow pipeline.

One entry point that runs the existing dataflow classes in the right order
over the indexed repository: per-function CFG/DFG/facts extraction,
module summaries, interprocedural summaries, call-site connection and
global-value propagation. Callers no longer assemble the pieces by hand.
"""
import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ... import config
from .models import DefUseFacts, Definition, ExpressionFact, VariableUse
from .interprocedural import FunctionSummary, InterproceduralSummaryBuilder
from .call_site_connector import CallSiteConnector, InterproceduralEdge
from .cross_module import CrossModuleAnalyzer, ModuleSummary
from .reaching_definitions import ReachingDefs


@dataclass
class RepositoryDFG:
    """Result of build_repository_dfg."""
    edges: List[InterproceduralEdge]
    global_edges: List[Dict[str, Any]]
    unresolved: List[Dict[str, Any]]
    summaries: Dict[str, FunctionSummary]
    modules: Dict[str, ModuleSummary]
    converged: bool
    # Per-function reaching-definition artifacts (function_id -> ReachingDefs),
    # retained so summaries, call-site connection and cross-module propagation
    # can resolve uses to the definitions that actually reach them.
    reaching: Dict[str, ReachingDefs] = None
    # Module-level reaching artifacts: file -> variable -> exit-state
    # definition ids, plus the set of files whose module analysis failed
    # (callers must not treat those as clean).
    module_exit_definitions: Dict[str, Dict[str, Dict[str, Any]]] = None
    module_analysis_failed: set = None

    def __post_init__(self):
        if self.reaching is None:
            self.reaching = {}
        if self.module_exit_definitions is None:
            self.module_exit_definitions = {}
        if self.module_analysis_failed is None:
            self.module_analysis_failed = set()


def _repo_path(rel_file: str) -> Path:
    return Path(config.REPO_ROOT) / rel_file


def _function_candidates(tree: ast.AST):
    """All function defs as (qualified_name, node) pairs."""
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


def _select_func_ast(tree: ast.AST, node: Dict[str, Any], file_path: str):
    """Pick the AST node for a graph function node (same rules as the
    data-flow tools: exact locator, then unique qualname/line match)."""
    from ..parsers.python_symbol_locator import find_function_ast

    symbol = {'id': node.get('id'), 'name': node.get('name'),
              'qualname': node.get('qualname'), 'file': file_path,
              'start': node.get('start'), 'end': node.get('end'),
              'kind': node.get('kind')}
    func_ast = find_function_ast(tree, symbol)
    if func_ast is not None:
        return func_ast

    qualname = node.get('qualname')
    matched = [(q, n) for q, n in _function_candidates(tree)
               if qualname and q == qualname]
    if not matched:
        return None
    start = node.get('start')
    if start is not None:
        by_line = [(q, n) for q, n in matched
                   if getattr(n, 'lineno', None) == start]
        if by_line:
            matched = by_line
    return matched[0][1] if len(matched) == 1 else None


def build_function_artifacts(graph, node: Dict[str, Any],
                             function_id: str) -> Dict[str, Any]:
    """Build (cfg, dfg, facts, func_ast, source) for one graph function node.

    Moved here from tools.visualization_spatial_tools._build_cfg_dfg_for_node,
    which discarded the facts and the function AST this pipeline needs.
    Returns a dict; raises on failure (callers decide how to record it).
    """
    from ..parsers.python_ast import parse_python_module
    from ..controlflow.python_cfg import PythonCFGBuilder
    from ..dataflow.python_extractor import PythonDefUseExtractor
    from ..dataflow.reaching_definitions import ReachingDefinitionsAnalyzer
    from .dependency_builder import DataFlowGraphBuilder

    rel_file = node.get('file', '')
    source = _repo_path(rel_file).read_text(encoding='utf-8')
    tree = parse_python_module(source, rel_file)
    func_ast = _select_func_ast(tree, node, rel_file)
    if func_ast is None:
        raise ValueError('Function AST node not found: %s' % function_id)

    artifact = PythonCFGBuilder().build_function(
        function_ast=func_ast, function_id=function_id,
        source=source, file_path=rel_file)
    facts = PythonDefUseExtractor().extract_function(
        artifact=artifact, source=source, file_path=rel_file)
    analysis = ReachingDefinitionsAnalyzer().analyze(artifact.graph, facts)
    if isinstance(analysis, dict) and 'error' in analysis:
        raise ValueError(analysis['error'])
    dfg = DataFlowGraphBuilder().build(artifact.graph, facts, analysis)

    return {'cfg': artifact.graph, 'dfg': dfg, 'facts': facts,
            'func_ast': func_ast, 'source': source, 'file': rel_file,
            'analysis': analysis}


# Compound statements whose bodies execute conditionally at module level.
_MODULE_CONDITIONAL = (ast.If, ast.Try, ast.TryStar, ast.For, ast.While,
                       ast.With, ast.AsyncFor, ast.AsyncWith, ast.Match)


def _walk_module(stmts, conditional=False):
    """Yield (statement, conditional) for module-level statements,
    descending into if/try/for/while/with/match bodies and except-handler
    bodies but never into function or class bodies (those are
    function-scoped)."""
    for node in stmts:
        yield node, conditional
        if isinstance(node, _MODULE_CONDITIONAL):
            for field in ('body', 'orelse', 'finalbody'):
                yield from _walk_module(getattr(node, field, None) or [],
                                        True)
            for handler in getattr(node, 'handlers', None) or []:
                yield handler, True
                yield from _walk_module(getattr(handler, 'body', None) or [],
                                        True)
            for case in getattr(node, 'cases', None) or []:
                yield from _walk_module(getattr(case, 'body', None) or [],
                                        True)


def _header_exprs(stmt, _has_future_annotations=False):
    """Expressions evaluated by a compound statement's own header (not its
    nested bodies, which are yielded separately)."""
    if isinstance(stmt, ast.If):
        return [stmt.test]
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return [stmt.iter]
    if isinstance(stmt, ast.While):
        return [stmt.test]
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return [i.context_expr for i in stmt.items]
    if isinstance(stmt, ast.Match):
        return [stmt.subject]
    if isinstance(stmt, (ast.Try, ast.TryStar)):
        return []
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        expressions = list(stmt.decorator_list)
        expressions.extend(stmt.args.defaults)
        expressions.extend(
            value for value in stmt.args.kw_defaults
            if value is not None
        )
        # Annotations are evaluated at definition time unless
        # `from __future__ import annotations` is active.
        if not _has_future_annotations:
            all_args = (
                list(stmt.args.posonlyargs)
                + list(stmt.args.args)
                + list(stmt.args.kwonlyargs)
            )
            if stmt.args.vararg:
                all_args.append(stmt.args.vararg)
            if stmt.args.kwarg:
                all_args.append(stmt.args.kwarg)
            expressions.extend(
                arg.annotation for arg in all_args
                if arg.annotation is not None
            )
            if stmt.returns is not None:
                expressions.append(stmt.returns)
        return expressions
    if isinstance(stmt, ast.ClassDef):
        expressions = list(stmt.decorator_list)
        expressions.extend(stmt.bases)
        if stmt.keywords:
            expressions.extend(
                keyword.value for keyword in stmt.keywords
            )
        return expressions
    return [stmt]


def _load_names(root):
    """Name(Load) nodes under ``root``, pruning nested def/class/lambda
    bodies which do not execute at module level."""
    stack = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            yield node
        stack.extend(ast.iter_child_nodes(node))


def _store_names(root):
    """Name(Store/Del) binding targets under ``root``."""
    for node in ast.walk(root):
        if isinstance(node, ast.Name) and isinstance(
                node.ctx, (ast.Store, ast.Del)):
            yield node


def _module_facts(file_path: str, source: str,
                  artifact=None, tree: Optional[ast.AST] = None) -> DefUseFacts:
    """Module-level DefUseFacts: top-level imports as Import/ImportFrom
    operations and top-level bindings as definitions, for
    CrossModuleAnalyzer.analyze_module.

    When ``artifact`` (a CFGBuildArtifact from
    PythonCFGBuilder.build_module) is supplied, every fact carries the CFG
    node ids of the statement that creates/uses it and module-level reads
    are emitted as VariableUse facts, so ReachingDefinitionsAnalyzer can
    run over the module CFG. Without an artifact the legacy line-only facts
    are produced (no uses, empty cfg_node_ids)."""
    facts = DefUseFacts(function_id=file_path, file=file_path)
    try:
        # Reuse the caller's tree when supplied: the CFG artifact's
        # ast_node_map / ast_index are keyed by id() of that tree's nodes,
        # so re-parsing here would silently break every node lookup.
        tree = tree if tree is not None else ast.parse(source)
    except Exception:
        return facts
    seq = [0]
    used_ids = set()

    cfg = getattr(artifact, 'graph', None) if artifact else None
    ast_index = getattr(artifact, 'ast_index', None) if artifact else None

    def _stmt_nodes(stmt):
        """Return CFG nodes mapped to this exact AST statement."""
        if cfg is None:
            return []
        node_id = cfg.ast_node_map.get(id(stmt))
        return [node_id] if node_id else []

    def _definition_nodes(name_node, stmt):
        """Return the exact commit node for a module-level binding."""
        if cfg is None:
            return []
        if ast_index is not None:
            node_ids = ast_index.get_cfg_nodes(name_node)
            roles = ast_index.get_roles(name_node)
            commit_ids = [
                node_id
                for node_id, role in zip(node_ids, roles)
                if role == "assignment_commit"
            ]
            if commit_ids:
                return list(dict.fromkeys(commit_ids))
        return _stmt_nodes(stmt)

    def _use_nodes(name_node, stmt, header_map):
        if cfg is None:
            return []
        ids = list(ast_index.get_cfg_nodes(name_node)) if ast_index else []
        if not ids:
            expr = header_map.get(id(name_node))
            if expr is not None:
                nid = cfg.ast_node_map.get(id(expr))
                if nid:
                    ids.append(nid)
        if not ids:
            nid = cfg.ast_node_map.get(id(stmt))
            if nid:
                ids.append(nid)
        return ids

    def _fact_id(prefix, *parts):
        seq[0] += 1
        base = '%s::%s::%s' % (file_path, prefix, ':'.join(
            str(p) for p in parts))
        if base in used_ids:
            base = '%s#%d' % (base, seq[0])
        used_ids.add(base)
        return base

    def _def(variable, line, kind, meta=None, conditional=False,
             column=0, node_ids=None):
        facts.definitions.append(Definition(
            id=_fact_id('top', variable, line, column),
            variable=variable, function_id=file_path, file=file_path,
            line=line, column=column, kind=kind,
            cfg_node_ids=list(node_ids or []),
            binding_key='%s::%s' % (file_path, variable),
            metadata=dict(meta or {}, scope='module'),
            conditional=conditional))

    _has_future_annotations = any(
        isinstance(stmt, ast.ImportFrom)
        and stmt.module == "__future__"
        and any(alias.name == "annotations" for alias in stmt.names)
        for stmt in tree.body)

    for node, cond in _walk_module(tree.body):
        if isinstance(node, ast.ExceptHandler):
            # `except E as e`: E is evaluated (use), e is bound then deleted.
            stmt_nodes = _stmt_nodes(node)
            header_roots = [node.type] if node.type is not None else []
            hmap = {}
            for r in header_roots:
                for n in ast.walk(r):
                    hmap[id(n)] = r
            if ast_index is not None or cfg is not None:
                for nm in _load_names_from_roots(header_roots):
                    ids = _use_nodes(nm, node, hmap)
                    if ids:
                        facts.uses.append(VariableUse(
                            id=_fact_id('use', nm.id, nm.lineno,
                                        nm.col_offset),
                            variable=nm.id, function_id=file_path,
                            file=file_path, line=nm.lineno,
                            column=nm.col_offset, cfg_node_ids=ids,
                            binding_key='%s::%s' % (file_path, nm.id),
                            metadata={'scope': 'module'}))
            if node.name:
                _def(node.name, node.lineno, 'assignment',
                     conditional=cond, column=node.col_offset,
                     node_ids=stmt_nodes)
            continue

        stmt_nodes = _stmt_nodes(node)
        header_roots = _header_exprs(
            node,
            _has_future_annotations,)
        # map every expression node under each header root to that root so
        # uses can fall back to the header's CFG node.
        hmap = {}
        for r in header_roots:
            if r is None:
                continue
            for n in ast.walk(r):
                hmap[id(n)] = r

        if isinstance(node, ast.Import):
            facts.operations.append(ExpressionFact(
                id=_fact_id('imp', node.lineno),
                function_id=file_path, file=file_path,
                line=node.lineno, column=0, cfg_node_ids=stmt_nodes,
                expression=ast.unparse(node), operation='Import',
                metadata={'scope': 'module'}))
            for a in node.names:
                _def((a.asname or a.name).split('.')[0], node.lineno,
                     'import',
                     {'import_module': a.name, 'import_kind': 'import',
                      'import_name': a.name}, conditional=cond,
                     column=node.col_offset, node_ids=stmt_nodes)
        elif isinstance(node, ast.ImportFrom):
            facts.operations.append(ExpressionFact(
                id=_fact_id('impf', node.lineno),
                function_id=file_path, file=file_path,
                line=node.lineno, column=0, cfg_node_ids=stmt_nodes,
                expression=ast.unparse(node), operation='ImportFrom',
                metadata={'scope': 'module'}))
            for a in node.names:
                if a.name != '*':
                    _def(a.asname or a.name, node.lineno, 'import',
                         {'import_module': node.module or '',
                          'import_level': node.level,
                          'import_kind': 'from', 'import_name': a.name},
                         conditional=cond, column=node.col_offset,
                         node_ids=stmt_nodes)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _def(node.name, node.lineno, 'function', conditional=cond,
                 column=node.col_offset, node_ids=stmt_nodes)
        elif isinstance(node, ast.ClassDef):
            _def(node.name, node.lineno, 'class', conditional=cond,
                 column=node.col_offset, node_ids=stmt_nodes)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for n in _store_names(t):
                    _def(n.id, node.lineno, 'assignment', conditional=cond,
                         column=n.col_offset,
                         node_ids=_definition_nodes(n, node))
        elif isinstance(node, ast.AnnAssign):
            if node.value is not None and isinstance(node.target, ast.Name):
                _def(node.target.id, node.lineno, 'assignment',
                     conditional=cond, column=node.target.col_offset,
                     node_ids=stmt_nodes)
        elif isinstance(node, ast.AugAssign) and isinstance(
                node.target, ast.Name):
            _def(node.target.id, node.lineno, 'assignment', conditional=cond,
                 column=node.target.col_offset,
                 node_ids=_definition_nodes(node.target, node))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            for n in _store_names(node.target):
                _def(n.id, node.lineno, 'assignment', conditional=cond,
                     column=n.col_offset, node_ids=stmt_nodes)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    for n in _store_names(item.optional_vars):
                        _def(n.id, node.lineno, 'assignment',
                             conditional=cond, column=n.col_offset,
                             node_ids=stmt_nodes)
        elif isinstance(node, ast.Delete):
            for t in node.targets:
                for n in _store_names(t):
                    _def(n.id, node.lineno, 'deletion',
                         {'is_deletion': True, 'is_kill_only': True},
                         conditional=cond, column=n.col_offset,
                         node_ids=stmt_nodes)

        # Walrus bindings inside header expressions (e.g. `if (x := f()):`).
        if cfg is not None:
            for r in header_roots:
                if r is None:
                    continue
                for n in ast.walk(r):
                    if isinstance(n, ast.NamedExpr) and isinstance(
                            n.target, ast.Name):
                        _def(n.target.id, n.lineno, 'assignment',
                             conditional=cond, column=n.target.col_offset,
                             node_ids=stmt_nodes)

        # Module-level reads: Load names in this statement's header/scope.
        if cfg is not None:
            seen_use = set()
            for r in header_roots:
                if r is None:
                    continue
                for nm in _load_names(r):
                    key = (nm.id, nm.lineno, nm.col_offset)
                    if key in seen_use:
                        continue
                    seen_use.add(key)
                    ids = _use_nodes(nm, node, hmap)
                    if not ids:
                        continue
                    facts.uses.append(VariableUse(
                        id=_fact_id('use', nm.id, nm.lineno,
                                    nm.col_offset),
                        variable=nm.id, function_id=file_path,
                        file=file_path, line=nm.lineno,
                        column=nm.col_offset, cfg_node_ids=ids,
                        binding_key='%s::%s' % (file_path, nm.id),
                        metadata={'scope': 'module'}))
    return facts


def _load_names_from_roots(roots):
    for r in roots:
        if r is None:
            continue
        yield from _load_names(r)


def _must_assigned_bindings(cfg, facts) -> set:
    """Binding keys definitely assigned on every normal path to the module
    exit. Must-analysis over binding keys (any definition of the binding
    counts), with unreachable nodes excluded."""
    from .reaching_definitions import ReachingDefinitionsAnalyzer
    analyzer = ReachingDefinitionsAnalyzer()
    reachable = analyzer._calculate_reachability(cfg)
    if not cfg.entry_node_id or cfg.entry_node_id not in reachable:
        return set()

    gen_keys: Dict[str, set] = {}
    for d in facts.definitions:
        for nid in d.cfg_node_ids or []:
            gen_keys.setdefault(nid, set()).add(d.binding_key)

    predecessors: Dict[str, List[str]] = {}
    for e in cfg.edges:
        predecessors.setdefault(e.target, []).append(e.source)

    all_out = {n.id: set() for n in cfg.nodes}
    in_sets: Dict[str, set] = {n.id: set() for n in cfg.nodes}
    worklist = [n.id for n in cfg.nodes if n.id in reachable]
    in_work = set(worklist)

    while worklist:
        node_id = worklist.pop(0)
        in_work.discard(node_id)
        preds = [p for p in predecessors.get(node_id, [])
                 if p in reachable]
        if node_id == cfg.entry_node_id or not preds:
            new_in = set()
        else:
            new_in = set.intersection(
                *(all_out[p] for p in preds)) if len(preds) > 1 \
                else set(all_out[preds[0]])
        new_out = gen_keys.get(node_id, set()) | new_in
        if new_in != in_sets[node_id] or new_out != all_out[node_id]:
            in_sets[node_id] = new_in
            all_out[node_id] = new_out
            for e in cfg.edges:
                if e.source == node_id and e.target in reachable \
                        and e.target not in in_work:
                    worklist.append(e.target)
                    in_work.add(e.target)

    return in_sets.get(cfg.exit_node_id, set())


def _analyze_module_reaching(file_path: str, source: str):
    """Build the module CFG, extract module facts, run reaching-definitions
    and compute per-variable exit definitions.

    Returns (facts, exit_defs, diagnostics). ``exit_defs`` maps variable
    name -> {'definition_ids', 'definitely_assigned', 'diagnostics'}.
    Raises on unrecoverable failure; callers record it as a partial/failed
    module analysis rather than falling back to line heuristics.
    """
    from ..controlflow.python_cfg import PythonCFGBuilder
    from .reaching_definitions import ReachingDefinitionsAnalyzer

    diagnostics: List[Dict[str, Any]] = []
    tree = ast.parse(source, filename=file_path)
    artifact = PythonCFGBuilder().build_module(
        tree, file_path, source, file_path)
    cfg = artifact.graph
    for d in getattr(cfg, 'metadata', {}).get('diagnostics', []) or []:
        diagnostics.append(d)

    facts = _module_facts(file_path, source, artifact=artifact, tree=tree)
    facts.metadata['scope'] = 'module'
    facts.diagnostics.extend(diagnostics)

    analysis = ReachingDefinitionsAnalyzer().analyze(cfg, facts)
    if isinstance(analysis, dict) and analysis.get('error'):
        raise ValueError('module reaching-definitions failed for %s: %s'
                         % (file_path, analysis['error']))
    analysis_diagnostics = (
        analysis.get("diagnostics", [])
        if isinstance(analysis, dict)
        else [])
    for diagnostic in analysis_diagnostics:
        if diagnostic not in facts.diagnostics:
            facts.diagnostics.append(diagnostic)
    diagnostics.extend(analysis_diagnostics)

    cfg_node_ids = {n.id for n in cfg.nodes}
    for fact in list(facts.definitions) + list(facts.uses):
        bad = [i for i in (fact.cfg_node_ids or []) if i not in cfg_node_ids]
        if bad:
            raise ValueError('fact %s references invalid CFG node(s) %s'
                             % (fact.id, bad))

    defs_by_id = {d.id: d for d in facts.definitions}
    exit_in = (analysis.get('in_sets') or {}).get(cfg.exit_node_id, set())
    must_keys = _must_assigned_bindings(cfg, facts)

    exit_defs: Dict[str, Dict[str, Any]] = {}
    for def_id in exit_in:
        d = defs_by_id.get(def_id)
        if d is None or d.metadata.get('is_kill_only'):
            continue
        entry = exit_defs.setdefault(
            d.variable, {'definition_ids': [], 'definitely_assigned': False,
                         'diagnostics': []})
        if def_id not in entry['definition_ids']:
            entry['definition_ids'].append(def_id)
    for var, entry in exit_defs.items():
        binding_key = '%s::%s' % (file_path, var)
        entry['definitely_assigned'] = binding_key in must_keys
        entry['definition_ids'].sort(
            key=lambda i: (defs_by_id[i].line,
                           defs_by_id[i].column))
    return facts, exit_defs, diagnostics


def _graph_ctx_from_codegraph(graph) -> Dict[str, Any]:
    """Reconstruct the resolver graph context from a loaded CodeGraph.

    The indexer builds graph_ctx at index time but does not persist it, so
    the pipeline rebuilds the fields the Python resolver reads
    (module_files, file_symbols, node_ids, nodes)."""
    from ..graph_engine.indexer import _module_name_for
    from ..languages import language_for_path

    nodes = list(getattr(graph, '_nodes', {}).values()) \
        or list((graph._raw_data or {}).get('nodes', []))
    node_ids = {n.get('id') for n in nodes}
    module_files: Dict[str, str] = {}
    file_symbols: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes:
        rel = n.get('file')
        if not rel:
            continue
        if n.get('kind') in ('function', 'method', 'object') \
                or '::' in (n.get('id') or ''):
            file_symbols.setdefault(rel, []).append(n)
        if language_for_path(rel) == 'python':
            mod = _module_name_for(rel, 'python')
            if mod:
                module_files[mod] = rel
    return {'nodes': nodes, 'node_ids': node_ids,
            'module_files': module_files,
            'file_symbols': file_symbols,
            'analyses': {}}


def _is_python_function_node(node: Dict[str, Any]) -> bool:
    return (node.get('file') or '').endswith('.py') \
        and node.get('kind') in ('function', 'method')


def build_repository_dfg(
    graph,
    graph_ctx: Optional[Dict[str, Any]] = None,
    function_ids: Optional[List[str]] = None,
    cache=None,
) -> RepositoryDFG:
    """Run the full interprocedural pipeline over the indexed repository.

    ``graph`` is a loaded CodeGraph; ``graph_ctx`` is the resolver context
    (rebuilt from the graph when omitted). ``function_ids`` restricts the
    per-function analysis; the default is every Python function/method node.
    """
    if graph_ctx is None:
        graph_ctx = _graph_ctx_from_codegraph(graph)

    if function_ids is None:
        function_ids = [n.get('id') for n in
                        (getattr(graph, '_nodes', {}).values()
                         or (graph._raw_data or {}).get('nodes', []))
                        if _is_python_function_node(n)]

    unresolved: List[Dict[str, Any]] = []
    all_facts: List[DefUseFacts] = []
    file_of: Dict[str, str] = {}
    ast_of: Dict[str, Any] = {}
    source_hash_of: Dict[str, str] = {}
    method_ids = set()
    facts_by_file: Dict[str, DefUseFacts] = {}
    module_sources: Dict[str, str] = {}
    reaching: Dict[str, ReachingDefs] = {}

    # (1) per-function artifacts
    for fid in function_ids:
        node = graph.get(fid)
        if not node:
            unresolved.append({'function_id': fid,
                               'reason': 'function not found in graph'})
            continue
        try:
            art = build_function_artifacts(graph, node, fid)
        except Exception as exc:
            unresolved.append({'function_id': fid,
                               'reason': 'artifact build failed: %s' % exc})
            continue
        facts = art['facts']
        all_facts.append(facts)
        # Scope tag: every fact keeps its owning scope — the module (file)
        # for top-level facts, the function id for function-level facts.
        facts.metadata['scope'] = 'module' if facts.function_id == art['file'] \
            else facts.function_id
        reaching[facts.function_id] = ReachingDefs(
            function_id=facts.function_id, file=art['file'],
            analysis=art['analysis'], facts=facts, cfg=art['cfg'])
        file_of[facts.function_id] = art['file']
        ast_of[facts.function_id] = art['func_ast']
        segment = ast.get_source_segment(art['source'], art['func_ast']) \
            or art['source']
        source_hash_of[facts.function_id] = hashlib.sha256(
            segment.encode('utf-8')).hexdigest()
        if node.get('kind') == 'method' or node.get('class_name'):
            method_ids.add(facts.function_id)
        module_sources.setdefault(art['file'], art['source'])
        fb = facts_by_file.setdefault(
            art['file'], DefUseFacts(function_id=art['file'],
                                     file=art['file']))
        fb.definitions.extend(facts.definitions)
        fb.uses.extend(facts.uses)
        fb.operations.extend(facts.operations)

    # (2) module summaries, once per file — including modules with no
    # functions (constants, re-export-only __init__), which are exactly the
    # files global-value propagation needs to see.
    analyzer = CrossModuleAnalyzer(graph_ctx)
    modules: Dict[str, ModuleSummary] = {}
    module_files = set(graph_ctx.get('module_files', {}).values())
    all_module_files = sorted(set(list(facts_by_file) + list(module_sources)
                                  + [f for f in module_files
                                     if f.endswith('.py')]))
    module_exit_definitions: Dict[str, Dict[str, Dict[str, Any]]] = {}
    module_analysis_failed: set = set()
    for rel_file in all_module_files:
        try:
            source = module_sources.get(rel_file)
            if source is None:
                source = _repo_path(rel_file).read_text(encoding='utf-8')
            try:
                mfacts, exit_defs, module_diags = _analyze_module_reaching(
                    rel_file, source)
                for diagnostic in module_diags:
                    unresolved.append({
                        "file": rel_file,
                        "stage": "module_reaching",
                        "reason": "module analysis diagnostic",
                        "diagnostic": diagnostic,
                    })
                module_exit_definitions[rel_file] = exit_defs
            except Exception as exc:
                # CFG/fact failure: record it; cross-module resolution must
                # not fall back to line-order heuristics for this module.
                module_analysis_failed.add(rel_file)
                unresolved.append({'file': rel_file,
                                   'reason': 'module reaching-definitions '
                                             'failed: %s' % exc})
                mfacts = _module_facts(rel_file, source)
            fb = facts_by_file.get(rel_file)
            if fb is not None:
                # Module-level facts first so analyze_module sees imports
                # and top-level bindings; function facts add the uses.
                fb.definitions[:0] = mfacts.definitions
                fb.uses[:0] = mfacts.uses
                fb.operations[:0] = mfacts.operations
            else:
                fb = mfacts
                facts_by_file[rel_file] = fb
            modules[rel_file] = analyzer.analyze_module(fb, rel_file)
        except Exception as exc:
            unresolved.append({'file': rel_file,
                               'reason': 'module analysis failed: %s' % exc})

    # (3) interprocedural summaries
    builder = InterproceduralSummaryBuilder(
        graph=graph, file_of=file_of,
        source_hash_of=source_hash_of, ast_of=ast_of,
        reaching=reaching)
    summaries = builder.compute_summaries(all_facts)
    converged = bool(builder._call_graph.metadata.get('converged', True)) \
        if builder._call_graph else True
    for fid, entries in (builder.unresolved or {}).items():
        for e in entries:
            unresolved.append({'function_id': fid, **e})

    # (4) call-site edges
    connector = CallSiteConnector(builder)
    edges_by_func = connector.connect_all_call_sites(
        all_facts, summaries, ast_of=ast_of, method_ids=method_ids,
        reaching=reaching)
    edges: List[InterproceduralEdge] = []
    for flist in edges_by_func.values():
        edges.extend(flist)

    # Resolve DFG node ids for edge endpoints where the per-function DFG
    # was built (fact_to_node lives on each function's DataFlowGraph).
    # build_function_artifacts results are not retained here, so node ids
    # stay None unless a caller resolves them — see repository_dfg_edges.

    # (5) global value propagation
    global_result = analyzer.propagate_global_values(
        modules, facts_by_file, reaching=reaching,
        module_exit_defs=module_exit_definitions,
        module_analysis_failed=module_analysis_failed)
    unresolved.extend(global_result.get('unresolved') or [])

    return RepositoryDFG(
        edges=edges,
        global_edges=global_result.get('edges') or [],
        unresolved=unresolved,
        summaries=summaries,
        modules=modules,
        converged=converged,
        reaching=reaching,
        module_exit_definitions=module_exit_definitions,
        module_analysis_failed=module_analysis_failed)
