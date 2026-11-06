"""Tree-sitter parser for multiple languages."""
import re

import tree_sitter_typescript
import tree_sitter_python
import tree_sitter_go
import tree_sitter_rust
import tree_sitter_java
import tree_sitter_c_sharp
import tree_sitter_cpp
from tree_sitter import Language, Parser

from ..languages import language_for_path, language_family as _lang_family_shared

# Initialize parsers
TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
PY_LANGUAGE = Language(tree_sitter_python.language())
GO_LANGUAGE = Language(tree_sitter_go.language())
RUST_LANGUAGE = Language(tree_sitter_rust.language())
JAVA_LANGUAGE = Language(tree_sitter_java.language())
CSHARP_LANGUAGE = Language(tree_sitter_c_sharp.language())
CPP_LANGUAGE = Language(tree_sitter_cpp.language())

EXT_TO_LANG = {
    '.ts': TS_LANGUAGE, '.tsx': TSX_LANGUAGE, '.js': TS_LANGUAGE, '.jsx': TS_LANGUAGE, '.mjs': TS_LANGUAGE, '.cjs': TS_LANGUAGE,
    '.py': PY_LANGUAGE,
    '.go': GO_LANGUAGE,
    '.rs': RUST_LANGUAGE,
    '.java': JAVA_LANGUAGE,
    '.cs': CSHARP_LANGUAGE,
    '.cpp': CPP_LANGUAGE, '.cc': CPP_LANGUAGE, '.cxx': CPP_LANGUAGE, '.hpp': CPP_LANGUAGE, '.h': CPP_LANGUAGE,
}

# Node types that represent function/method declarations per language family
_FUNC_TYPES = {
    'python': {'function_definition', 'class_definition'},
    'js': {'function_declaration', 'function_expression', 'arrow_function', 'class_declaration',
           'variable_declarator', 'pair', 'method_definition'},
    'go': {'function_declaration', 'method_declaration', 'type_declaration'},
    'rust': {'function_item', 'function_signature_item', 'struct_item', 'enum_item', 'impl_item'},
    'java': {'method_declaration', 'class_declaration', 'interface_declaration', 'constructor_declaration'},
    'csharp': {'method_declaration', 'constructor_declaration', 'class_declaration', 'interface_declaration'},
    'cpp': {'function_definition', 'class_specifier', 'struct_specifier'},
}

# Call node types per language family
_CALL_TYPES = {
    'python': {'call'},
    'js': {'call_expression', 'new_expression'},
    'go': {'call_expression'},
    'rust': {'call_expression'},
    'java': {'method_invocation', 'object_creation_expression'},
    'csharp': {'invocation_expression', 'object_creation_expression'},
    'cpp': {'call_expression'},
}

def _lang_family(file_path: str) -> str:
    return _lang_family_shared(file_path)

def parse_file(file_path: str, text: str):
    """Parse a file using tree-sitter and return the AST."""
    ext = '.' + file_path.rsplit('.', 1)[-1].lower() if '.' in file_path else ''
    if file_path.endswith('.tsx'):
        lang = TSX_LANGUAGE
    elif file_path.endswith(('.ts', '.js', '.jsx', '.mjs', '.cjs')):
        lang = TS_LANGUAGE
    else:
        lang = EXT_TO_LANG.get(ext, TS_LANGUAGE)
    parser = Parser(lang)
    return parser.parse(text.encode('utf-8'))

