"""Python AST analysis: symbols, call sites, imports, classes and type facts.

This module is the single place where Python source is understood. It uses the
``ast`` module (not line ranges) so every symbol and call site carries its real
lexical owner, qualified name and source span.

``analyze_python_source`` returns a dict with:

- ``symbols``: function/method/class declarations with qualified names.
- ``call_sites``: every call expression with its owning function (or ``None``
  for module-level code) and a stable ``callsite_id``.
- ``imports``: structured import statements including relative-import level.
- ``classes``: class metadata (bases, methods, span).
- ``scopes``: per-function type facts (parameter annotations, local
  constructor assignments, ``self.<attr>`` constructor assignments).
"""
import ast
from typing import Dict, List, Optional, Tuple

# Names that are dynamic or otherwise not statically resolvable call targets.
DYNAMIC_CALL_NAMES = {
    'getattr', 'setattr', 'delattr', 'hasattr', 'eval', 'exec', 'compile',
    '__import__', 'globals', 'locals', 'vars', 'super',
}

BUILTIN_NAMES = {
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes', 'callable',
    'chr', 'classmethod', 'compile', 'complex', 'delattr', 'dict', 'dir', 'divmod',
    'enumerate', 'eval', 'exec', 'filter', 'float', 'format', 'frozenset', 'getattr',
    'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance',
    'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max', 'memoryview', 'min',
    'next', 'object', 'oct', 'open', 'ord', 'pow', 'print', 'property', 'range',
    'repr', 'reversed', 'round', 'set', 'setattr', 'slice', 'sorted', 'staticmethod',
    'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip', '__import__',
}


def _unparse(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ''


def _col(text_lines: List[str], lineno: int, byte_col: int) -> int:
    """Convert an ast byte column to a character column."""
    if lineno - 1 >= len(text_lines):
        return byte_col
    line = text_lines[lineno - 1]
    raw = line.encode('utf-8')
    if byte_col >= len(raw):
        return len(line)
    return len(raw[:byte_col].decode('utf-8', errors='replace'))


def _signature(node: ast.FunctionDef) -> str:
    """Build a readable signature like ``(self, amount: float)``."""
    args = node.args
    parts = []
    all_args = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(all_args) - len(args.defaults)) + list(args.defaults)
    for a, d in zip(all_args, defaults):
        s = a.arg
        if a.annotation is not None:
            s += ': ' + _unparse(a.annotation)
        if d is not None:
            s += ' = ' + _unparse(d)
        parts.append(s)
    if args.vararg is not None:
        parts.append('*' + args.vararg.arg)
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        s = a.arg
        if a.annotation is not None:
            s += ': ' + _unparse(a.annotation)
        if d is not None:
            s += ' = ' + _unparse(d)
        parts.append(s)
    if args.kwarg is not None:
        parts.append('**' + args.kwarg.arg)
    return '(' + ', '.join(parts) + ')'


def _parameters(node: ast.FunctionDef) -> List[str]:
    args = node.args
    names = [a.arg for a in list(args.posonlyargs) + list(args.args)]
    if args.vararg:
        names.append(args.vararg.arg)
    names += [a.arg for a in args.kwonlyargs]
    if args.kwarg:
        names.append(args.kwarg.arg)
    return names


def _param_annotations(node: ast.FunctionDef) -> Dict[str, Optional[str]]:
    out = {}
    args = node.args
    for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
        out[a.arg] = _unparse(a.annotation) if a.annotation is not None else None
    if args.vararg is not None:
        out[args.vararg.arg] = _unparse(args.vararg.annotation) if args.vararg.annotation else None
    if args.kwarg is not None:
        out[args.kwarg.arg] = _unparse(args.kwarg.annotation) if args.kwarg.annotation else None
    return out


