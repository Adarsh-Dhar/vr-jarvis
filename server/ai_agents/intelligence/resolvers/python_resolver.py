"""Python call resolver.

Resolution is evidence-based: every result carries the method that produced it
(``resolution_method``) and the source facts behind it (``evidence``). Nothing
here guesses a target from a bare name match — unresolved and dynamic calls are
reported honestly so the indexer never fabricates edges.
"""
import re
from typing import Dict, List, Optional, Tuple

from .base import (
    ResolverAdapter, FileContext, ResolutionResult,
    STATUS_STATIC_RESOLVED, STATUS_POLYMORPHIC, STATUS_AMBIGUOUS,
    STATUS_UNRESOLVED, STATUS_EXTERNAL, STATUS_DYNAMIC,
)
from .bindings import BindingTable, Binding
from ..parsers.python_ast import (
    analyze_python_source, DYNAMIC_CALL_NAMES, BUILTIN_NAMES,
)

_MAX_IMPORT_DEPTH = 4


def _strip_generics(expr: str) -> str:
    """``Optional[Payment]`` / ``list[X]`` -> keep only simple type names."""
    return re.sub(r'\[.*\]', '', expr).strip()


def _annotation_type_names(annotation: str) -> List[str]:
    """Extract candidate type names from an annotation string."""
    if not annotation:
        return []
    ann = annotation.strip()
    # Union[A, B] / Optional[A] / tuple[...]
    if ann.startswith('Union[') or ann.startswith('Optional['):
        inner = ann[ann.find('[') + 1:ann.rfind(']')]
        parts = [p.strip() for p in inner.split(',')]
        out = []
        for p in parts:
            out += _annotation_type_names(p)
        return [n for n in out if n and n != 'None']
    # A | B unions
    if '|' in ann:
        out = []
        for p in ann.split('|'):
            out += _annotation_type_names(p)
        return out
    # dotted name -> last component is the class name
    ann = _strip_generics(ann)
    if not ann:
        return []
    # strip quotes for string annotations
    ann = ann.strip('\'"')
    if ann in ('None', 'NoneType', 'Any', 'object'):
        return []
    return [ann.split('.')[-1]]


def _result(status, reason, targets=None, candidates=None, method='', evidence=None,
            dispatch='static', diagnostics=None):
    return ResolutionResult(
        status=status,
        targets=targets or [],
        candidates=candidates or [],
        reason=reason,
        resolution_method=method,
        evidence=evidence or [],
        dispatch_kind=dispatch,
        diagnostics=diagnostics or [],
    )


