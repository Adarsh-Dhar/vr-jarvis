"""Binding table for tracking import and local name bindings."""
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field


@dataclass
class Binding:
    """A binding from a local name to a symbol."""
    name: str  # Local name (e.g., 'validate', 'auth_validate')
    symbol_id: str  # Resolved symbol ID (e.g., 'authentication.py::validate')
    kind: str  # 'local', 'import', 'alias', 'module'
    line: int  # Line where binding occurs


class BindingTable:
    """Tracks name-to-symbol bindings for a file."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.bindings: Dict[str, List[Binding]] = {}  # name -> bindings
        self.module_bindings: Dict[str, str] = {}  # module name -> symbol ID prefix
        self.class_bindings: Dict[str, str] = {}  # class name -> symbol ID
        self.scopes: List[Set[str]] = [set()]  # Stack of scopes for local variables
    
    def add_binding(self, binding: Binding):
        """Add a binding to the current scope."""
        name = binding.name
        if name not in self.bindings:
            self.bindings[name] = []
        self.bindings[name].append(binding)
        self.scopes[-1].add(name)
    
    def add_module_binding(self, module_name: str, symbol_prefix: str):
        """Add a module-level import binding."""
        self.module_bindings[module_name] = symbol_prefix
    
    def add_class_binding(self, class_name: str, symbol_id: str):
        """Add a class definition binding."""
        self.class_bindings[class_name] = symbol_id
    
    def push_scope(self):
        """Push a new scope (e.g., entering a function)."""
        self.scopes.append(set())
    
    def pop_scope(self):
        """Pop the current scope."""
        if len(self.scopes) > 1:
            self.scopes.pop()
    
    def resolve_name(self, name: str) -> Optional[Binding]:
        """Resolve a name to its binding, checking from innermost scope outward."""
        if name in self.bindings:
            # Return the most recent binding
            return self.bindings[name][-1]
        return None
    
    def resolve_module_name(self, module_name: str) -> Optional[str]:
        """Resolve a module name to its symbol prefix."""
        return self.module_bindings.get(module_name)
    
    def resolve_class_name(self, class_name: str) -> Optional[str]:
        """Resolve a class name to its symbol ID."""
        return self.class_bindings.get(class_name)
    
    def get_all_bindings(self, name: str) -> List[Binding]:
        """Get all bindings for a name (for ambiguous cases)."""
        return self.bindings.get(name, [])
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for debugging."""
        return {
            'file_path': self.file_path,
            'bindings': {k: [{'name': b.name, 'symbol_id': b.symbol_id, 'kind': b.kind, 'line': b.line} 
                           for b in v] for k, v in self.bindings.items()},
            'module_bindings': self.module_bindings,
            'class_bindings': self.class_bindings
        }
