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
    """Extract function calls using tree-sitter."""
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
                    name = fn.text.decode('utf-8').strip()
                    # For member access like obj.method, take the last segment
                    for sep in ('.', '->', '::'):
                        if sep in name:
                            name = name.rsplit(sep, 1)[-1]
                    name = name.strip('()[] ')
                    if name and name.isidentifier():
                        calls.append({
                            'name': name,
                            'line': node.start_point[0] + 1,
                            'type': 'method' if ('.' in fn.text.decode('utf-8') or '->' in fn.text.decode('utf-8')) else 'direct'
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
                    # Get the function name
                    if function_node.type == 'identifier':
                        name = function_node.text.decode('utf-8')
                        calls.append({
                            'name': name,
                            'line': node.start_point[0] + 1,
                            'type': 'direct'
                        })
                    elif function_node.type == 'attribute':
                        # Method call: obj.method() or self.method()
                        attribute_node = function_node.child_by_field_name('attribute')
                        if attribute_node:
                            name = attribute_node.text.decode('utf-8')
                            calls.append({
                                'name': name,
                                'line': node.start_point[0] + 1,
                                'type': 'method'
                            })
        else:
            # JavaScript/TypeScript call node types
            if node.type in ['call_expression', 'new_expression']:
                function_node = node.child_by_field_name('function')
                if function_node:
                    # Get the function name
                    if function_node.type == 'identifier':
                        name = function_node.text.decode('utf-8')
                        calls.append({
                            'name': name,
                            'line': node.start_point[0] + 1,
                            'type': 'direct'
                        })
                    elif function_node.type == 'member_expression':
                        # Method call: obj.method() or this.method()
                        property_node = function_node.child_by_field_name('property')
                        if property_node:
                            name = property_node.text.decode('utf-8')
                            calls.append({
                                'name': name,
                                'line': node.start_point[0] + 1,
                                'type': 'method'
                            })
        
        for child in node.children:
            walk_node(child)
    
    walk_node(root)
    return calls
