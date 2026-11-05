"""Python-specific call resolver with binding table."""
from typing import Dict, List, Optional
from .base import ResolverAdapter, FileContext, ResolutionResult
from .bindings import BindingTable, Binding
from ..parsers.python_ast import extract_class_ranges, extract_parameter_annotations, extract_type_assignments_in_init, extract_base_classes


class PythonResolver(ResolverAdapter):
    """Python call resolver using binding tables and AST analysis."""
    
    def build_context(self, file_path: str, text: str, graph_nodes: List[Dict]) -> FileContext:
        """Build context for a Python file."""
        # Extract imports using tree-sitter
        from ..parsers.tree_sitter_parser import extract_imports_with_tree_sitter
        imports = extract_imports_with_tree_sitter(file_path, text)
        
        # Extract class information
        class_ranges = extract_class_ranges(text)
        base_classes = extract_base_classes(text)
        
        classes = {}
        for class_name, (start, end) in class_ranges.items():
            classes[class_name] = {
                'start': start,
                'end': end,
                'bases': base_classes.get(class_name, [])
            }
        
        # Extract function information
        import ast
        functions = {}
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualname = node.name
                    # Add class prefix if inside a class
                    for parent in ast.walk(tree):
                        if isinstance(parent, ast.ClassDef) and node in ast.walk(parent):
                            qualname = f"{parent.name}.{node.name}"
                            break
                    functions[qualname] = {
                        'start': node.lineno,
                        'end': node.end_lineno or node.lineno,
                        'name': node.name
                    }
        except SyntaxError:
            pass
        
        # Extract type assignments for polymorphic resolution
        type_assignments = extract_type_assignments_in_init(text)
        
        return FileContext(
            file_path=file_path,
            imports=imports,
            classes=classes,
            functions=functions,
            type_assignments=type_assignments
        )
    
    def resolve(self, call: Dict, file_ctx: FileContext, graph_ctx: Dict) -> ResolutionResult:
        """Resolve a Python call to its target(s)."""
        call_name = call.get('name', '')
        receiver = call.get('receiver', '')
        call_type = call.get('call_type', 'direct')
        line = call.get('line', 0)
        
        # Build binding table for this file
        binding_table = self._build_binding_table(file_ctx, graph_ctx)
        
        # Resolution order from the plan:
        # 1. Local scope and same file (prefer for direct calls without receiver)
        # 2. Explicit import binding including aliases
        # 3. module.func through a module binding
        # 4. self.m() and cls.m() through the class and its bases
        # 5. Receiver with a known type: polymorphic
        # 6. Several name matches: ambiguous
        # 7. Import points outside the repo: external
        
        nodes_by_name = self._index_nodes_by_name(graph_ctx.get('nodes', []))
        nodes_by_file = self._index_nodes_by_file(graph_ctx.get('nodes', []))
        
        # Step 1: Check local scope and same file (for direct calls, prefer same-file)
        if not receiver or receiver == '':
            same_file_candidates = nodes_by_file.get(file_ctx.file_path, [])
            same_file_matches = [n for n in same_file_candidates if n['name'] == call_name]
            
            if same_file_matches:
                if len(same_file_matches) == 1:
                    return ResolutionResult(
                        status='static_resolved',
                        targets=[same_file_matches[0]['id']],
                        candidates=[],
                        reason='Same-file match (direct call)'
                    )
                # Multiple in same file - try line range to disambiguate
                for match in same_file_matches:
                    if match.get('start', 0) <= line <= match.get('end', 999999):
                        return ResolutionResult(
                            status='static_resolved',
                            targets=[match['id']],
                            candidates=[],
                            reason='Same-file match by line range'
                        )
        
        # Step 2: Check explicit import bindings (prefer explicit over module-level)
        binding = binding_table.resolve_name(call_name)
        if binding:
            # Prefer explicit import/alias bindings over module-level bindings
            if binding.kind in ['import', 'alias']:
                symbol_id = binding.symbol_id
                if symbol_id in nodes_by_name or any(n['id'] == symbol_id for n in graph_ctx.get('nodes', [])):
                    return ResolutionResult(
                        status='static_resolved',
                        targets=[symbol_id],
                        candidates=[],
                        reason=f'Explicit import binding: {binding.kind}'
                    )
            elif binding.kind == 'module':
                # Module-level binding - check if there's also an explicit binding
                all_bindings = binding_table.get_all_bindings(call_name)
                explicit_bindings = [b for b in all_bindings if b.kind in ['import', 'alias']]
                if explicit_bindings:
                    # Use the explicit binding instead
                    symbol_id = explicit_bindings[-1].symbol_id
                    if symbol_id in nodes_by_name or any(n['id'] == symbol_id for n in graph_ctx.get('nodes', [])):
                        return ResolutionResult(
                            status='static_resolved',
                            targets=[symbol_id],
                            candidates=[],
                            reason=f'Explicit import binding: {explicit_bindings[-1].kind}'
                        )
                # Use module-level binding as fallback
                symbol_id = binding.symbol_id
                if symbol_id in nodes_by_name or any(n['id'] == symbol_id for n in graph_ctx.get('nodes', [])):
                    return ResolutionResult(
                        status='static_resolved',
                        targets=[symbol_id],
                        candidates=[],
                        reason=f'Module-level binding'
                    )
        
        # Step 3: Check module.func calls
        if receiver:
            # Check if receiver is a module
            module_prefix = binding_table.resolve_module_name(receiver)
            if module_prefix:
                # Try to find module_name.func
                target_id = f"{module_prefix}::{call_name}"
                if any(n['id'] == target_id for n in graph_ctx.get('nodes', [])):
                    return ResolutionResult(
                        status='static_resolved',
                        targets=[target_id],
                        candidates=[],
                        reason='Module-qualified call'
                    )
        
        # Step 4: Check self.m() and cls.m() calls
        if receiver in ['self', 'cls']:
            # Find the class containing this call (by line number)
            containing_class = self._find_containing_class(line, file_ctx)
            if containing_class:
                # Check for method in class
                method_id = f"{file_ctx.file_path}::{containing_class}.{call_name}"
                if any(n['id'] == method_id for n in graph_ctx.get('nodes', [])):
                    return ResolutionResult(
                        status='static_resolved',
                        targets=[method_id],
                        candidates=[],
                        reason=f'Self/cls method in class {containing_class}'
                    )
                # Check base classes (inheritance)
                for base in file_ctx.classes.get(containing_class, {}).get('bases', []):
                    # Resolve base class to actual file
                    base_class_id = self._resolve_class_name(base, graph_ctx)
                    if base_class_id:
                        base_method_id = f"{base_class_id}::{call_name}"
                        if any(n['id'] == base_method_id for n in graph_ctx.get('nodes', [])):
                            return ResolutionResult(
                                status='static_resolved',
                                targets=[base_method_id],
                                candidates=[],
                                reason=f'Inherited method from base class {base}'
                            )
        
        # Step 5: Check typed receiver (polymorphic)
        if receiver:
            # Try to resolve receiver type
            class_id = binding_table.resolve_class_name(receiver)
            if not class_id:
                # Check type_assignments from __init__
                type_key = f"{file_ctx.file_path}::{receiver}"
                if type_key in file_ctx.type_assignments:
                    class_id = file_ctx.type_assignments[type_key]
            
            if class_id:
                # Found a class binding - check for method
                method_id = f"{class_id}::{call_name}"
                candidates = []
                if any(n['id'] == method_id for n in graph_ctx.get('nodes', [])):
                    candidates.append(method_id)
                # Check subclasses (polymorphic)
                for node in graph_ctx.get('nodes', []):
                    if node.get('kind') == 'function' and node.get('name') == call_name:
                        if '::' in node['id']:
                            node_class = node['id'].split('::')[0]
                            if node_class != class_id:
                                candidates.append(node['id'])
                
                if candidates:
                    if len(candidates) == 1:
                        return ResolutionResult(
                            status='static_resolved',
                            targets=[candidates[0]],
                            candidates=[],
                            reason=f'Typed receiver {receiver} -> single candidate'
                        )
                    else:
                        return ResolutionResult(
                            status='polymorphic',
                            targets=[candidates[0]],  # Primary target
                            candidates=candidates,
                            reason=f'Polymorphic method call on {receiver} with {len(candidates)} candidates'
                        )
        
        # Step 6: Check for multiple matches (ambiguous)
        # But first check if there's an explicit binding that overrides this
        all_matches = nodes_by_name.get(call_name, [])
        if len(all_matches) > 1:
            # Check if there's an explicit binding that resolves this
            binding = binding_table.resolve_name(call_name)
            if binding and binding.kind in ['import', 'alias']:
                # Use the explicitly bound target
                if binding.symbol_id in [n['id'] for n in graph_ctx.get('nodes', [])]:
                    return ResolutionResult(
                        status='static_resolved',
                        targets=[binding.symbol_id],
                        candidates=[],
                        reason=f'Explicit binding overrides ambiguity: {binding.kind}'
                    )
            # No explicit binding - truly ambiguous
            return ResolutionResult(
                status='ambiguous',
                targets=[],
                candidates=[n['id'] for n in all_matches],
                reason=f'Ambiguous: {len(all_matches)} matches for {call_name}'
            )
        elif len(all_matches) == 1:
            return ResolutionResult(
                status='static_resolved',
                targets=[all_matches[0]['id']],
                candidates=[],
                reason='Unique match'
            )
        
        # Step 7: External or unresolved
        # Check if it might be an external library call
        for imp in file_ctx.imports:
            module = imp.get('module', '')
            if module and call_name in module:
                return ResolutionResult(
                    status='external',
                    targets=[],
                    candidates=[],
                    reason=f'External library: {module}'
                )
            # Check if call matches imported module name
            if module and call_name == module.rsplit('.', 1)[-1]:
                return ResolutionResult(
                    status='external',
                    targets=[],
                    candidates=[],
                    reason=f'External module: {module}'
                )
        
        return ResolutionResult(
            status='unresolved',
            targets=[],
            candidates=[],
            reason='No matches found'
        )
    
    def _build_binding_table(self, file_ctx: FileContext, graph_ctx: Dict) -> BindingTable:
        """Build a binding table for the file."""
        table = BindingTable(file_ctx.file_path)
        
        # Build a lookup of available symbols in each module
        module_symbols = {}
        for node in graph_ctx.get('nodes', []):
            if node.get('file'):
                # Extract module from file path
                # file is like 'payments.py' or 'auth/authentication.py'
                file_path = node['file']
                if '/' in file_path:
                    module = file_path.rsplit('/', 1)[0]
                else:
                    module = file_path.rsplit('.', 1)[0] if '.' in file_path else file_path
                if module not in module_symbols:
                    module_symbols[module] = set()
                module_symbols[module].add(node['name'])
        
        # First pass: add explicit from imports (highest priority)
        explicit_imports = set()
        for imp in file_ctx.imports:
            module = imp.get('module', '')
            name = imp.get('name')
            alias = imp.get('alias')
            kind = imp.get('kind', 'import')
            
            if kind == 'from' and name:
                # from X import Y [as Z]
                binding_name = alias or name
                # Convert module path to file path format
                # Need to map module name to actual file path
                # e.g., 'payments' -> 'payments.py' (file in graph nodes)
                module_file = None
                for node in graph_ctx.get('nodes', []):
                    if node.get('file'):
                        # Match module name to file name (without extension)
                        file_stem = node['file'].rsplit('.', 1)[0] if '.' in node['file'] else node['file']
                        if file_stem == module or node['file'] == module:
                            module_file = node['file']
                            break
                
                if module_file:
                    symbol_id = f"{module_file}::{name}"
                else:
                    # Fallback: use module as-is
                    symbol_id = f"{module.replace('.', '/')}::{name}" if '.' in module else f"{module}::{name}"
                table.add_binding(Binding(
                    name=binding_name,
                    symbol_id=symbol_id,
                    kind='alias' if alias else 'import',
                    line=imp.get('line', 0)
                ))
                explicit_imports.add(binding_name)
        
        # Second pass: add module imports (lower priority, don't override explicit)
        for imp in file_ctx.imports:
            module = imp.get('module', '')
            name = imp.get('name')
            alias = imp.get('alias')
            kind = imp.get('kind', 'import')
            
            if kind == 'import':
                # import X [as Y]
                binding_name = alias or module.split('.')[-1]
                table.add_module_binding(binding_name, module)
                
                # Also add potential bindings for all symbols in that module
                # But skip symbols that have explicit imports
                module_key = module.replace('.', '/')
                if module_key in module_symbols:
                    for symbol in module_symbols[module_key]:
                        if symbol not in explicit_imports:
                            table.add_binding(Binding(
                                name=symbol,
                                symbol_id=f"{module_key}::{symbol}",
                                kind='module',
                                line=imp.get('line', 0)
                            ))
        
        # Add class bindings
        for class_name, class_info in file_ctx.classes.items():
            symbol_id = f"{file_ctx.file_path}::{class_name}"
            table.add_class_binding(class_name, symbol_id)
        
        return table
    
    def _index_nodes_by_name(self, nodes: List[Dict]) -> Dict[str, List[Dict]]:
        """Index nodes by name for fast lookup."""
        index = {}
        for node in nodes:
            name = node.get('name', '')
            if name:
                index.setdefault(name, []).append(node)
        return index
    
    def _index_nodes_by_file(self, nodes: List[Dict]) -> Dict[str, List[Dict]]:
        """Index nodes by file for fast lookup."""
        index = {}
        for node in nodes:
            file = node.get('file', '')
            if file:
                index.setdefault(file, []).append(node)
        return index
    
    def _find_containing_class(self, line: int, file_ctx: FileContext) -> Optional[str]:
        """Find the class containing a given line."""
        for class_name, class_info in file_ctx.classes.items():
            if class_info['start'] <= line <= class_info['end']:
                return class_name
        return None
    
    def _resolve_class_name(self, class_name: str, graph_ctx: Dict) -> Optional[str]:
        """Resolve a class name to its full symbol ID."""
        # Try to find the class in the graph
        for node in graph_ctx.get('nodes', []):
            if node.get('name') == class_name and node.get('kind') == 'object':
                return node['id']
            # Also check for class_name.method patterns
            if node.get('class_name') == class_name:
                return node['id']
        return None