def _call_type_name(node: ast.expr) -> Optional[str]:
    """Return the called class/function name for ``X(...)`` style calls."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        # module.Class(...) -> 'Class'
        return node.attr
    return None


def _assigned_type_names(value: ast.expr) -> List[str]:
    """Collect constructor type names from an assignment RHS.

    Handles ``X()``, ``X() if c else Y()``, ``X | Y`` annotations are handled
    by the caller via AnnAssign.
    """
    names = []
    if isinstance(value, ast.Call):
        t = _call_type_name(value.func)
        if t:
            names.append(t)
    elif isinstance(value, ast.IfExp):
        names += _assigned_type_names(value.body)
        names += _assigned_type_names(value.orelse)
    elif isinstance(value, ast.BoolOp):
        for v in value.values:
            names += _assigned_type_names(v)
    return names


def _annassign_type_names(annotation: ast.expr) -> List[str]:
    """Collect type names from an annotation like ``Payment``, ``A | B``, ``Union[A, B]``."""
    if annotation is None:
        return []
    if isinstance(annotation, ast.Name):
        return [annotation.id]
    if isinstance(annotation, ast.Attribute):
        return [annotation.attr]
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _annassign_type_names(annotation.left) + _annassign_type_names(annotation.right)
    if isinstance(annotation, ast.Subscript):
        # Union[A, B], Optional[A], list[A] -> slice may hold names
        sl = annotation.slice
        elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
        out = []
        for e in elts:
            out += _annassign_type_names(e)
        if not out:
            out = _annassign_type_names(sl)
        return out
    if isinstance(annotation, ast.Constant) and annotation.value is Ellipsis:
        return []
    return []


def analyze_python_source(text: str, file_path: str = '') -> dict:
    """Analyze Python source once and return symbols, call sites and facts."""
    result = {
        'symbols': [],
        'call_sites': [],
        'imports': [],
        'classes': {},
        'scopes': {},
        'module_name': '',
        'ok': True,
        'error': None,
    }
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError) as exc:
        result['ok'] = False
        result['error'] = str(exc)
        return result

    text_lines = text.splitlines()

    # module dotted name from repo-relative path, e.g. 'pkg/mod.py' -> 'pkg.mod'
    rel = file_path.replace('\\', '/')
    if rel.endswith('.py'):
        mod = rel[:-3].replace('/', '.')
        if mod.endswith('.__init__'):
            mod = mod[:-len('.__init__')]
        result['module_name'] = mod

    # scope stack entries: ('class'|'function', qualname, node)
    scope_stack: List[Tuple[str, str, ast.AST]] = []

    def qualname_of(name: str) -> str:
        prefix = '.'.join(q for _, q, _ in scope_stack)
        return f'{prefix}.{name}' if prefix else name

    def current_function_qualname() -> Optional[str]:
        for kind, q, _ in reversed(scope_stack):
            if kind == 'function':
                return q
        return None

    def enclosing_class_qualnames() -> List[str]:
        return [q for kind, q, _ in scope_stack if kind == 'class']

    symbols_by_qualname: Dict[str, dict] = {}
    scope_facts: Dict[str, dict] = {}

    class SymbolCollector(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef):
            qual = qualname_of(node.name)
            bases = [_unparse(b) for b in node.bases]
            decorators = [_unparse(d) for d in node.decorator_list]
            sym = {
                'name': node.name,
                'qualname': qual,
                'kind': 'object',
                'class_name': enclosing_class_qualnames()[-1].split('.')[-1] if enclosing_class_qualnames() else '',
                'class_qualname': '.'.join(enclosing_class_qualnames()),
                'parent_qualname': '.'.join(q for _, q, _ in scope_stack),
                'file': file_path,
                'language': 'python',
                'start': node.lineno,
                'end': node.end_lineno or node.lineno,
                'signature': '',
                'parameters': [],
                'decorators': decorators,
                'bases': bases,
                'id': f'{file_path}::{qual}',
            }
            result['symbols'].append(sym)
            symbols_by_qualname[qual] = sym
            result['classes'][qual] = {
                'name': node.name,
                'qualname': qual,
                'bases': bases,
                'start': node.lineno,
                'end': node.end_lineno or node.lineno,
                'methods': {},
            }
            scope_stack.append(('class', qual, node))
            self.generic_visit(node)
            scope_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self._function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            self._function(node)

        def _function(self, node):
            qual = qualname_of(node.name)
            classes = enclosing_class_qualnames()
            direct_class = classes[-1] if classes else ''
            # A function directly inside a class body is a method; anything else
            # nested under a function is a nested function.
            parent_kinds = [k for k, _, _ in scope_stack]
            kind = 'method' if (direct_class and parent_kinds and parent_kinds[-1] == 'class') else 'function'
            sym = {
                'name': node.name,
                'qualname': qual,
                'kind': kind,
                'class_name': direct_class.split('.')[-1] if direct_class else '',
                'class_qualname': direct_class,
                'parent_qualname': '.'.join(q for _, q, _ in scope_stack),
                'file': file_path,
                'language': 'python',
                'start': node.lineno,
                'end': node.end_lineno or node.lineno,
                'signature': _signature(node),
                'parameters': _parameters(node),
                'decorators': [_unparse(d) for d in node.decorator_list],
                'return_annotation': _unparse(node.returns) if node.returns is not None else None,
                'id': f'{file_path}::{qual}',
            }
            result['symbols'].append(sym)
            symbols_by_qualname[qual] = sym
            # register as a method of the innermost class
            if direct_class and direct_class in result['classes']:
                result['classes'][direct_class]['methods'][node.name] = qual

            scope_stack.append(('function', qual, node))
            # Decorator expressions are real calls (e.g. @app.route('/x')).
            for dec in node.decorator_list:
                self._visit_expr(dec, qual)
            facts = {
                'param_types': {k: v for k, v in _param_annotations(node).items() if v},
                'local_types': {},      # var -> [type names]
                'self_attr_types': {},  # attr -> [type names] (only meaningful in methods)
                'nested_functions': {}, # name -> qualname
                'symbol_id': f'{file_path}::{qual}',
            }
            scope_facts[qual] = facts

            # Walk the body manually so we can collect local type facts and
            # nested function definitions while still visiting calls.
            for stmt in node.body:
                self._visit_stmt(stmt, facts, qual)
            scope_stack.pop()

        # -- statement-level fact collection ---------------------------------
        def _visit_stmt(self, stmt, facts, fn_qual):
            # Definition statements own their own subtrees.
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._function(stmt)
                return
            if isinstance(stmt, ast.ClassDef):
                self.visit_ClassDef(stmt)
                return
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    result['imports'].append({
                        'module': alias.name, 'name': None, 'alias': alias.asname,
                        'kind': 'import', 'line': stmt.lineno, 'level': 0,
                    })
                return
            if isinstance(stmt, ast.ImportFrom):
                for alias in stmt.names:
                    result['imports'].append({
                        'module': stmt.module or '', 'name': alias.name,
                        'alias': alias.asname, 'kind': 'from',
                        'line': stmt.lineno, 'level': stmt.level or 0,
                    })
                return

            # Type facts from assignments (calls inside the RHS are still visited
            # by the generic child walk below).
            if isinstance(stmt, ast.Assign):
                names = _assigned_type_names(stmt.value)
                if names:
                    for t in stmt.targets:
                        for nm in self._target_names(t):
                            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == 'self':
                                facts['self_attr_types'].setdefault(t.attr, [])
                                for n in names:
                                    if n not in facts['self_attr_types'][t.attr]:
                                        facts['self_attr_types'][t.attr].append(n)
                            elif isinstance(t, ast.Name):
                                facts['local_types'].setdefault(t.id, [])
                                for n in names:
                                    if n not in facts['local_types'][t.id]:
                                        facts['local_types'][t.id].append(n)
            elif isinstance(stmt, ast.AnnAssign) and stmt.target is not None:
                type_names = _annassign_type_names(stmt.annotation)
                rhs_names = _assigned_type_names(stmt.value) if stmt.value is not None else []
                all_names = type_names + rhs_names
                tgt = stmt.target
                if all_names:
                    if isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) and tgt.value.id == 'self':
                        facts['self_attr_types'].setdefault(tgt.attr, [])
                        for n in all_names:
                            if n not in facts['self_attr_types'][tgt.attr]:
                                facts['self_attr_types'][tgt.attr].append(n)
                    elif isinstance(tgt, ast.Name):
                        facts['local_types'].setdefault(tgt.id, [])
                        for n in all_names:
                            if n not in facts['local_types'][tgt.id]:
                                facts['local_types'][tgt.id].append(n)

            for child in ast.iter_child_nodes(stmt):
                if isinstance(child, ast.stmt):
                    self._visit_stmt(child, facts, fn_qual)
                else:
                    self._visit_expr(child, fn_qual)

        def _target_names(self, t):
            if isinstance(t, ast.Name):
                return [t.id]
            if isinstance(t, (ast.Tuple, ast.List)):
                out = []
                for e in t.elts:
                    out += self._target_names(e)
                return out
            if isinstance(t, ast.Attribute):
                return [t.attr]
            return []

        # -- call collection ---------------------------------------------------
        def _visit_expr(self, node, fn_qual):
            """Walk expressions looking for ast.Call nodes (each visited once)."""
            if isinstance(node, ast.Call):
                self._record_call(node, fn_qual)
            for child in ast.iter_child_nodes(node):
                self._visit_expr(child, fn_qual)

        def _record_call(self, node: ast.Call, fn_qual):
            func = node.func
            # `super()` inside `super().m()` is part of the outer call expression,
            # not an independent call site.
            if isinstance(func, ast.Name) and func.id == 'super':
                return
            name = ''
            receiver = ''
            receiver_root = ''
            receiver_expr = ''
            call_type = 'direct'
            is_super = False

            if isinstance(func, ast.Name):
                name = func.id
                call_type = 'direct'
            elif isinstance(func, ast.Attribute):
                name = func.attr
                call_type = 'method'
                receiver_expr = _unparse(func.value) or ''
                receiver = receiver_expr
                # root of the receiver chain, e.g. 'self' in 'self.service.x'
                v = func.value
                while isinstance(v, ast.Attribute):
                    v = v.value
                if isinstance(v, ast.Name):
                    receiver_root = v.id
                elif isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == 'super':
                    receiver_root = 'super'
                    is_super = True
                    call_type = 'super'
                elif isinstance(v, ast.Call):
                    call_type = 'dynamic'
                else:
                    receiver_root = receiver_expr
            else:
                # func is itself a Call/Subscript/etc -> dynamic invocation
                name = _unparse(func)
                call_type = 'dynamic'
                receiver_expr = _unparse(func)

            args = node.args
            keywords = node.keywords
            arg_count = len(args) + len(keywords)

            caller_id = None
            if fn_qual:
                caller_id = f'{file_path}::{fn_qual}'
            col = _col(text_lines, node.lineno, node.col_offset)
            end_col = _col(text_lines, node.end_lineno or node.lineno,
                           node.end_col_offset or node.col_offset)
            callsite_id = f'{file_path}:{node.lineno}:{col}'

            result['call_sites'].append({
                'callsite_id': callsite_id,
                'caller_id': caller_id,
                'caller_qualname': fn_qual or '',
                'name': name,
                'receiver': receiver,
                'receiver_root': receiver_root,
                'receiver_expr': receiver_expr,
                'full_expression': _unparse(func) or name,
                'line': node.lineno,
                'column': col,
                'end_line': node.end_lineno or node.lineno,
                'end_column': end_col,
                'call_type': call_type,
                'arg_count': arg_count,
                'file': file_path,
                'language': 'python',
            })

    # Top-level: visit module body; imports/classes/functions handled by visitor,
    # module-level calls collected too.
    collector = SymbolCollector()

    # We need module-level imports and module-level calls as well.
    def visit_top(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    result['imports'].append({
                        'module': alias.name, 'name': None, 'alias': alias.asname,
                        'kind': 'import', 'line': child.lineno, 'level': 0,
                    })
            elif isinstance(child, ast.ImportFrom):
                for alias in child.names:
                    result['imports'].append({
                        'module': child.module or '', 'name': alias.name,
                        'alias': alias.asname, 'kind': 'from',
                        'line': child.lineno, 'level': child.level or 0,
                    })
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                collector.visit(child)
            else:
                # Module-level statements: defs nested in compound statements are
                # still registered; calls get caller_id=None (module scope).
                collector._visit_stmt(child, {}, None)

    visit_top(tree)

    # Assign scope facts to result
    result['scopes'] = scope_facts

    # legacy dotted ids for backward compatibility
    for sym in result['symbols']:
        mod = result['module_name']
        sym['legacy_id'] = f'{mod}.{sym["qualname"]}' if mod else sym['qualname']

    return result


# ---------------------------------------------------------------------------
# Backwards-compatible helpers (kept for callers that used the old API)
# ---------------------------------------------------------------------------

def extract_class_ranges(text: str) -> Dict[str, Tuple[int, int]]:
    """Extract class name to line range mapping."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    class_ranges = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)
    return class_ranges


def extract_parameter_annotations(text: str) -> Dict[str, List[Dict]]:
    """Extract parameter type annotations from functions."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    annotations = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = []
            for arg in node.args.args:
                annotation = _unparse(arg.annotation) if arg.annotation else None
                params.append({'name': arg.arg, 'annotation': annotation})
            if params:
                annotations[node.name] = params
    return annotations


def extract_type_assignments_in_init(text: str) -> Dict[str, str]:
    """Extract self.x = Class() assignments in __init__ methods."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    type_assignments = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                    for stmt in ast.walk(item):
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if (isinstance(target, ast.Attribute)
                                        and isinstance(target.value, ast.Name)
                                        and target.value.id == 'self'):
                                    if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name):
                                        type_assignments[f"{node.name}.{target.attr}"] = stmt.value.func.id
    return type_assignments


def extract_base_classes(text: str) -> Dict[str, List[str]]:
    """Extract base class expressions."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    base_classes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = [_unparse(b) or '<unknown>' for b in node.bases]
            if bases:
                base_classes[node.name] = bases
    return base_classes
