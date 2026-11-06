"""JavaScript/TypeScript call resolver (structural, no type checker).

Resolves what can be proven from imports, same-file declarations, class
methods and module members. Anything requiring real type information
(typed receivers, interface dispatch, re-export chains it cannot prove)
is reported as unresolved/ambiguous — never fabricated.
"""
import os
import re
from typing import Dict, List, Optional, Tuple

from .base import (
    ResolverAdapter, FileContext, ResolutionResult,
    STATUS_STATIC_RESOLVED, STATUS_AMBIGUOUS, STATUS_UNRESOLVED,
    STATUS_EXTERNAL, STATUS_DYNAMIC,
)
from .bindings import BindingTable, Binding
from ..parsers.python_ast import BUILTIN_NAMES

_JS_EXTS = ('.ts', '.tsx', '.js', '.jsx', '.mts', '.cts')
_DYNAMIC_NAMES = {'import', 'eval', 'require.resolve'}


def _norm_rel(base_dir: str, spec: str) -> str:
    """Join a relative import specifier onto the importer's directory."""
    parts = []
    for p in (base_dir + '/' + spec).split('/'):
        if p in ('', '.'):
            continue
        if p == '..':
            if parts:
                parts.pop()
            continue
        parts.append(p)
    return '/'.join(parts)


def _resolve_js_module(spec: str, from_file: str, graph_ctx: Dict) -> Optional[str]:
    """Resolve a JS/TS import specifier to a repo-relative file, or None."""
    if not spec or not spec.startswith('.'):
        return None  # bare specifier -> node_modules / external
    base = os.path.dirname(from_file)
    stem = _norm_rel(base, spec)
    # strip a .js/.jsx extension so `./x.js` can resolve to `./x.ts`
    for ext in ('.js', '.jsx', '.mjs', '.cjs'):
        if stem.endswith(ext):
            stem = stem[:-len(ext)]
            break
    files = set(graph_ctx.get('file_symbols', {}).keys())
    for cand in [stem + e for e in _JS_EXTS] + [stem]:
        if cand in files:
            return cand
    for e in _JS_EXTS:
        cand = stem + '/index' + e
        if cand in files:
            return cand
    return None


def _result(status, reason, targets=None, candidates=None, method='',
            dispatch='static', diagnostics=None):
    from .base import CONFIDENCE
    return ResolutionResult(
        status=status, targets=targets or [], candidates=candidates or [],
        reason=reason, confidence=CONFIDENCE.get(status),
        resolution_method=method, dispatch_kind=dispatch,
        diagnostics=diagnostics or [],
    )