class PythonResolver(ResolverAdapter):
    language = 'python'

    def __init__(self):
        self._ctx_cache: Dict[str, Tuple[FileContext, BindingTable]] = {}
        self._mro_cache: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # context
    # ------------------------------------------------------------------
    def build_context(self, file_path: str, text: str, graph_nodes: List[Dict],
                      analysis: Optional[Dict] = None) -> FileContext:
        if analysis is None:
            analysis = analyze_python_source(text, file_path)

        classes = {}
        functions = {}
        for sym in analysis.get('symbols', []):
            entry = {
                'start': sym['start'], 'end': sym['end'], 'name': sym['name'],
                'qualname': sym['qualname'], 'kind': sym['kind'],
                'class_qualname': sym.get('class_qualname', ''),
                'bases': sym.get('bases', []),
            }
            if sym['kind'] == 'object':
                classes[sym['qualname']] = entry
            else:
                functions[sym['qualname']] = entry

        return FileContext(
            file_path=file_path,
            imports=analysis.get('imports', []),
            classes=classes,
            functions=functions,
            analysis=analysis,
            language='python',
        )

    # ------------------------------------------------------------------
    # graph-context helpers (module map, class index, symbol lookup)
    # ------------------------------------------------------------------
    @staticmethod
    def _module_files(graph_ctx: Dict) -> Dict[str, str]:
        return graph_ctx.get('module_files', {})

    @staticmethod
    def _node_ids(graph_ctx: Dict) -> set:
        return graph_ctx.get('node_ids', set())

    def _file_symbols(self, graph_ctx: Dict, rel: str) -> List[dict]:
        return graph_ctx.get('file_symbols', {}).get(rel, [])

    def _top_level_symbol(self, graph_ctx: Dict, rel: str, name: str) -> Optional[str]:
        """Find ``rel::name`` for a top-level function or class in a file."""
        for sym in self._file_symbols(graph_ctx, rel):
            if sym.get('qualname') == name and sym.get('kind') in ('function', 'method', 'object'):
                sid = sym.get('id') or f'{rel}::{name}'
                if sid in self._node_ids(graph_ctx):
                    return sid
        return None

    def _resolve_module_file(self, dotted: str, graph_ctx: Dict) -> Optional[str]:
        """Resolve a dotted module path to a repo-relative file."""
        return self._module_files(graph_ctx).get(dotted)

    def _resolve_relative_module(self, level: int, module: str, file_path: str,
                                 graph_ctx: Dict) -> str:
        """Resolve a relative import to an absolute dotted module path."""
        parts = file_path.replace('\\', '/')[:-3].split('/') if file_path.endswith('.py') else []
        if parts and parts[-1] == '__init__':
            parts = parts[:-1]
        # level=1 means "current package": drop `level` trailing components? For
        # pkg/mod.py, level=1 -> pkg; for pkg/__init__.py (parts=pkg), level=1 -> pkg.
        drop = level  # level counts dots: 1 -> stay in current package dir
        # current package = directory containing the module (or the package itself for __init__)
        if file_path.endswith('__init__.py'):
            base = parts  # already the package parts
        else:
            base = parts[:-1]
        keep = max(0, len(base) - (level - 1))
        base = base[:keep]
        dotted = '.'.join(base + ([module] if module else []))
        return dotted

    def _resolve_import_target(self, imp: Dict, file_path: str,
                               graph_ctx: Dict, depth: int = 0) -> Tuple[Optional[str], str, str]:
        """Resolve one import statement to (symbol_id, kind, resolved_file).

        kind is 'symbol' | 'module' | 'unresolved' | 'external'.
        """
        module = imp.get('module') or ''
        name = imp.get('name')
        level = imp.get('level', 0) or 0
        kind_imp = imp.get('kind', 'import')

        if level:
            module = self._resolve_relative_module(level, module, file_path, graph_ctx)
        elif kind_imp == 'import':
            module = module
        # for 'from X import Y', module is X; for 'import X', module is X

        module_file = self._resolve_module_file(module, graph_ctx) if module else None

        if kind_imp == 'import':
            # import X [as Y]  -> module binding (possibly submodule attribute later)
            if module_file:
                return None, 'module', module_file
            # maybe it's a package whose __init__ exists under another key
            return None, 'external' if module else 'unresolved', ''

        # from X import Y [as Z]
        if name is None:
            return None, 'unresolved', ''
        if name == '*':
            return None, 'star', module_file or ''

        # Y may be a submodule: X.Y
        submodule = f'{module}.{name}' if module else name
        sub_file = self._resolve_module_file(submodule, graph_ctx)
        if sub_file and kind_imp == 'from':
            # `from pkg import submod` -> module binding
            # but `from pkg.mod import func` -> func is symbol in pkg/mod.py
            # Distinguish: if X.Y resolves to a file AND X also resolves to a file
            # whose symbols don't contain Y, treat as module.
            if module_file:
                # does module_file define symbol `name`?
                if self._top_level_symbol(graph_ctx, module_file, name):
                    pass  # symbol wins
                else:
                    return None, 'module', sub_file
            else:
                return None, 'module', sub_file

        if module_file:
            sid = self._top_level_symbol(graph_ctx, module_file, name)
            if sid:
                return sid, 'symbol', module_file
            # re-export: target file imports `name` itself
            if depth < _MAX_IMPORT_DEPTH:
                for sub in self._file_symbols(graph_ctx, module_file):
                    pass
                reexp = self._find_reexport(module_file, name, graph_ctx, depth + 1)
                if reexp:
                    return reexp
            return None, 'unresolved', module_file

        # module itself unresolved -> external (third-party/stdlib) unless relative
        if level:
            return None, 'unresolved', ''
        return None, 'external', ''

    def _find_reexport(self, rel: str, name: str, graph_ctx: Dict, depth: int) -> Optional[str]:
        """Follow ``from z import name`` chains inside ``rel`` (re-exports)."""
        analysis = graph_ctx.get('analyses', {}).get(rel)
        if not analysis:
            return None
        for imp in analysis.get('imports', []):
            if imp.get('kind') == 'from' and imp.get('name') == name:
                sid, k, _ = self._resolve_import_target(imp, rel, graph_ctx, depth)
                if k == 'symbol' and sid:
                    return sid
        return None

    # ------------------------------------------------------------------
    # binding table
    # ------------------------------------------------------------------
    def _binding_table(self, file_ctx: FileContext, graph_ctx: Dict) -> BindingTable:
        cached = self._ctx_cache.get(file_ctx.file_path)
        if cached and cached[0] is file_ctx:
            return cached[1]

        table = BindingTable(file_ctx.file_path)
        analysis = file_ctx.analysis or {}
        symbols = analysis.get('symbols', [])

        def _sid(sym):
            return sym.get('id') or f"{file_ctx.file_path}::{sym['qualname']}"

        # register every scope first, then wire parents (order-independent)
        id_to_parent = {}
        for sym in symbols:
            sid = _sid(sym)
            table.add_scope(sid)
            parent_q = sym.get('parent_qualname') or ''
            id_to_parent[sid] = f"{file_ctx.file_path}::{parent_q}" if parent_q else ''
        for sid, pid in id_to_parent.items():
            if pid:
                table.scope_parent[sid] = pid

        # imports -> bindings (module scope)
        for imp in file_ctx.imports:
            alias = imp.get('alias')
            name = imp.get('name')
            kind_imp = imp.get('kind', 'import')
            module = imp.get('module') or ''
            level = imp.get('level', 0) or 0
            line = imp.get('line', 0)

            bound_name = alias or (name if kind_imp == 'from' else module.split('.')[-1])
            if not bound_name:
                continue

            if kind_imp == 'import':
                # resolve dotted module possibly relative (imports can't be relative
                # in `import x` form, but be safe)
                dotted = module
                if level:
                    dotted = self._resolve_relative_module(level, module, file_ctx.file_path, graph_ctx)
                mfile = self._resolve_module_file(dotted, graph_ctx) if dotted else None
                table.add_binding(Binding(
                    name=bound_name, symbol_id='', kind='module',
                    scope_id='', start_line=line, module=dotted,
                    resolved_file=mfile or '',
                ))
                continue

            # from X import Y [as Z]
            dotted = module
            if level:
                dotted = self._resolve_relative_module(level, module, file_ctx.file_path, graph_ctx)
            sid, k, rfile = self._resolve_import_target(
                {**imp, 'module': dotted, 'level': 0}, file_ctx.file_path, graph_ctx)
            if k == 'symbol' and sid:
                table.add_binding(Binding(
                    name=bound_name, symbol_id=sid,
                    kind='alias' if alias else 'import',
                    scope_id='', start_line=line, module=dotted,
                    imported_name=name or '', resolved_file=rfile,
                ))
            elif k == 'module':
                # `from pkg import submod` -> module binding for `submod`
                sub_dotted = f'{dotted}.{name}' if dotted else name
                table.add_binding(Binding(
                    name=bound_name, symbol_id='', kind='module',
                    scope_id='', start_line=line, module=sub_dotted,
                    imported_name=name or '', resolved_file=rfile,
                ))
            elif k == 'star':
                table.add_binding(Binding(
                    name='*', symbol_id='', kind='star',
                    scope_id='', start_line=line, module=dotted, resolved_file=rfile,
                ))
            else:
                # unresolved/external import: record so calls can be classified
                table.add_binding(Binding(
                    name=bound_name, symbol_id='',
                    kind='external' if k == 'external' else 'unresolved_import',
                    scope_id='', start_line=line, module=dotted or module,
                    imported_name=name or '', resolved_file=rfile,
                ))

        # module-level functions/classes as bindings (they shadow earlier imports
        # when defined later in the file — resolve_name picks latest start_line)
        for sym in symbols:
            if not sym.get('parent_qualname'):
                sid = sym.get('id') or f"{file_ctx.file_path}::{sym['qualname']}"
                kind = 'class' if sym['kind'] == 'object' else 'local'
                table.add_binding(Binding(
                    name=sym['name'], symbol_id=sid, kind=kind,
                    scope_id='', start_line=sym['start'],
                ))
            elif sym.get('kind') in ('function', 'method'):
                # nested function: bind inside its parent scope
                parent_q = sym.get('parent_qualname') or ''
                parent_id = f"{file_ctx.file_path}::{parent_q}" if parent_q else ''
                sid = sym.get('id') or f"{file_ctx.file_path}::{sym['qualname']}"
                table.add_binding(Binding(
                    name=sym['name'], symbol_id=sid, kind='nested',
                    scope_id=parent_id, start_line=sym['start'],
                ))

        # parameters of each function as 'param' bindings in that function's scope
        for sym in symbols:
            if sym.get('kind') in ('function', 'method'):
                sid = _sid(sym)
                for p in sym.get('parameters') or []:
                    table.add_binding(Binding(
                        name=p, symbol_id='', kind='param',
                        scope_id=sid, start_line=sym['start'],
                    ))
        self._ctx_cache[file_ctx.file_path] = (file_ctx, table)
        return table

    # ------------------------------------------------------------------
    # class / MRO helpers
    # ------------------------------------------------------------------
    def _class_symbol(self, graph_ctx: Dict, class_id: str) -> Optional[dict]:
        for n in graph_ctx.get('nodes', []):
            if n.get('id') == class_id:
                return n
        return None

    def _resolve_class_name(self, name: str, file_path: str, graph_ctx: Dict,
                            imports_hint: Optional[List[Dict]] = None) -> List[str]:
        """Resolve a class name to candidate class symbol ids."""
        short = name.split('.')[-1]
        short = _strip_generics(short)
        if not short:
            return []
        candidates = list(graph_ctx.get('class_by_name', {}).get(short, []))
        if not candidates:
            return []
        if len(candidates) == 1:
            return candidates
        # prefer same file, then imported file, then unique remainder
        same_file = [c for c in candidates
                     if (self._class_file(graph_ctx, c) == file_path)]
        if len(same_file) == 1:
            return same_file
        if same_file:
            return same_file
        # check explicit imports of this name
        imported_files = set()
        for imp in (imports_hint or []):
            if imp.get('kind') == 'from' and (imp.get('name') == short or imp.get('alias') == short):
                dotted = imp.get('module') or ''
                if imp.get('level'):
                    dotted = self._resolve_relative_module(imp['level'], dotted, file_path, graph_ctx)
                mf = self._resolve_module_file(dotted, graph_ctx)
                if mf:
                    imported_files.add(mf)
        imported = [c for c in candidates if self._class_file(graph_ctx, c) in imported_files]
        if imported:
            return imported
        return candidates

    @staticmethod
    def _class_file(graph_ctx: Dict, class_id: str) -> str:
        node = graph_ctx.get('symbol_by_id', {}).get(class_id)
        return node.get('file', '') if node else ''

    def resolve_base_class_ids(self, base_exprs: List[str], file_path: str,
                               graph_ctx: Dict) -> List[str]:
        """Resolve base-class expressions to class symbol ids (best effort)."""
        out = []
        for expr in base_exprs or []:
            expr = (expr or '').strip()
            if not expr or expr == 'object':
                continue
            expr = re.sub(r'\[.*\]', '', expr).strip()
            if '.' in expr:
                mod, _, cls = expr.rpartition('.')
                mf = self._resolve_module_file(mod, graph_ctx)
                if mf:
                    ids = [c for c in graph_ctx.get('class_by_name', {}).get(cls, [])
                           if self._class_file(graph_ctx, c) == mf]
                    out.extend(ids or [c for c in graph_ctx.get('class_by_name', {}).get(cls, [])])
                    continue
            out.extend(self._resolve_class_name(expr, file_path, graph_ctx))
        # dedupe preserving order
        seen, res = set(), []
        for c in out:
            if c not in seen:
                seen.add(c)
                res.append(c)
        return res

    def _mro(self, class_id: str, graph_ctx: Dict) -> List[str]:
        """Approximate C3 MRO: class first, then bases depth-first, deduped."""
        if class_id in self._mro_cache:
            return self._mro_cache[class_id]
        classes = graph_ctx.get('classes_info', {})
        info = classes.get(class_id)
        if not info:
            self._mro_cache[class_id] = [class_id]
            return [class_id]
        result = [class_id]
        for base in info.get('base_ids', []):
            for c in self._mro(base, graph_ctx):
                if c not in result:
                    result.append(c)
        self._mro_cache[class_id] = result
        return result

    def _method_in_class(self, class_id: str, name: str, graph_ctx: Dict) -> Optional[str]:
        """Find ``name`` defined directly on class ``class_id`` (not inherited)."""
        node = graph_ctx.get('symbol_by_id', {}).get(class_id)
        if not node:
            return None
        qual = node.get('qualname') or node.get('class_name', '')
        file = node.get('file', '')
        if not qual or not file:
            return None
        sid = f'{file}::{qual}.{name}'
        ids = self._node_ids(graph_ctx)
        if sid in ids:
            return sid
        return None

    def _lookup_method_mro(self, class_id: str, name: str, graph_ctx: Dict) -> List[str]:
        """All implementations of ``name`` reachable from ``class_id``'s MRO,
        plus overrides in known subclasses (virtual dispatch candidates)."""
        impls = []
        for c in self._mro(class_id, graph_ctx):
            sid = self._method_in_class(c, name, graph_ctx)
            if sid:
                impls.append(sid)
                break  # MRO: first definition wins for the static target
        # subclass overrides are additional runtime candidates
        for sub in graph_ctx.get('subclasses', {}).get(class_id, []):
            for c in self._mro(sub, graph_ctx):
                sid = self._method_in_class(c, name, graph_ctx)
                if sid and sid not in impls:
                    impls.append(sid)
        return impls

    # ------------------------------------------------------------------
    # scope facts
    # ------------------------------------------------------------------
    def _caller_symbol(self, file_ctx: FileContext, call: Dict) -> Optional[dict]:
        caller_id = call.get('caller_id')
        if not caller_id:
            return None
        for sym in (file_ctx.analysis or {}).get('symbols', []):
            if (sym.get('id') or f"{file_ctx.file_path}::{sym['qualname']}") == caller_id:
                return sym
        return None

    def _scope_facts(self, file_ctx: FileContext, qualname: str) -> dict:
        return (file_ctx.analysis or {}).get('scopes', {}).get(qualname, {})

    def _enclosing_class_qualname(self, sym: Optional[dict]) -> str:
        if not sym:
            return ''
        return sym.get('class_qualname') or ''

    def _self_attr_types(self, file_ctx: FileContext, class_qualname: str,
                         attr: str) -> List[str]:
        """Collect ``self.<attr> = T()`` types across all methods of a class."""
        types = []
        for sym in (file_ctx.analysis or {}).get('symbols', []):
            if sym.get('class_qualname') == class_qualname:
                facts = self._scope_facts(file_ctx, sym['qualname'])
                for t in facts.get('self_attr_types', {}).get(attr, []):
                    if t not in types:
                        types.append(t)
        return types

    def _receiver_types(self, call: Dict, file_ctx: FileContext,
                        graph_ctx: Dict) -> Tuple[List[str], str]:
        """Infer possible runtime types for the call receiver.

        Returns (type_names, origin) where origin is 'assignment', 'annotation',
        'self_attr', 'param' or 'unknown'.
        """
        receiver = call.get('receiver') or ''
        root = call.get('receiver_root') or ''
        caller = self._caller_symbol(file_ctx, call)
        facts = self._scope_facts(file_ctx, caller['qualname']) if caller else {}

        if root == 'self':
            # self.service.execute() -> attribute type; self.m() handled elsewhere
            parts = receiver.split('.')
            if len(parts) >= 2:
                attr = parts[1]
                cls_q = self._enclosing_class_qualname(caller)
                types = self._self_attr_types(file_ctx, cls_q, attr)
                if types:
                    return types, 'self_attr'
            return [], 'unknown'

        if not root:
            return [], 'unknown'

        # parameter annotation: payment: Payment
        ann = facts.get('param_types', {}).get(root)
        if ann:
            return _annotation_type_names(ann), 'annotation'

        # local constructor assignments / annotated assignments
        local = facts.get('local_types', {}).get(root)
        if local:
            return list(local), 'assignment'

        return [], 'unknown'

    # ------------------------------------------------------------------
    # main resolution
    # ------------------------------------------------------------------
    def resolve(self, call: Dict, file_ctx: FileContext, graph_ctx: Dict) -> ResolutionResult:
        name = call.get('name') or ''
        receiver = call.get('receiver') or ''
        receiver_root = call.get('receiver_root') or ''
        call_type = call.get('call_type') or 'direct'
        line = call.get('line', 0)
        evidence = [{'type': 'ast_call', 'file': file_ctx.file_path,
                     'line': line, 'column': call.get('column', 0)}]

        if not name:
            return _result(STATUS_UNRESOLVED, 'Empty callee name', method='none', evidence=evidence)

        # ---- dynamic constructs -------------------------------------------
        if call_type == 'dynamic' or name in DYNAMIC_CALL_NAMES:
            return _result(STATUS_DYNAMIC,
                           f'Dynamic call construct ({name or call_type}) cannot be resolved statically',
                           method='dynamic_detect', dispatch='dynamic', evidence=evidence,
                           diagnostics=['dynamic_construct'])

        table = self._binding_table(file_ctx, graph_ctx)
        caller = self._caller_symbol(file_ctx, call)
        caller_qual = caller['qualname'] if caller else ''
        scope_id = call.get('caller_id') or ''
        class_qual = self._enclosing_class_qualname(caller)

        # ---- super() -------------------------------------------------------
        if call_type == 'super' or receiver_root == 'super':
            return self._resolve_super(name, class_qual, file_ctx, graph_ctx, evidence)

        # ---- self / cls ----------------------------------------------------
        if receiver_root in ('self', 'cls') and receiver in ('self', 'cls'):
            return self._resolve_self_method(name, class_qual, file_ctx, graph_ctx, evidence)

        # ---- module-qualified: payments.validate(), pkg.mod.func() --------
        module_hit = self._resolve_module_member(call, file_ctx, graph_ctx, evidence)
        if module_hit is not None:
            return module_hit

        # ---- typed receiver: payment.process(), self.service.execute() ----
        if receiver:
            typed = self._resolve_typed_receiver(call, file_ctx, graph_ctx, table, evidence)
            if typed is not None:
                return typed
            # receiver exists but type unknown -> unresolved (no name guessing)
            return _result(
                STATUS_UNRESOLVED,
                f'Cannot determine type of receiver "{receiver}"',
                method='receiver_type', evidence=evidence,
                diagnostics=['unknown_receiver_type'])

        # ---- direct call ----------------------------------------------------
        return self._resolve_direct(name, file_ctx, graph_ctx, table, scope_id, line,
                                    caller, evidence)

    # ------------------------------------------------------------------
    # resolution strategies
    # ------------------------------------------------------------------
    def _resolve_super(self, name, class_qual, file_ctx, graph_ctx, evidence):
        if not class_qual:
            return _result(STATUS_UNRESOLVED, 'super() outside a class method',
                           method='super', evidence=evidence)
        # find class id for class_qual in this file
        class_id = f"{file_ctx.file_path}::{class_qual}"
        if class_id not in self._node_ids(graph_ctx):
            return _result(STATUS_UNRESOLVED, f'Class {class_qual} not found',
                           method='super', evidence=evidence)
        mro = self._mro(class_id, graph_ctx)
        # skip the enclosing class itself
        for c in mro[1:]:
            sid = self._method_in_class(c, name, graph_ctx)
            if sid:
                return _result(STATUS_STATIC_RESOLVED, f'super().{name} -> {sid}',
                               targets=[sid], method='mro_super', evidence=evidence,
                               dispatch='virtual')
        return _result(STATUS_UNRESOLVED, f'No base class defines {name}',
                       method='mro_super', evidence=evidence)

    def _resolve_self_method(self, name, class_qual, file_ctx, graph_ctx, evidence):
        if not class_qual:
            return _result(STATUS_UNRESOLVED, 'self/cls call outside a class method',
                           method='self_method', evidence=evidence)
        class_id = f"{file_ctx.file_path}::{class_qual}"
        if class_id not in self._node_ids(graph_ctx):
            # class may be nested: try suffix match on qualname
            matches = [c for c in graph_ctx.get('class_by_name', {}).get(class_qual.split('.')[-1], [])
                       if self._class_file(graph_ctx, c) == file_ctx.file_path]
            if matches:
                class_id = matches[0]
            else:
                return _result(STATUS_UNRESOLVED, f'Class {class_qual} not found',
                               method='self_method', evidence=evidence)
        impls = self._lookup_method_mro(class_id, name, graph_ctx)
        if not impls:
            return _result(STATUS_UNRESOLVED, f'No method {name} on {class_qual} or bases',
                           method='self_method', evidence=evidence)
        if len(impls) == 1:
            return _result(STATUS_STATIC_RESOLVED, f'self.{name} -> {impls[0]}',
                           targets=impls, method='self_method', evidence=evidence,
                           dispatch='virtual')
        return _result(STATUS_POLYMORPHIC,
                       f'self.{name} has {len(impls)} possible implementations',
                       targets=[impls[0]], candidates=impls, method='self_method',
                       evidence=evidence, dispatch='virtual')

    def _resolve_module_member(self, call, file_ctx, graph_ctx, evidence):
        """Handle ``module.attr()`` where module is an import binding or a
        dotted module path. Returns None when the receiver is not a module."""
        receiver = call.get('receiver') or ''
        name = call.get('name') or ''
        if not receiver:
            return None
        receiver_root = call.get('receiver_root') or ''

        table = self._binding_table(file_ctx, graph_ctx)

        # candidate dotted paths: full receiver expr, then root
        candidates = []
        if receiver:
            candidates.append(receiver)
        if receiver_root and receiver_root != receiver:
            candidates.append(receiver_root)

        for dotted in candidates:
            # is `dotted` an imported module alias?
            module_dotted = table.resolve_module_name(dotted)
            if module_dotted is None and '.' not in dotted:
                # maybe `import a.b` bound as 'a' -> module 'a.b'; receiver 'a.b.c'
                # try progressively: module_bindings has bound names only
                module_dotted = table.module_bindings.get(dotted)
            if module_dotted is None:
                # treat receiver itself as a dotted module path in the repo
                mf = self._resolve_module_file(dotted, graph_ctx)
                if mf:
                    module_dotted, module_file = dotted, mf
                else:
                    continue
            else:
                module_file = self._resolve_module_file(module_dotted, graph_ctx)

            if not module_file:
                # imported module that does not exist in the repo -> external
                return _result(STATUS_EXTERNAL,
                               f'Call on external module "{dotted}"',
                               method='module_import', dispatch='external',
                               evidence=evidence, diagnostics=['external_module'])

            # remaining attribute path after the module: e.g. receiver 'pkg.mod'
            # resolved to file; `name` is the member being called.
            sid = self._top_level_symbol(graph_ctx, module_file, name)
            if sid:
                return _result(STATUS_STATIC_RESOLVED,
                               f'module.{name} -> {sid}', targets=[sid],
                               method='module_import', evidence=evidence)
            # member may itself be a submodule: module.name
            sub = f'{module_dotted}.{name}' if module_dotted else name
            sub_file = self._resolve_module_file(sub, graph_ctx)
            if sub_file:
                return _result(STATUS_EXTERNAL,
                               f'Call on submodule {sub} (module object)',
                               method='module_import', dispatch='external',
                               evidence=evidence, diagnostics=['module_object_call'])
            return _result(STATUS_UNRESOLVED,
                           f'Module {module_file} has no symbol {name}',
                           method='module_import', evidence=evidence,
                           diagnostics=['module_member_missing'])
        return None

    def _resolve_typed_receiver(self, call, file_ctx, graph_ctx, table, evidence):
        receiver = call.get('receiver') or ''
        name = call.get('name') or ''
        root = call.get('receiver_root') or ''

        type_names, origin = self._receiver_types(call, file_ctx, graph_ctx)
        if not type_names:
            return None  # unknown -> caller reports unresolved

        # resolve each type name to class ids
        class_ids = []
        ambiguous_classes = []
        for t in type_names:
            ids = self._resolve_class_name(t, file_ctx.file_path, graph_ctx, file_ctx.imports)
            if not ids:
                # maybe imported via `import mod` then `mod.Class()` assignment
                # local_types already store bare class names; try graph-wide unique
                ids = self._resolve_class_name(t, file_ctx.file_path, graph_ctx, file_ctx.imports)
            if ids:
                class_ids.extend(ids)
            else:
                ambiguous_classes.append(t)

        # dedupe
        seen, uniq = set(), []
        for c in class_ids:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        class_ids = uniq

        if not class_ids:
            return _result(STATUS_UNRESOLVED,
                           f'Type(s) {type_names} for receiver "{receiver}" not found in repo',
                           method='type_inference', evidence=evidence,
                           diagnostics=['type_not_found'])

        # gather method implementations across all candidate classes
        impls = []
        for cid in class_ids:
            for sid in self._lookup_method_mro(cid, name, graph_ctx):
                if sid not in impls:
                    impls.append(sid)

        if not impls:
            return _result(STATUS_UNRESOLVED,
                           f'No method {name} on type(s) {type_names}',
                           method='type_inference', evidence=evidence,
                           diagnostics=['method_not_on_type'])

        concrete = origin == 'assignment' and len(type_names) == 1 and len(class_ids) == 1
        if len(impls) == 1:
            return _result(STATUS_STATIC_RESOLVED,
                           f'{receiver}.{name} -> {impls[0]} (type {type_names})',
                           targets=impls, method='type_inference', evidence=evidence,
                           dispatch='virtual' if not concrete else 'static')
        return _result(STATUS_POLYMORPHIC,
                       f'{receiver}.{name} has {len(impls)} possible implementations',
                       targets=[impls[0]], candidates=impls, method='type_inference',
                       evidence=evidence, dispatch='virtual')

    def _resolve_direct(self, name, file_ctx, graph_ctx, table, scope_id, line,
                        caller, evidence):
        ids = self._node_ids(graph_ctx)
        analysis = file_ctx.analysis or {}
        symbols = analysis.get('symbols', [])
        caller_qual = caller['qualname'] if caller else ''

        # 1. recursive / nested local function
        if caller_qual:
            own = f"{file_ctx.file_path}::{caller_qual}"
            if caller is not None and name == caller.get('name'):
                return _result(STATUS_STATIC_RESOLVED, 'Recursive self-call',
                               targets=[own], method='local_scope', evidence=evidence)
            for sym in symbols:
                if (sym.get('parent_qualname') == caller_qual and sym.get('name') == name
                        and sym.get('kind') in ('function', 'method')):
                    sid = sym.get('id') or f"{file_ctx.file_path}::{sym['qualname']}"
                    if sid in ids:
                        return _result(STATUS_STATIC_RESOLVED,
                                       f'Nested function {name}', targets=[sid],
                                       method='local_scope', evidence=evidence)

        # 2. bindings visible at this scope (imports, module defs, params, nested)
        bindings = table.resolve_name(name, scope_id=scope_id, line=line)
        best = bindings[0] if bindings else None
        if best:
            if best.kind == 'param':
                # callable parameter -> dynamic unless annotation gives a class
                ann = (self._scope_facts(file_ctx, caller_qual).get('param_types', {})
                       .get(name) if caller_qual else None)
                if ann:
                    tnames = _annotation_type_names(ann)
                    class_ids = []
                    for t in tnames:
                        class_ids.extend(self._resolve_class_name(t, file_ctx.file_path, graph_ctx, file_ctx.imports))
                    if class_ids:
                        sid = class_ids[0]
                        if sid in ids:
                            return _result(STATUS_STATIC_RESOLVED,
                                           f'Parameter {name}: {ann} -> {sid}',
                                           targets=[sid], method='param_annotation',
                                           evidence=evidence, dispatch='static')
                return _result(STATUS_DYNAMIC,
                               f'Parameter "{name}" is a callable value; target unknown',
                               method='param_binding', dispatch='dynamic',
                               evidence=evidence, diagnostics=['callable_param'])
            if best.kind in ('import', 'alias') and best.symbol_id:
                if best.symbol_id in ids:
                    return _result(STATUS_STATIC_RESOLVED,
                                   f'Import binding {name} -> {best.symbol_id}',
                                   targets=[best.symbol_id], method='import_binding',
                                   evidence=evidence)
                return _result(STATUS_UNRESOLVED,
                               f'Import binding {name} points outside indexed symbols',
                               method='import_binding', evidence=evidence)
            if best.kind == 'module':
                # `from pkg import mod` then calling mod() -> module object call
                return _result(STATUS_EXTERNAL,
                               f'Call on module object {name}',
                               method='module_binding', dispatch='external',
                               evidence=evidence, diagnostics=['module_object_call'])
            if best.kind in ('local', 'class', 'nested') and best.symbol_id:
                if best.symbol_id in ids:
                    return _result(STATUS_STATIC_RESOLVED,
                                   f'{best.kind} binding {name} -> {best.symbol_id}',
                                   targets=[best.symbol_id], method='scope_binding',
                                   evidence=evidence)
            if best.kind in ('external', 'unresolved_import'):
                status = STATUS_EXTERNAL if best.kind == 'external' else STATUS_UNRESOLVED
                return _result(status,
                               f'Import of {name} from "{best.module}" is {best.kind}',
                               method='import_binding',
                               dispatch='external' if status == STATUS_EXTERNAL else 'unknown',
                               evidence=evidence,
                               diagnostics=[best.kind])
            if best.kind == 'star':
                return self._resolve_star(name, file_ctx, graph_ctx, evidence)

        # 3. builtins
        if name in BUILTIN_NAMES:
            return _result(STATUS_EXTERNAL, f'Builtin function {name}',
                           method='builtin', dispatch='external', evidence=evidence,
                           diagnostics=['builtin'])

        # 4. star imports -> ambiguous across repo candidates
        star = [b for b in table.get_all_bindings('*') if b.kind == 'star']
        if star:
            return self._resolve_star(name, file_ctx, graph_ctx, evidence)

        # 5. no binding: name-match candidates across the repo are *ambiguous*
        #    evidence, never a confirmed edge.
        matches = [n['id'] for n in graph_ctx.get('nodes', [])
                   if n.get('name') == name and n.get('kind') in ('function', 'method', 'object')
                   and n.get('id') in ids]
        # prefer top-level (unqualified) functions
        top = [m for m in matches
               if '.' not in (graph_ctx.get('symbol_by_id', {}).get(m, {}).get('qualname') or '')]
        if top:
            matches = top
        if len(matches) == 1:
            return _result(STATUS_AMBIGUOUS,
                           f'Unbound name {name} matches {matches[0]} but no import/local binding proves it',
                           candidates=matches, method='name_match', evidence=evidence,
                           diagnostics=['unbound_name'])
        if len(matches) > 1:
            return _result(STATUS_AMBIGUOUS,
                           f'Unbound name {name} has {len(matches)} candidates',
                           candidates=matches[:50], method='name_match', evidence=evidence,
                           diagnostics=['unbound_name'])
        return _result(STATUS_UNRESOLVED, f'No target found for {name}',
                       method='none', evidence=evidence, diagnostics=['no_match'])

    def _resolve_star(self, name, file_ctx, graph_ctx, evidence):
        matches = [n['id'] for n in graph_ctx.get('nodes', [])
                   if n.get('name') == name and n.get('kind') in ('function', 'method', 'object')
                   and n.get('id') in self._node_ids(graph_ctx)]
        top = [m for m in matches
               if '.' not in (graph_ctx.get('symbol_by_id', {}).get(m, {}).get('qualname') or '')]
        if top:
            matches = top
        if matches:
            return _result(STATUS_AMBIGUOUS,
                           f'Star import: {name} has {len(matches)} candidates',
                           candidates=matches[:50], method='star_import', evidence=evidence,
                           diagnostics=['star_import'])
        return _result(STATUS_UNRESOLVED, f'Star import: no candidate for {name}',
                       method='star_import', evidence=evidence, diagnostics=['star_import'])
