"""Tree-sitter parser for multiple languages."""
import tree_sitter_typescript
import tree_sitter_python
import tree_sitter_go
import tree_sitter_rust
import tree_sitter_java
import tree_sitter_c_sharp
import tree_sitter_cpp
from tree_sitter import Language, Parser

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
    ext = '.' + file_path.rsplit('.', 1)[-1].lower() if '.' in file_path else ''
    if ext == '.py':
        return 'python'
    if ext in ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'):
        return 'js'
    if ext == '.go':
        return 'go'
    if ext == '.rs':
        return 'rust'
    if ext == '.java':
        return 'java'
    if ext == '.cs':
        return 'csharp'
    return 'cpp'

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
                # ES6 import
                for child in node.children:
                    if child.type == 'import_clause':
                        for spec in child.children:
                            if spec.type == 'import_specifier':
                                # import {x} from 'module'
                                name_node = spec.child_by_field_name('name')
                                alias_node = spec.child_by_field_name('alias')
                                name = name_node.text.decode('utf-8') if name_node else None
                                alias = alias_node.text.decode('utf-8') if alias_node else None
                                
                                # Find the module string
                                from_node = node.child_by_field_name('source')
                                module = from_node.text.decode('utf-8').strip('"\'') if from_node else None
                                
                                imports.append({
                                    'module': module,
                                    'name': name,
                                    'alias': alias,
                                    'kind': 'import',
                                    'line': node.start_point[0] + 1,
                                    'level': level
                                })
                    elif spec.type == 'namespace_import':
                        # import * as x from 'module'
                        alias_node = spec.child_by_field_name('name')
                        alias = alias_node.text.decode('utf-8') if alias_node else None
                        from_node = node.child_by_field_name('source')
                        module = from_node.text.decode('utf-8').strip('"\'') if from_node else None
                        
                        imports.append({
                            'module': module,
                            'name': None,
                            'alias': alias,
                            'kind': 'import',
                            'line': node.start_point[0] + 1,
                            'level': level
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