def extract_symbols_with_tree_sitter(file_path: str, text: str):
    """Extract symbols using tree-sitter instead of regex."""
    tree = parse_file(file_path, text)
    root = tree.root_node
    family = _lang_family(file_path)
    symbols = []

    if family in ('go', 'rust', 'java', 'csharp', 'cpp'):
        # Generic extraction for the newly added languages
        func_types = _FUNC_TYPES[family]
        object_types = {'class_declaration', 'struct_item', 'enum_item', 'impl_item',
                        'interface_declaration', 'class_specifier', 'struct_specifier',
                        'type_declaration'}

        CPP_KEYWORDS = {'void', 'int', 'char', 'float', 'double', 'bool', 'auto', 'long',
                        'short', 'unsigned', 'signed', 'const', 'static', 'virtual',
                        'public', 'private', 'protected', 'inline', 'extern', 'struct',
                        'class', 'enum', 'union', 'typename', 'template', 'namespace',
                        'if', 'else', 'for', 'while', 'return', 'new', 'delete'}

        def decl_name(node):
            # Descend declarator chains to the innermost identifier (C/C++/Java/C#)
            d = node.child_by_field_name('declarator') or node.child_by_field_name('name')
            depth = 0
            while d is not None and depth < 6:
                if d.type == 'identifier' or d.type == 'field_identifier' or d.type == 'type_identifier':
                    return d.text.decode('utf-8')
                nxt = d.child_by_field_name('declarator') or d.child_by_field_name('name')
                if nxt is None and len(d.children) > 0:
                    # scan children for an identifier-ish node
                    for c in d.children:
                        if c.type in ('identifier', 'field_identifier', 'type_identifier',
                                      'function_declarator', 'identifier_declarator',
                                      'pointer_declarator', 'reference_declarator'):
                            nxt = c
                            break
                d = nxt
                depth += 1
            return None

        def walk(node):
            if node.type in func_types or node.type in object_types:
                name = decl_name(node)
                if name is None and node.type in object_types:
                    name_node = node.child_by_field_name('name')
                    name = name_node.text.decode('utf-8') if name_node else None
                if name and name not in CPP_KEYWORDS:
                    kind = 'object' if node.type in object_types else 'function'
                    symbols.append({
                        'name': name.split('.')[-1].split('::')[-1],
                        'kind': kind,
                        'start': node.start_point[0] + 1,
                        'end': node.end_point[0] + 1
                    })
            for child in node.children:
                walk(child)
        walk(root)
        return symbols

    if file_path.endswith('.py'):
        # Python: function_def, class_def
        def walk_node(node):
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    symbols.append({
                        'name': name_node.text.decode('utf-8'),
                        'kind': 'function',
                        'start': node.start_point[0] + 1,
                        'end': node.end_point[0] + 1
                    })
            elif node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    symbols.append({
                        'name': name_node.text.decode('utf-8'),
                        'kind': 'object',
                        'start': node.start_point[0] + 1,
                        'end': node.end_point[0] + 1
                    })
            
            for child in node.children:
                walk_node(child)
        
        walk_node(root)
    
    else:
        # JavaScript/TypeScript: function_declaration, arrow_function, class_declaration, variable_declarator, pair
        def walk_node(node):
            # Handle named function declarations
            if node.type in ['function_declaration', 'function_expression']:
                name_node = node.child_by_field_name('name')
                if name_node:
                    symbols.append({
                        'name': name_node.text.decode('utf-8'),
                        'kind': 'function',
                        'start': node.start_point[0] + 1,
                        'end': node.end_point[0] + 1
                    })
            # Handle arrow functions assigned to variables
            elif node.type == 'variable_declarator':
                name_node = node.child_by_field_name('name')
                value_node = node.child_by_field_name('value')
                if name_node and value_node and value_node.type in ['arrow_function', 'function_expression']:
                    symbols.append({
                        'name': name_node.text.decode('utf-8'),
                        'kind': 'function',
                        'start': node.start_point[0] + 1,
                        'end': node.end_point[0] + 1
                    })
            # Handle object property assignments with functions
            elif node.type == 'pair':
                key_node = node.child_by_field_name('key')
                value_node = node.child_by_field_name('value')
                if key_node and value_node and value_node.type in ['arrow_function', 'function_expression']:
                    symbols.append({
                        'name': key_node.text.decode('utf-8'),
                        'kind': 'function',
                        'start': node.start_point[0] + 1,
                        'end': node.end_point[0] + 1
                    })
            # Handle class declarations
            elif node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    symbols.append({
                        'name': name_node.text.decode('utf-8'),
                        'kind': 'object',
                        'start': node.start_point[0] + 1,
                        'end': node.end_point[0] + 1
                    })
            
            for child in node.children:
                walk_node(child)
        
        walk_node(root)
    
    return symbols

