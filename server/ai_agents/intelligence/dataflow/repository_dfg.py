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
from .models import DefUseFacts, Definition, ExpressionFact
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

    def __post_init__(self):
        if self.reaching is None:
            self.reaching = {}


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


def _module_facts(file_path: str, source: str) -> DefUseFacts:
    """Module-level DefUseFacts: top-level imports as Import/ImportFrom
    operations and top-level bindings as definitions, for
    CrossModuleAnalyzer.analyze_module."""
    facts = DefUseFacts(function_id=file_path, file=file_path)
    try:
        tree = ast.parse(source)
    except Exception:
        return facts
    seq = [0]

    # Compound statements whose bodies execute conditionally at module level.
    _CONDITIONAL = (ast.If, ast.Try, ast.For, ast.While, ast.With,
                    ast.AsyncFor, ast.AsyncWith)

    def _walk_module(stmts, conditional=False):
        """Yield (statement, conditional) for module-level statements,
        descending into if/try/for/while/with bodies but never into
        function or class bodies (those are function-scoped)."""
        for node in stmts:
            yield node, conditional
            if isinstance(node, _CONDITIONAL):
                for field in ('body', 'orelse', 'finalbody'):
                    yield from _walk_module(getattr(node, field, None) or [],
                                            True)

    def _def(variable, line, kind, meta=None, conditional=False):
        seq[0] += 1
        facts.definitions.append(Definition(
            id='%s::top::%s:%d' % (file_path, variable, line),
            variable=variable, function_id=file_path, file=file_path,
            line=line, column=0, kind=kind, cfg_node_ids=[],
            binding_key='%s::%s' % (file_path, variable),
            metadata=dict(meta or {}, scope='module'),
            conditional=conditional))

    for node, cond in _walk_module(tree.body):
        if isinstance(node, ast.Import):
            facts.operations.append(ExpressionFact(
                id='%s::imp:%d' % (file_path, node.lineno),
                function_id=file_path, file=file_path,
                line=node.lineno, column=0, cfg_node_ids=[],
                expression=ast.unparse(node), operation='Import',
                metadata={'scope': 'module'}))
            for a in node.names:
                _def((a.asname or a.name).split('.')[0], node.lineno,
                     'import',
                     {'import_module': a.name, 'import_kind': 'import',
                      'import_name': a.name}, conditional=cond)
        elif isinstance(node, ast.ImportFrom):
            facts.operations.append(ExpressionFact(
                id='%s::impf:%d' % (file_path, node.lineno),
                function_id=file_path, file=file_path,
                line=node.lineno, column=0, cfg_node_ids=[],
                expression=ast.unparse(node), operation='ImportFrom',
                metadata={'scope': 'module'}))
            for a in node.names:
                if a.name != '*':
                    _def(a.asname or a.name, node.lineno, 'import',
                         {'import_module': node.module or '',
                          'import_level': node.level,
                          'import_kind': 'from', 'import_name': a.name},
                         conditional=cond)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _def(node.name, node.lineno, 'function', conditional=cond)
        elif isinstance(node, ast.ClassDef):
            _def(node.name, node.lineno, 'class', conditional=cond)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        _def(n.id, node.lineno, 'assignment', conditional=cond)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            _def(node.target.id, node.lineno, 'assignment', conditional=cond)
    return facts


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
    for rel_file in all_module_files:
        try:
            source = module_sources.get(rel_file)
            if source is None:
                source = _repo_path(rel_file).read_text(encoding='utf-8')
            mfacts = _module_facts(rel_file, source)
            fb = facts_by_file.get(rel_file)
            if fb is not None:
                # Module-level facts first so analyze_module sees imports
                # and top-level bindings; function facts add the uses.
                fb.definitions[:0] = mfacts.definitions
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
        modules, facts_by_file, reaching=reaching)
    unresolved.extend(global_result.get('unresolved') or [])

    return RepositoryDFG(
        edges=edges,
        global_edges=global_result.get('edges') or [],
        unresolved=unresolved,
        summaries=summaries,
        modules=modules,
        converged=converged,
        reaching=reaching)
