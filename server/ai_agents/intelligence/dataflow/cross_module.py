"""Cross-file and cross-module propagation for interprocedural analysis."""
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple

from .models import DefUseFacts, Definition
from .interprocedural import InterproceduralSummaryBuilder, FunctionSummary

EXTERNAL = 'external'


def _parse_import_expr(expr: str) -> List[Dict[str, Any]]:
    """Parse 'import a.b as c' / 'from x import y as z' / 'from . import w'
    into resolver imp dicts {module, name, level, kind}."""
    expr = (expr or '').strip()
    if not expr:
        return []
    out = []
    if expr.startswith('import '):
        for part in expr[len('import '):].split(','):
            part = part.strip()
            if not part:
                continue
            if ' as ' in part:
                mod, alias = [s.strip() for s in part.split(' as ', 1)]
            else:
                mod, alias = part, None
            # import a.b.c binds 'a'; the module path is the full dotted name
            top = mod.split('.')[0]
            out.append({'module': mod, 'name': alias or top,
                        'level': 0, 'kind': 'import'})
        return out
    if expr.startswith('from '):
        rest = expr[len('from '):]
        if ' import ' not in rest:
            return []
        mod_part, names_part = rest.split(' import ', 1)
        mod_part = mod_part.strip()
        level = 0
        while mod_part.startswith('.'):
            level += 1
            mod_part = mod_part[1:]
        module = mod_part.strip()
        for part in names_part.split(','):
            part = part.strip()
            if not part:
                continue
            if ' as ' in part:
                name, alias = [s.strip() for s in part.split(' as ', 1)]
            else:
                name, alias = part, part
            out.append({'module': module, 'name': name, 'alias': alias,
                        'level': level, 'kind': 'from'})
        return out
    return []


def _module_source(file_path: str) -> Optional[str]:
    """Best-effort read of a module's source for AST-level facts."""
    candidates = [Path(file_path)]
    try:
        from .. import config
        root = getattr(config, 'REPO_ROOT', None)
        if root:
            candidates.append(Path(root) / file_path)
    except Exception:
        pass
    for c in candidates:
        try:
            if c.is_file():
                return c.read_text(encoding='utf-8')
        except Exception:
            continue
    return None


def _function_line_ranges(tree: ast.AST) -> List[Tuple[int, int]]:
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.lineno is not None:
            ranges.append((node.lineno, node.end_lineno or node.lineno))
    return ranges


def _all_exports(tree: ast.AST) -> Optional[List[str]]:
    """__all__ when it is a statically-known list/tuple of strings."""
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and t.id == '__all__' \
                    and isinstance(node.value, (ast.List, ast.Tuple)):
                names = [e.value for e in node.value.elts
                         if isinstance(e, ast.Constant)
                         and isinstance(e.value, str)]
                if len(names) == len(node.value.elts):
                    return names
    return None