def extract_calls_with_tree_sitter(file_path: str, text: str):
    """Extract function calls using tree-sitter.
    
    Returns dict with:
    - name: function/method name
    - receiver: text before last ., ->, or :: (e.g., "authentication" in authentication.validate())
    - full_expression: complete call expression
    - line: line number (1-based)
    - column: column number (0-based)
    - end_line: end line number (1-based)
    - call_type: direct, method, constructor, dynamic
    - arg_count: number of arguments
    """
    tree = parse_file(file_path, text)
    root = tree.root_node
    family = _lang_family(file_path)
    calls = []

    if family in ('go', 'rust', 'java', 'csharp', 'cpp'):
        call_types = _CALL_TYPES[family]

        def walk(node):
            if node.type in call_types:
                # Try common function-name fields across grammars
                fn = (node.child_by_field_name('function')
                      or node.child_by_field_name('name')
                      or node.child_by_field_name('constructor')
                      or node.child_by_field_name('object'))
                if fn is not None:
                    full_expr = fn.text.decode('utf-8').strip()
                    name = full_expr
                    receiver = ''
                    
                    # Extract receiver and name
                    for sep in ('.', '->', '::'):
                        if sep in name:
                            parts = name.rsplit(sep, 1)
                            receiver = parts[0].strip()
                            name = parts[1].strip()
                            break
                    
                    name = name.strip('()[] ')
                    full_expr = full_expr.strip('()[] ')
                    
                    # Count arguments
                    args_node = node.child_by_field_name('arguments')
                    arg_count = 0
                    if args_node:
                        arg_count = len([c for c in args_node.children if c.type not in ('(', ')', ',')])
                    
                    # Determine call type
                    if node.type == 'object_creation_expression' or 'new_expression' in node.type:
                        call_type = 'constructor'
                    elif receiver:
                        call_type = 'method'
                    else:
                        call_type = 'direct'
                    
                    if name and name.isidentifier():
                        calls.append({
                            'name': name,
                            'receiver': receiver,
                            'full_expression': full_expr,
                            'line': node.start_point[0] + 1,
                            'column': node.start_point[1],
                            'end_line': node.end_point[0] + 1,
                            'call_type': call_type,
                            'arg_count': arg_count
                        })
            for child in node.children:
                walk(child)
        walk(root)
        return calls

    def walk_node(node):
        # Look for call expressions - different node types for Python vs JS/TS
        if file_path.endswith('.py'):
            # Python call node type is 'call'
            if node.type == 'call':
                function_node = node.child_by_field_name('function')
                if function_node:
                    full_expr = function_node.text.decode('utf-8').strip()
                    name = full_expr
                    receiver = ''
                    
                    # Extract receiver and name for method calls
                    if function_node.type == 'attribute':
                        object_node = function_node.child_by_field_name('object')
                        attribute_node = function_node.child_by_field_name('attribute')
                        if object_node and attribute_node:
                            receiver = object_node.text.decode('utf-8').strip()
                            name = attribute_node.text.decode('utf-8').strip()
                    
                    # Count arguments
                    args_node = node.child_by_field_name('arguments')
                    arg_count = 0
                    if args_node:
                        arg_count = len([c for c in args_node.children if c.type not in ('(', ')', ',')])
                    
                    # Determine call type
                    if receiver:
                        call_type = 'method'
                    else:
                        call_type = 'direct'
                    
                    calls.append({
                        'name': name,
                        'receiver': receiver,
                        'full_expression': full_expr,
                        'line': node.start_point[0] + 1,
                        'column': node.start_point[1],
                        'end_line': node.end_point[0] + 1,
                        'call_type': call_type,
                        'arg_count': arg_count
                    })
        else:
            # JavaScript/TypeScript call node types
            if node.type in ['call_expression', 'new_expression']:
                function_node = node.child_by_field_name('function')
                if function_node:
                    full_expr = function_node.text.decode('utf-8').strip()
                    name = full_expr
                    receiver = ''
                    
                    # Extract receiver and name for method calls
                    if function_node.type == 'member_expression':
                        object_node = function_node.child_by_field_name('object')
                        property_node = function_node.child_by_field_name('property')
                        if object_node and property_node:
                            receiver = object_node.text.decode('utf-8').strip()
                            name = property_node.text.decode('utf-8').strip()
                    
                    # Count arguments
                    args_node = node.child_by_field_name('arguments')
                    arg_count = 0
                    if args_node:
                        arg_count = len([c for c in args_node.children if c.type not in ('(', ')', ',')])
                    
                    # Determine call type
                    if node.type == 'new_expression':
                        call_type = 'constructor'
                    elif receiver:
                        call_type = 'method'
                    else:
                        call_type = 'direct'
                    
                    calls.append({
                        'name': name,
                        'receiver': receiver,
                        'full_expression': full_expr,
                        'line': node.start_point[0] + 1,
                        'column': node.start_point[1],
                        'end_line': node.end_point[0] + 1,
                        'call_type': call_type,
                        'arg_count': arg_count
                    })
        
        for child in node.children:
            walk_node(child)
    
    walk_node(root)
    return calls


