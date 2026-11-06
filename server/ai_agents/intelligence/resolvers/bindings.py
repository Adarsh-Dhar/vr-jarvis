"""Scope-aware binding table for tracking name -> symbol bindings.

Bindings are stored per lexical scope (``scope_id`` is a symbol id such as
``payments.py::CardPayment.process``; the empty string is module scope). A name
defined inside one function is never visible from another function: lookup walks
the scope-parent chain from the call site's scope outward to module scope and
stops at the first scope that binds the name.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class Binding:
    """A binding from a local name to a symbol or module."""
    name: str                    # local bound name (e.g. 'validate', 'auth_validate', 'payments')
    symbol_id: str = ''          # resolved symbol id, '' when target is a module/external
    kind: str = 'local'          # 'import' | 'alias' | 'module' | 'local' | 'param' | 'class' | 'nested'
    scope_id: str = ''           # owning scope symbol id ('' = module scope)
    start_line: int = 0          # first line where the binding is visible
    end_line: int = 0            # last line (0 = rest of scope)
    module: str = ''             # dotted module for import/module bindings
    imported_name: str = ''      # original name before aliasing
    resolved_file: str = ''      # repo-relative file the binding points into


class BindingTable:
    """Tracks name-to-symbol bindings for one file, organized by lexical scope."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        # scope_id -> {name: [Binding,...]}
        self._scopes: Dict[str, Dict[str, List[Binding]]] = {'': {}}
        # scope_id -> parent scope_id ('' parent = module scope)
        self.scope_parent: Dict[str, str] = {}
        # bound name -> dotted module path, for `import x [as y]` style bindings
        self.module_bindings: Dict[str, str] = {}
        # class name -> class symbol id (module-level classes)
        self.class_bindings: Dict[str, str] = {}

    # -- scope management -----------------------------------------------------
    def add_scope(self, scope_id: str, parent: str = ''):
        """Register a lexical scope and its parent (first registration wins)."""
        self._scopes.setdefault(scope_id, {})
        if scope_id not in self.scope_parent:
            self.scope_parent[scope_id] = parent if parent == '' or parent in self._scopes else ''

    def scope_chain(self, scope_id: str) -> List[str]:
        """Return scope ids from innermost to module scope ('' last)."""
        chain = []
        seen = set()
        cur = scope_id
        while cur and cur not in seen:
            seen.add(cur)
            chain.append(cur)
            cur = self.scope_parent.get(cur, '')
        chain.append('')
        return chain

    # -- binding management ---------------------------------------------------
    def add_binding(self, binding: Binding):
        scope = binding.scope_id or ''
        self._scopes.setdefault(scope, {})
        self._scopes[scope].setdefault(binding.name, []).append(binding)
        if binding.kind == 'module' and binding.module:
            self.module_bindings[binding.name] = binding.module
        if binding.kind == 'class' and binding.symbol_id:
            self.class_bindings[binding.name] = binding.symbol_id

    def add_module_binding(self, bound_name: str, module: str):
        self.module_bindings[bound_name] = module

    def add_class_binding(self, class_name: str, symbol_id: str):
        self.class_bindings[class_name] = symbol_id

    # -- lookup ----------------------------------------------------------------
    def _visible(self, binding: Binding, line: int, scope_id: str) -> bool:
        # Module-scope names resolve at call time in Python/JS: a def later in
        # the file is still visible to earlier calls, so line checks only apply
        # inside function-local scopes (redefinitions, imports in branches).
        if scope_id == '':
            return True
        if line and binding.start_line and binding.start_line > line:
            return False
        if binding.end_line and line and line > binding.end_line:
            return False
        return True

    def resolve_name(self, name: str, scope_id: str = '', line: int = 0) -> List[Binding]:
        """Return candidate bindings for ``name`` visible from ``scope_id``.

        Ordered innermost scope first; within a scope the LATEST binding before
        the call line wins (redefinitions shadow earlier ones). Once a scope
        binds the name, outer scopes are not consulted (shadowing).
        """
        for scope in self.scope_chain(scope_id):
            bindings = self._scopes.get(scope, {}).get(name, [])
            visible = [b for b in bindings if self._visible(b, line, scope)]
            if visible:
                # latest binding wins -> descending start_line, [0] is best
                visible.sort(key=lambda b: b.start_line, reverse=True)
                return visible
        return []

    def resolve_module_name(self, module_name: str) -> Optional[str]:
        """Resolve a module alias to its dotted module path."""
        return self.module_bindings.get(module_name)

    def resolve_class_name(self, class_name: str) -> Optional[str]:
        """Resolve a class name to its symbol ID."""
        return self.class_bindings.get(class_name)

    def get_all_bindings(self, name: str) -> List[Binding]:
        """Get every binding for a name across all scopes (ambiguity analysis)."""
        out = []
        for scope in self._scopes.values():
            out.extend(scope.get(name, []))
        return out

    def to_dict(self) -> Dict:
        return {
            'file_path': self.file_path,
            'scopes': {
                sid: {n: [b.__dict__ for b in bl] for n, bl in names.items()}
                for sid, names in self._scopes.items()
            },
            'module_bindings': self.module_bindings,
            'class_bindings': self.class_bindings,
        }