def _top_level_public_names(tree: ast.AST) -> List[str]:
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            if not node.name.startswith('_'):
                names.append(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and not t.id.startswith('_'):
                    names.append(t.id)
        elif isinstance(node, ast.Import):
            for a in node.names:
                bound = (a.asname or a.name).split('.')[0]
                if not bound.startswith('_'):
                    names.append(bound)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == '*':
                    continue
                bound = a.asname or a.name
                if not bound.startswith('_'):
                    names.append(bound)
    return names


@dataclass
class ModuleSummary:
    """Summary of a module for cross-file analysis."""
    module_id: str  # File path or module name
    file_path: str
    top_level_definitions: List[str]  # Definition IDs at module level
    global_writes: List[str]  # Definitions that write to globals
    imports: List[str]  # Imported modules (raw import expressions)
    exports: List[str]  # Names exported from this module
    metadata: Dict[str, Any] = field(default_factory=dict)


class CrossModuleAnalyzer:
    """
    Analyze cross-file and cross-module data flow.

    Handles:
    - Module-level facts (top-level assignments, globals)
    - Import resolution and cross-module references
    - Global variable propagation across files
    """

    def __init__(self, graph_ctx: Optional[Dict[str, Any]] = None,
                 resolver=None):
        self._module_summaries: Dict[str, ModuleSummary] = {}
        self._import_graph: Dict[str, Set[str]] = {}  # module -> set of imports
        # graph_ctx is the indexer's repository-wide context
        # (module_files, file_symbols, node_ids, ...). Without it every
        # import resolves as external/unresolved.
        self._graph_ctx = graph_ctx or {}
        self._resolver = resolver
        if self._resolver is None and graph_ctx is not None:
            try:
                from ..resolvers.python_resolver import PythonResolver
                self._resolver = PythonResolver()
            except Exception:
                self._resolver = None

    def analyze_module(
        self,
        facts: DefUseFacts,
        file_path: str
    ) -> ModuleSummary:
        """
        Analyze a module (file) for cross-file propagation.

        Returns a ModuleSummary with top-level definitions and imports.
        """
        module_id = file_path

        # Real top-level check: a definition is module-level only when it is
        # not inside any FunctionDef/AsyncFunctionDef body. DefUseFacts has
        # no scope field, so the ranges come from the module AST.
        tree = None
        source = _module_source(file_path)
        if source:
            try:
                tree = ast.parse(source)
            except Exception:
                tree = None
        fn_ranges = _function_line_ranges(tree) if tree is not None else []

        def _is_top_level(d: Definition) -> bool:
            if not fn_ranges:
                # No AST available: keep the previous conservative behaviour
                # only for definitions that are not function-scoped. Facts
                # from per-function extraction carry the function id; module
                # facts do not.
                return not (d.function_id and '::' in d.function_id
                            and d.function_id != file_path)
            return not any(lo <= d.line <= hi for lo, hi in fn_ranges)

        top_level_defs = []
        global_writes = []
        top_level_names = set()

        for definition in facts.definitions:
            if not _is_top_level(definition):
                continue
            top_level_defs.append(definition.id)
            top_level_names.add(definition.variable)
            # Global writes: explicit `global x` statements surface through
            # the is_global metadata; binding keys of the form file::name
            # written at module level are module globals by construction.
            if definition.metadata.get('is_global') \
                    or definition.binding_key.startswith('%s::' % file_path):
                global_writes.append(definition.id)

        # Extract imports from operations, keeping both the raw expressions
        # and the parsed resolver dicts.
        imports = []
        import_details = []
        for operation in facts.operations:
            if operation.operation in ('Import', 'ImportFrom'):
                imports.append(operation.expression)
                import_details.extend(_parse_import_expr(operation.expression))

        exports = _all_exports(tree) if tree is not None else None
        if exports is None and tree is not None:
            exports = _top_level_public_names(tree)
        if exports is None:
            exports = sorted(n for n in top_level_names if not n.startswith('_'))

        summary = ModuleSummary(
            module_id=module_id,
            file_path=file_path,
            top_level_definitions=top_level_defs,
            global_writes=global_writes,
            imports=imports,
            exports=exports,
            metadata={'import_details': import_details}
        )

        self._module_summaries[module_id] = summary
        self._import_graph[module_id] = {d['module'] for d in import_details
                                         if d.get('module')}

        return summary

    def resolve_import(
        self,
        import_name,
        source_module: str
    ) -> Optional[str]:
        """
        Resolve an import to a target module.

        Delegates to the Python resolver (python_resolver._resolve_import_target).
        Returns the repo-relative file path for in-repo modules, the marker
        'external' for third-party/stdlib modules, and None only when the
        import cannot be resolved at all. ``import_name`` may be a raw import
        expression string or an already-parsed imp dict.
        """
        if isinstance(import_name, dict):
            details = [dict(import_name)]
        else:
            details = _parse_import_expr(str(import_name))
            if not details:
                # A bare dotted name is treated as `import <name>`.
                details = [{'module': str(import_name), 'name': None,
                            'level': 0, 'kind': 'import'}]
        for imp in details:
            if imp.get('kind') == 'import' and not imp.get('name'):
                imp['name'] = (imp.get('module') or '').split('.')[0] or None
        if self._resolver is None or self._graph_ctx is None:
            return None
        results = []
        for imp in details:
            try:
                _sid, kind, resolved_file = self._resolver._resolve_import_target(
                    imp, source_module, self._graph_ctx)
            except Exception:
                continue
            if kind == 'external':
                results.append(EXTERNAL)
            elif resolved_file:
                results.append(resolved_file)
            # 'unresolved'/'star' without a file contribute nothing
        if not results:
            return None
        # Prefer an in-repo file over the external marker.
        for r in results:
            if r != EXTERNAL:
                return r
        return EXTERNAL

    def propagate_globals(
        self,
        all_summaries: Dict[str, ModuleSummary]
    ) -> Dict[str, Any]:
        """
        Propagate global variable definitions across modules via a worklist
        over the resolved import graph.

        Only imports that resolve to an in-repo file propagate; unresolved
        and external imports are recorded in 'unresolved_imports', never
        skipped silently.

        Returns {'global_usage': module -> set of global definition ids,
                 'unresolved_imports': [module, import, reason]}.
        """
        global_usage: Dict[str, Set[str]] = {}
        unresolved_imports: List[Dict[str, str]] = []

        # Resolve each module's imports once.
        resolved: Dict[str, Dict[str, Optional[str]]] = {}
        for module_id, summary in all_summaries.items():
            per_import: Dict[str, Optional[str]] = {}
            details = (summary.metadata or {}).get('import_details') or []
            for imp in details:
                key = '%s:%s' % (imp.get('module'), imp.get('name'))
                target = self.resolve_import(imp, module_id)
                per_import[key] = target
                if target is None:
                    unresolved_imports.append({
                        'module': module_id,
                        'import': key,
                        'reason': 'unresolved',
                    })
                elif target == EXTERNAL:
                    unresolved_imports.append({
                        'module': module_id,
                        'import': key,
                        'reason': 'external',
                    })
            resolved[module_id] = per_import

        # Worklist propagation: a module uses the top-level definitions of
        # every in-repo module reachable through resolved imports.
        for module_id in all_summaries:
            used: Set[str] = set()
            seen = {module_id}
            worklist = [module_id]
            while worklist:
                cur = worklist.pop()
                for target in resolved.get(cur, {}).values():
                    if not target or target == EXTERNAL \
                            or target not in all_summaries \
                            or target in seen:
                        continue
                    seen.add(target)
                    worklist.append(target)
                    used.update(all_summaries[target].top_level_definitions)
                    used.update(all_summaries[target].global_writes)
            global_usage[module_id] = used

        return {'global_usage': global_usage,
                'unresolved_imports': unresolved_imports}

    def resolve_symbol(
        self,
        importer_file: str,
        local_name: str
    ) -> Optional[Tuple[str, Optional[str]]]:
        """Resolve a name used in ``importer_file`` to (target_file,
        target_name) through that module's recorded imports.

        Handles ``from x import y as z`` (local_name 'z' -> (x.py, 'y')),
        relative imports and ``import mod`` / ``import mod as m``
        (local_name 'm' -> (mod.py, None) — the module itself). Returns None
        when no import binds the name or the target is not in the repo.
        """
        summary = self._module_summaries.get(importer_file)
        if summary is None:
            return None
        for imp in (summary.metadata or {}).get('import_details') or []:
            bound = imp.get('alias') or imp.get('name')
            if bound != local_name:
                continue
            target = self.resolve_import(imp, importer_file)
            if not target or target == EXTERNAL:
                return None
            if imp.get('kind') == 'from':
                return (target, imp.get('name'))
            return (target, None)
        return None

    def propagate_global_values(
        self,
        summaries: Dict[str, ModuleSummary],
        facts_by_file: Dict[str, DefUseFacts]
    ) -> Dict[str, Any]:
        """Turn resolved imports into value-level 'global' edges.

        For every import that resolves to an in-repo module, match the
        imported name against the exporting module's top-level definitions
        (by variable name), then to uses in the importing file whose
        variable equals the local alias (or ``alias.attr`` for
        ``import mod`` forms). Each confirmed match yields
        {'source': def_id, 'target': use_id, 'kind': 'global',
         'resolution': 'confirmed', 'file', 'line', 'target_file'}.
        Unresolved or external imports are reported, never emitted as edges.
        """
        edges: List[Dict[str, Any]] = []
        unresolved: List[Dict[str, Any]] = []

        for importer_file, summary in summaries.items():
            facts = facts_by_file.get(importer_file)
            if facts is None:
                continue
            details = (summary.metadata or {}).get('import_details') or []
            for imp in details:
                local = imp.get('alias') or imp.get('name')
                if not local:
                    continue
                kind = imp.get('kind')
                target = self.resolve_import(imp, importer_file)
                if target is None:
                    # Fallback: module-level names (constants, __init__
                    # re-exports) have no symbol node for the resolver, so
                    # resolve the module file directly from module_files.
                    mod = imp.get('module') or ''
                    module_files = self._graph_ctx.get('module_files') or {}
                    candidates = [mod]
                    pkg = importer_file.rsplit('/', 1)[0].replace('/', '.') \
                        if '/' in importer_file else ''
                    if pkg:
                        candidates.insert(0, '%s.%s' % (pkg, mod) if mod else pkg)
                    for cand in candidates:
                        if cand and cand in module_files:
                            target = module_files[cand]
                            break
                if not target or target == EXTERNAL \
                        or target not in summaries:
                    unresolved.append({
                        'module': importer_file,
                        'import': '%s:%s' % (imp.get('module'), local),
                        'reason': 'external' if target == EXTERNAL
                                  else 'unresolved',
                    })
                    continue

                # Uses of the local alias, including alias.attr for
                # ``import mod`` style bindings.
                uses = [u for u in facts.uses
                        if u.variable == local
                        or u.variable.startswith(local + '.')]
                if not uses:
                    continue

                # Exporting module's top-level definitions by variable name.
                target_facts = facts_by_file.get(target)
                target_summary = summaries.get(target)
                top_ids = set(target_summary.top_level_definitions) \
                    if target_summary else set()
                by_var_top: Dict[str, Definition] = {}
                by_var_mod: Dict[str, Definition] = {}
                if target_facts is not None:
                    for d in target_facts.definitions:
                        if d.variable in by_var_mod:
                            continue
                        if d.id in top_ids:
                            by_var_top.setdefault(d.variable, d)
                        if d.function_id == target:
                            by_var_mod.setdefault(d.variable, d)

                for u in uses:
                    if kind == 'from':
                        tname = imp.get('name')
                    else:
                        tname = u.variable.split('.', 1)[1] \
                            if '.' in u.variable else None
                    td = by_var_top.get(tname) or by_var_mod.get(tname)
                    if td is None:
                        unresolved.append({
                            'module': importer_file,
                            'import': local,
                            'reason': 'no top-level definition %r in %s'
                                      % (tname, target),
                            'file': importer_file,
                            'line': u.line,
                        })
                        continue
                    edges.append({
                        'source': td.id,
                        'target': u.id,
                        'kind': 'global',
                        'resolution': 'confirmed',
                        'file': importer_file,
                        'line': u.line,
                        'target_file': target,
                    })

        return {'edges': edges, 'unresolved': unresolved}

    def get_module_summary(self, module_id: str) -> Optional[ModuleSummary]:
        """Get a module summary by ID."""
        return self._module_summaries.get(module_id)