def extract_imports_with_tree_sitter(file_path: str, text: str):
    """Extract import statements using tree-sitter.
    
    Returns list of dicts with:
    - module: imported module path
    - name: imported name (if using 'from X import Y')
    - alias: import alias (if using 'import X as Y')
    - kind: import statement type (import, from, require)
    - line: line number (1-based)
    - level: nesting level (0 for top-level)
    """
    tree = parse_file(file_path, text)
    root = tree.root_node
    imports = []
    
    if file_path.endswith('.py'):
        # Use AST for Python for better import extraction
        import ast
        try:
            tree_ast = ast.parse(text)
            
            for node in ast.walk(tree_ast):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({
                            'module': alias.name,
                            'name': None,
                            'alias': alias.asname,
                            'kind': 'import',
                            'line': node.lineno,
                            'level': 0  # Python imports are always at module level
                        })
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports.append({
                            'module': module,
                            'name': alias.name,
                            'alias': alias.asname,
                            'kind': 'from',
                            'line': node.lineno,
                            'level': 0
                        })
        except SyntaxError:
            pass
    else:
        # Use tree-sitter for JavaScript/TypeScript
        def walk_node(node, level=0):
            # import_statement, require, and import() nodes
            if node.type == 'import_statement':
                # ES6 import: import [def] [,] [{a as b}] [, * as ns] from 'mod'
                from_node = node.child_by_field_name('source')
                module = from_node.text.decode('utf-8').strip('"\'') if from_node else None

                def _spec_nodes(n):
                    for c in n.children:
                        if c.type in ('import_specifier', 'namespace_import'):
                            yield c
                        else:
                            yield from _spec_nodes(c)

                for child in node.children:
                    if child.type != 'import_clause':
                        continue
                    # default import: bare identifier child of import_clause
                    default_name = None
                    for c in child.children:
                        if c.type == 'identifier':
                            default_name = c.text.decode('utf-8')
                            break
                    if default_name:
                        imports.append({
                            'module': module, 'name': 'default', 'alias': default_name,
                            'kind': 'import', 'line': node.start_point[0] + 1, 'level': level,
                        })
                    for spec in _spec_nodes(child):
                        if spec.type == 'import_specifier':
                            # import {x} / {x as y} from 'module'
                            name_node = spec.child_by_field_name('name')
                            alias_node = spec.child_by_field_name('alias')
                            name = name_node.text.decode('utf-8') if name_node else None
                            alias = alias_node.text.decode('utf-8') if alias_node else None
                            imports.append({
                                'module': module, 'name': name, 'alias': alias,
                                'kind': 'import', 'line': node.start_point[0] + 1, 'level': level,
                            })
                        elif spec.type == 'namespace_import':
                            # import * as x from 'module'
                            alias_node = spec.child_by_field_name('name')
                            alias = alias_node.text.decode('utf-8') if alias_node else None
                            imports.append({
                                'module': module, 'name': None, 'alias': alias,
                                'kind': 'import', 'line': node.start_point[0] + 1, 'level': level,
                            })
            elif node.type == 'call_expression':
                # Check for require('module')
                function_node = node.child_by_field_name('function')
                if function_node and function_node.type == 'identifier':
                    if function_node.text.decode('utf-8') == 'require':
                        args_node = node.child_by_field_name('arguments')
                        if args_node:
                            for arg in args_node.children:
                                if arg.type == 'string':
                                    module = arg.text.decode('utf-8').strip('"\'')
                                    imports.append({
                                        'module': module,
                                        'name': None,
                                        'alias': None,
                                        'kind': 'require',
                                        'line': node.start_point[0] + 1,
                                        'level': level
                                    })
                                    break
            
            for child in node.children:
                walk_node(child, level + 1)
        
        walk_node(root)
    
    return imports


# ---------------------------------------------------------------------------
# Structured extraction: symbols and call sites with lexical ownership.
# Used by the indexer for non-Python languages. Python uses
# intelligence.parsers.python_ast.analyze_python_source instead.
# ---------------------------------------------------------------------------