class JavaScriptResolver(ResolverAdapter):
    """Structural resolver for javascript and typescript."""
    language = 'javascript'

    def __init__(self):
        self._tables: Dict[str, Tuple[FileContext, BindingTable]] = {}

    # ------------------------------------------------------------------
    def build_context(self, file_path: str, text: str, graph_nodes: List[Dict],
                      analysis: Optional[Dict] = None) -> FileContext:
        from ..parsers.tree_sitter_parser import extract_imports_with_tree_sitter
        imports = (analysis or {}).get('imports') or extract_imports_with_tree_sitter(file_path, text)
        symbols = (analysis or {}).get('symbols', [])
        classes = {}
        functions = {}
        for sym in symbols:
            entry = {'start': sym.get('start'), 'end': sym.get('end'),
                     'name': sym.get('name'), 'qualname': sym.get('qualname'),
                     'kind': sym.get('kind'), 'class_qualname': sym.get('class_qualname', '')}
            if sym.get('kind') == 'object':
                classes[sym.get('qualname', '')] = entry
            else:
                functions[sym.get('qualname', '')] = entry
        return FileContext(file_path=file_path, imports=imports, classes=classes,
                           functions=functions, analysis=analysis or {},
                           language='javascript')

    # ------------------------------------------------------------------
    def _binding_table(self, file_ctx: FileContext, graph_ctx: Dict) -> BindingTable:
        key = file_ctx.file_path
        if key in self._tables:
            return self._tables[key][1]
        table = BindingTable(file_ctx.file_path)
        analysis = file_ctx.analysis or {}
        symbols = analysis.get('symbols', [])

        def sid(sym):
            return sym.get('id') or f"{file_ctx.file_path}::{sym.get('qualname', sym.get('name',''))}"

        id_to_parent = {}
        for sym in symbols:
            s = sid(sym)
            table.add_scope(s)
            pq = sym.get('parent_qualname') or ''
            id_to_parent[s] = f"{file_ctx.file_path}::{pq}" if pq else ''
        for s, p in id_to_parent.items():
            if p:
                table.scope_parent[s] = p

        # imports
        for imp in file_ctx.imports:
            module = imp.get('module') or ''
            name = imp.get('name')
            alias = imp.get('alias')
            kind = imp.get('kind', 'import')
            line = imp.get('line', 0)
            if not module:
                continue
            target = _resolve_js_module(module, file_ctx.file_path, graph_ctx)
            if kind == 'require':
                bound = alias or module.split('/')[-1].split('.')[0]
                table.add_binding(Binding(name=bound, symbol_id='', kind='module',
                                          scope_id='', start_line=line, module=module,
                                          resolved_file=target or ''))
                continue
            if name is None or name == 'default':
                # default or namespace import -> module-ish binding; member
                # access is resolved at the use site against the target file
                bound = alias or module.split('/')[-1].split('.')[0]
                table.add_binding(Binding(name=bound, symbol_id='', kind='module',
                                          scope_id='', start_line=line, module=module,
                                          resolved_file=target or '',
                                          imported_name='*' if (name is None and alias) else 'default'))
                continue
            # named import {a as b}
            bound = alias or name
            target_sid = None
            if target:
                target_sid = self._top_level(graph_ctx, target, name)
            if target_sid:
                table.add_binding(Binding(name=bound, symbol_id=target_sid,
                                          kind='alias' if alias else 'import',
                                          scope_id='', start_line=line, module=module,
                                          imported_name=name, resolved_file=target or ''))
            else:
                table.add_binding(Binding(name=bound, symbol_id='',
                                          kind='external' if target is None else 'unresolved_import',
                                          scope_id='', start_line=line, module=module,
                                          imported_name=name, resolved_file=target or ''))

        # top-level and nested function/class bindings
        for sym in symbols:
            s = sid(sym)
            pq = sym.get('parent_qualname') or ''
            scope = f"{file_ctx.file_path}::{pq}" if pq else ''
            k = 'class' if sym.get('kind') == 'object' else ('nested' if pq else 'local')
            table.add_binding(Binding(name=sym.get('name', ''), symbol_id=s,
                                      kind=k, scope_id=scope, start_line=sym.get('start', 0)))
        # parameters
        for sym in symbols:
            if sym.get('kind') in ('function', 'method'):
                s = sid(sym)
                for p in sym.get('parameters') or []:
                    table.add_binding(Binding(name=p, symbol_id='', kind='param',
                                              scope_id=s, start_line=sym.get('start', 0)))

        self._tables[key] = (file_ctx, table)
        return table

    # ------------------------------------------------------------------
    @staticmethod
    def _top_level(graph_ctx: Dict, rel: str, name: str) -> Optional[str]:
        for sym in graph_ctx.get('file_symbols', {}).get(rel, []):
            if sym.get('name') == name and not sym.get('parent_qualname'):
                sid = sym.get('id') or f'{rel}::{sym.get("qualname", name)}'
                if sid in graph_ctx.get('node_ids', set()):
                    return sid
        return None

    def _caller_symbol(self, file_ctx, call):
        cid = call.get('caller_id')
        for sym in (file_ctx.analysis or {}).get('symbols', []):
            if (sym.get('id') or f"{file_ctx.file_path}::{sym.get('qualname','')}") == cid:
                return sym
        return None

    # ------------------------------------------------------------------
    def resolve(self, call: Dict, file_ctx: FileContext, graph_ctx: Dict) -> ResolutionResult:
        name = call.get('name') or ''
        receiver = call.get('receiver') or ''
        receiver_root = call.get('receiver_root') or ''
        call_type = call.get('call_type') or 'direct'
        line = call.get('line', 0)

        if not name:
            return _result(STATUS_UNRESOLVED, 'Empty callee name', method='none')
        if call_type == 'dynamic' or name in ('import', 'eval'):
            return _result(STATUS_DYNAMIC, 'Dynamic invocation cannot be resolved statically',
                           method='dynamic_detect', dispatch='dynamic',
                           diagnostics=['dynamic_construct'])

        table = self._binding_table(file_ctx, graph_ctx)
        caller = self._caller_symbol(file_ctx, call)
        scope_id = call.get('caller_id') or ''
        class_qual = (caller or {}).get('class_qualname', '')
        node_ids = graph_ctx.get('node_ids', set())

        # ---- this.method() / self.method() ---------------------------------
        if receiver_root in ('this', 'self') and receiver in ('this', 'self'):
            if class_qual:
                sid = f"{file_ctx.file_path}::{class_qual}.{name}"
                if sid in node_ids:
                    return _result(STATUS_STATIC_RESOLVED, f'this.{name} -> {sid}',
                                   targets=[sid], method='this_method', dispatch='virtual')
            return _result(STATUS_UNRESOLVED,
                           f'No method {name} on enclosing class', method='this_method')

        # ---- module.member() ----------------------------------------------
        if receiver:
            mod_hit = self._resolve_module_member(call, file_ctx, graph_ctx, table)
            if mod_hit is not None:
                return mod_hit
            # receiver chains like users.repo.delete: resolve root binding to a
            # file, then look for a matching qualified symbol
            chain_hit = self._resolve_receiver_chain(call, file_ctx, graph_ctx, table)
            if chain_hit is not None:
                return chain_hit
            return _result(STATUS_UNRESOLVED,
                           f'Cannot determine type of receiver "{receiver}"',
                           method='receiver_type', diagnostics=['unknown_receiver_type'])

        # ---- direct call ----------------------------------------------------
        return self._resolve_direct(name, file_ctx, graph_ctx, table, scope_id, line, caller)

    # ------------------------------------------------------------------
    def _resolve_module_member(self, call, file_ctx, graph_ctx, table):
        receiver = call.get('receiver') or ''
        name = call.get('name') or ''
        for dotted in {receiver, call.get('receiver_root') or ''} - {''}:
            module = table.resolve_module_name(dotted)
            target = None
            if module:
                target = _resolve_js_module(module, file_ctx.file_path, graph_ctx)
                if target is None:
                    # module binding recorded resolved_file at build time
                    for b in table.get_all_bindings(dotted):
                        if b.resolved_file:
                            target = b.resolved_file
                            break
            else:
                target = _resolve_js_module(dotted, file_ctx.file_path, graph_ctx)
            if target is None:
                continue
            sid = self._top_level(graph_ctx, target, name)
            if sid:
                return _result(STATUS_STATIC_RESOLVED, f'module.{name} -> {sid}',
                               targets=[sid], method='module_import')
            # member may be a class method or nested export: unique name match in file
            cands = [s.get('id') for s in graph_ctx.get('file_symbols', {}).get(target, [])
                     if s.get('name') == name and s.get('id') in graph_ctx.get('node_ids', set())]
            if len(cands) == 1:
                return _result(STATUS_STATIC_RESOLVED, f'module member {name} -> {cands[0]}',
                               targets=cands, method='module_import')
            if len(cands) > 1:
                return _result(STATUS_AMBIGUOUS, f'{len(cands)} candidates for {name}',
                               candidates=cands, method='module_import')
            return _result(STATUS_UNRESOLVED, f'No symbol {name} in {target}',
                           method='module_import')
        return None

    def _resolve_receiver_chain(self, call, file_ctx, graph_ctx, table):
        """obj.a.b() where obj is an imported binding: resolve file then member."""
        receiver = call.get('receiver') or ''
        name = call.get('name') or ''
        parts = receiver.split('.')
        if len(parts) < 2:
            return None
        root = parts[0]
        bindings = table.resolve_name(root, scope_id=call.get('caller_id') or '',
                                      line=call.get('line', 0))
        if not bindings or not bindings[0].resolved_file:
            return None
        target = bindings[0].resolved_file
        # build candidate qualified names: users.repo.delete -> repo.delete,
        # also try just the final attr against file symbols
        tail = '.'.join(parts[1:])
        for sym in graph_ctx.get('file_symbols', {}).get(target, []):
            q = sym.get('qualname') or ''
            if q == tail or q.endswith('.' + tail) or q.split('.')[-1] == name and tail == name:
                sid = sym.get('id')
                if sid in graph_ctx.get('node_ids', set()):
                    return _result(STATUS_STATIC_RESOLVED,
                                   f'receiver chain {receiver}.{name} -> {sid}',
                                   targets=[sid], method='receiver_chain')
        return _result(STATUS_UNRESOLVED,
                       f'No symbol for {receiver}.{name} in {target}',
                       method='receiver_chain', diagnostics=['member_not_found'])

    def _resolve_direct(self, name, file_ctx, graph_ctx, table, scope_id, line, caller):
        node_ids = graph_ctx.get('node_ids', set())
        analysis = file_ctx.analysis or {}
        symbols = analysis.get('symbols', [])
        caller_qual = (caller or {}).get('qualname', '')

        # recursive / nested local
        if caller is not None:
            own = caller.get('id')
            if name == caller.get('name') and own in node_ids:
                return _result(STATUS_STATIC_RESOLVED, 'Recursive self-call',
                               targets=[own], method='local_scope')
            for sym in symbols:
                if (sym.get('parent_qualname') == caller_qual and sym.get('name') == name):
                    sid = sym.get('id')
                    if sid in node_ids:
                        return _result(STATUS_STATIC_RESOLVED, 'Nested/local function',
                                       targets=[sid], method='local_scope')

        bindings = table.resolve_name(name, scope_id=scope_id, line=line)
        best = bindings[0] if bindings else None
        if best:
            if best.kind == 'param':
                return _result(STATUS_DYNAMIC, f'Parameter "{name}" is a callable value',
                               method='param_binding', dispatch='dynamic',
                               diagnostics=['callable_param'])
            if best.kind in ('import', 'alias') and best.symbol_id:
                if best.symbol_id in node_ids:
                    return _result(STATUS_STATIC_RESOLVED,
                                   f'Import binding {name} -> {best.symbol_id}',
                                   targets=[best.symbol_id], method='import_binding')
                return _result(STATUS_UNRESOLVED, 'Import target outside indexed symbols',
                               method='import_binding')
            if best.kind == 'module':
                return _result(STATUS_EXTERNAL, f'Call on module object {name}',
                               method='module_binding', dispatch='external',
                               diagnostics=['module_object_call'])
            if best.kind in ('local', 'class', 'nested') and best.symbol_id:
                if best.symbol_id in node_ids:
                    return _result(STATUS_STATIC_RESOLVED,
                                   f'{best.kind} binding {name} -> {best.symbol_id}',
                                   targets=[best.symbol_id], method='scope_binding')
            if best.kind in ('external', 'unresolved_import'):
                status = STATUS_EXTERNAL if best.kind == 'external' else STATUS_UNRESOLVED
                return _result(status, f'Import of {name} from "{best.module}" is {best.kind}',
                               method='import_binding',
                               dispatch='external' if status == STATUS_EXTERNAL else 'unknown',
                               diagnostics=[best.kind])

        if name in BUILTIN_NAMES or name in ('require', 'module', 'exports', 'process', 'console'):
            return _result(STATUS_EXTERNAL, f'Builtin/global {name}', method='builtin',
                           dispatch='external', diagnostics=['builtin'])

        # unique top-level match in same file -> still ambiguous without binding?
        # For JS, same-file function declarations ARE bindings (added above), so
        # reaching here means truly unbound: report name-match candidates.
        matches = [s.get('id') for s in symbols
                   if s.get('name') == name and s.get('id') in node_ids]
        top = [m for m in matches
               if '.' not in ((graph_ctx.get('symbol_by_id', {}).get(m) or {}).get('qualname') or '')]
        if top:
            matches = top
        if len(matches) == 1:
            return _result(STATUS_AMBIGUOUS,
                           f'Unbound name {name} matches {matches[0]} without a binding',
                           candidates=matches, method='name_match',
                           diagnostics=['unbound_name'])
        if len(matches) > 1:
            return _result(STATUS_AMBIGUOUS, f'Unbound name {name}: {len(matches)} candidates',
                           candidates=matches[:50], method='name_match',
                           diagnostics=['unbound_name'])
        return _result(STATUS_UNRESOLVED, f'No target found for {name}', method='none',
                       diagnostics=['no_match'])