# Function-like node types per family (used to establish call-site ownership)
_FUNCTION_LIKE = {
    'js': {'function_declaration', 'function_expression', 'arrow_function',
           'generator_function_declaration', 'generator_function',
           'method_definition', 'function_signature'},
    'go': {'function_declaration', 'method_declaration'},
    'rust': {'function_item', 'function_signature_item'},
    'java': {'method_declaration', 'constructor_declaration'},
    'csharp': {'method_declaration', 'constructor_declaration'},
    'cpp': {'function_definition'},
}

_OBJECT_TYPES = {
    'js': {'class_declaration', 'class', 'abstract_class_declaration',
           'interface_declaration', 'internal_module'},
    'go': {'type_declaration'},
    'rust': {'struct_item', 'enum_item', 'impl_item', 'trait_item', 'mod_item'},
    'java': {'class_declaration', 'interface_declaration', 'enum_declaration'},
    'csharp': {'class_declaration', 'interface_declaration', 'struct_declaration',
               'enum_declaration', 'record_declaration'},
    'cpp': {'class_specifier', 'struct_specifier', 'namespace_definition'},
}


def _node_text(node) -> str:
    try:
        return node.text.decode('utf-8')
    except Exception:
        return ''


def _field_text(node, field) -> str:
    child = node.child_by_field_name(field)
    return _node_text(child) if child is not None else ''


def _js_symbol_name(node):
    """Best-effort name for a JS/TS declaration node."""
    t = node.type
    if t in ('function_declaration', 'function_expression', 'generator_function_declaration',
             'generator_function'):
        return _field_text(node, 'name')
    if t == 'method_definition':
        return _field_text(node, 'name')
    if t == 'arrow_function':
        return ''  # named by the declarator/pair that owns it
    if t in ('class_declaration', 'class', 'abstract_class_declaration',
             'interface_declaration'):
        return _field_text(node, 'name')
    return ''


def _js_declarator_name(node):
    name_node = node.child_by_field_name('name')
    if name_node is not None and name_node.type == 'identifier':
        return _node_text(name_node)
    return ''


def extract_symbols_structured(file_path: str, text: str):
    """Extract symbols with qualified names and lexical parents.

    Returns a list of dicts compatible with the Python analyzer's symbol shape:
    name, qualname, kind ('function'|'method'|'object'), class_name,
    class_qualname, parent_qualname, file, language, start, end, signature,
    parameters, id.
    """
    language = language_for_path(file_path)
    family = _lang_family(file_path)
    if family == 'python':
        # Python has its own analyzer; keep this function total anyway.
        from .python_ast import analyze_python_source
        return analyze_python_source(text, file_path).get('symbols', [])

    tree = parse_file(file_path, text)
    root = tree.root_node
    symbols = []

    func_like = _FUNCTION_LIKE.get(family, set())
    object_types = _OBJECT_TYPES.get(family, set())

    # stack entries: (kind, name, is_class_scope)
    stack = []

    def qualname():
        return '.'.join(n for _, n, _ in stack if n)

    def current_class_qualname():
        classes = [q for k, q, _ in stack]
        # stack holds names not quals; rebuild class quals below
        return ''

    # We track (node_type, name, qualname_at_entry) to compute class_qualname.
    # Simpler: keep parallel list of (is_object, qualname).
    scope_meta = []  # list of dicts {is_object, qualname}

    def _meta():
        objs = [m['qualname'] for m in scope_meta if m['is_object']]
        return objs[-1] if objs else ''

    def _parent_qual():
        return scope_meta[-1]['qualname'] if scope_meta else ''

    def _emit(node, name, kind):
        if not name:
            return
        parent_q = _parent_qual()
        qual = f'{parent_q}.{name}' if parent_q else name
        is_method = kind == 'method' or (kind == 'function' and _meta())
        sym = {
            'name': name,
            'qualname': qual,
            'kind': 'method' if is_method and kind != 'object' else kind,
            'class_name': (_meta().split('.')[-1] if _meta() else ''),
            'class_qualname': _meta(),
            'parent_qualname': parent_q,
            'file': file_path,
            'language': language,
            'start': node.start_point[0] + 1,
            'end': node.end_point[0] + 1,
            'signature': '',
            'parameters': [],
            'decorators': [],
            'id': f'{file_path}::{qual}',
        }
        symbols.append(sym)
        return qual

    CPP_KEYWORDS = {'void', 'int', 'char', 'float', 'double', 'bool', 'auto', 'long',
                    'short', 'unsigned', 'signed', 'const', 'static', 'virtual',
                    'public', 'private', 'protected', 'inline', 'extern', 'struct',
                    'class', 'enum', 'union', 'typename', 'template', 'namespace',
                    'if', 'else', 'for', 'while', 'return', 'new', 'delete'}

    def decl_name(node):
        d = node.child_by_field_name('declarator') or node.child_by_field_name('name')
        depth = 0
        while d is not None and depth < 6:
            if d.type in ('identifier', 'field_identifier', 'type_identifier'):
                return _node_text(d)
            nxt = d.child_by_field_name('declarator') or d.child_by_field_name('name')
            if nxt is None and len(d.children) > 0:
                for c in d.children:
                    if c.type in ('identifier', 'field_identifier', 'type_identifier',
                                  'function_declarator', 'identifier_declarator',
                                  'pointer_declarator', 'reference_declarator'):
                        nxt = c
                        break
            d = nxt
            depth += 1
        return None

    def visit(node):
        t = node.type
        pushed = False
        name = None
        kind = None
        is_object = t in object_types

        if family == 'js':
            if t in ('function_declaration', 'function_expression', 'generator_function_declaration',
                     'generator_function'):
                name = _js_symbol_name(node)
                kind = 'function'
            elif t == 'method_definition':
                name = _js_symbol_name(node)
                kind = 'method'
            elif t == 'arrow_function':
                # named by owning declarator/pair; anonymous otherwise
                kind = 'function'
                name = ''
            elif t in ('class_declaration', 'class', 'abstract_class_declaration',
                       'interface_declaration', 'internal_module'):
                name = _js_symbol_name(node)
                kind = 'object'
            elif t == 'variable_declarator':
                value = node.child_by_field_name('value')
                if value is not None and value.type in ('arrow_function', 'function_expression',
                                                         'generator_function'):
                    name = _js_declarator_name(node)
                    kind = 'function'
            elif t == 'pair':
                value = node.child_by_field_name('value')
                if value is not None and value.type in ('arrow_function', 'function_expression'):
                    name = _field_text(node, 'key')
                    kind = 'method'
        else:
            if t in func_like:
                name = decl_name(node)
                kind = 'method' if t in ('method_declaration',) else 'function'
            elif t in object_types:
                name = decl_name(node)
                if name is None:
                    name = _field_text(node, 'name')
                kind = 'object'
            if name in CPP_KEYWORDS:
                name = None

        qual = None
        if name and kind:
            if t == 'variable_declarator' or t == 'pair':
                # the declarator itself is the symbol; its value child is the body
                qual = _emit(node, name, kind)
            else:
                qual = _emit(node, name, kind)

        # For declarator/pair we emitted the symbol but must still descend into
        # the function value so nested calls/symbols get the right owner.
        descend_as_scope = bool(qual) or (kind == 'function' and t in ('arrow_function',))
        if descend_as_scope:
            scope_name = name or (qual.split('.')[-1] if qual else '')
            scope_qual = qual or _parent_qual()
            scope_meta.append({'is_object': is_object or kind == 'object',
                               'qualname': scope_qual or scope_name})
            pushed = True

        for child in node.children:
            # skip re-processing: variable_declarator's value arrow_function would
            # double-push an anonymous scope; harmless since name '' -> qual same
            visit(child)

        if pushed:
            scope_meta.pop()

    visit(root)
    return symbols


def extract_calls_structured(file_path: str, text: str):
    """Extract call sites with their owning function (lexical, not line ranges).

    Returns dicts compatible with the Python analyzer's call-site shape:
    callsite_id, caller_id, caller_qualname, name, receiver, receiver_root,
    receiver_expr, full_expression, line, column, end_line, end_column,
    call_type, arg_count, file, language.
    """
    language = language_for_path(file_path)
    family = _lang_family(file_path)
    tree = parse_file(file_path, text)
    root = tree.root_node
    calls = []

    func_like = _FUNCTION_LIKE.get(family, set())
    call_types = _CALL_TYPES.get(family, {'call_expression', 'new_expression'})

    # owner stack: qualnames of enclosing function-like nodes
    owner_stack = []

    def visit(node):
        t = node.type
        # Determine if this node opens a named function scope
        scope_name = None
        is_func_scope = False
        if family == 'js':
            if t in ('function_declaration', 'function_expression', 'generator_function_declaration',
                     'generator_function', 'method_definition', 'function_signature'):
                scope_name = _js_symbol_name(node)
                is_func_scope = True
            elif t == 'variable_declarator':
                value = node.child_by_field_name('value')
                if value is not None and value.type in ('arrow_function', 'function_expression',
                                                         'generator_function'):
                    scope_name = _js_declarator_name(node)
                    is_func_scope = True
            elif t == 'pair':
                value = node.child_by_field_name('value')
                if value is not None and value.type in ('arrow_function', 'function_expression'):
                    scope_name = _field_text(node, 'key')
                    is_func_scope = True
            elif t == 'arrow_function':
                is_func_scope = True  # anonymous scope keeps owner qualname
        else:
            if t in func_like:
                scope_name = decl_name_fallback(node)
                is_func_scope = True

        if t in call_types:
            calls.append(_make_call(node, file_path, language, owner_stack))

        if is_func_scope:
            parent = owner_stack[-1] if owner_stack else ''
            qual = f'{parent}.{scope_name}' if (parent and scope_name) else (scope_name or parent)
            owner_stack.append(qual or '')
            for child in node.children:
                visit(child)
            owner_stack.pop()
        else:
            for child in node.children:
                visit(child)

    def decl_name_fallback(node):
        d = node.child_by_field_name('declarator') or node.child_by_field_name('name')
        depth = 0
        while d is not None and depth < 6:
            if d.type in ('identifier', 'field_identifier', 'type_identifier'):
                return _node_text(d)
            nxt = d.child_by_field_name('declarator') or d.child_by_field_name('name')
            if nxt is None and len(d.children) > 0:
                for c in d.children:
                    if c.type in ('identifier', 'field_identifier', 'type_identifier',
                                  'function_declarator', 'identifier_declarator'):
                        nxt = c
                        break
            d = nxt
            depth += 1
        return ''

    def _member_parts(expr_node):
        """Return (receiver_text, name) for member_expression-ish nodes."""
        obj = expr_node.child_by_field_name('object')
        prop = (expr_node.child_by_field_name('property')
                or expr_node.child_by_field_name('attribute')
                or expr_node.child_by_field_name('field'))
        if prop is None:
            return '', _node_text(expr_node)
        recv = _node_text(obj) if obj is not None else ''
        return recv, _node_text(prop)

    def _root_of(expr_text):
        # leftmost identifier of a dotted/call chain
        m = re.match(r'\s*([A-Za-z_$][\w$]*)', expr_text or '')
        return m.group(1) if m else ''

    def _make_call(node, fpath, lang, owners):
        fn = (node.child_by_field_name('function')
              or node.child_by_field_name('name')
              or node.child_by_field_name('constructor'))
        name = ''
        receiver = ''
        receiver_root = ''
        receiver_expr = ''
        call_type = 'direct'
        full_expr = ''

        if fn is not None:
            full_expr = _node_text(fn).strip()
            if fn.type in ('member_expression', 'attribute', 'field_expression',
                           'navigation_expression', 'qualified_identifier'):
                receiver, name = _member_parts(fn)
                receiver_expr = receiver
                receiver_root = _root_of(receiver)
                call_type = 'method'
            elif fn.type in ('identifier', 'field_identifier', 'type_identifier'):
                name = _node_text(fn)
            else:
                name = full_expr
                call_type = 'dynamic'
                receiver_expr = full_expr
        else:
            name = _node_text(node).strip()
            call_type = 'dynamic'

        args_node = node.child_by_field_name('arguments')
        arg_count = 0
        if args_node is not None:
            arg_count = len([c for c in args_node.children
                             if c.type not in ('(', ')', ',', 'comment')])

        if node.type in ('new_expression', 'object_creation_expression'):
            call_type = 'constructor' if call_type == 'direct' else call_type

        line = node.start_point[0] + 1
        col = node.start_point[1]
        end_line = node.end_point[0] + 1
        caller_qual = owners[-1] if owners else ''
        caller_id = f'{fpath}::{caller_qual}' if caller_qual else None

        return {
            'callsite_id': f'{fpath}:{line}:{col}',
            'caller_id': caller_id,
            'caller_qualname': caller_qual,
            'name': name,
            'receiver': receiver,
            'receiver_root': receiver_root,
            'receiver_expr': receiver_expr,
            'full_expression': full_expr or name,
            'line': line,
            'column': col,
            'end_line': end_line,
            'end_column': node.end_point[1],
            'call_type': call_type,
            'arg_count': arg_count,
            'file': fpath,
            'language': lang,
        }

    visit(root)
    return calls
