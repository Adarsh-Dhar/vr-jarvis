"""Tree-sitter parser for JavaScript/TypeScript files."""
import tree_sitter_typescript
import tree_sitter_python
from tree_sitter import Language, Parser

# Initialize parsers
TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
PY_LANGUAGE = Language(tree_sitter_python.language())

def parse_file(file_path: str, text: str):
    """Parse a file using tree-sitter and return the AST."""
    if file_path.endswith(('.ts', '.tsx')):
        parser = Parser(TSX_LANGUAGE if file_path.endswith('.tsx') else TS_LANGUAGE)
    elif file_path.endswith('.py'):
        parser = Parser(PY_LANGUAGE)
    else:
        # For JS/JSX, use TypeScript parser as fallback
        parser = Parser(TS_LANGUAGE)
    
    return parser.parse(text.encode('utf-8'))

def extract_symbols_with_tree_sitter(file_path: str, text: str):
    """Extract symbols using tree-sitter instead of regex."""
    tree = parse_file(file_path, text)
    root = tree.root_node
    
    symbols = []
    
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
        # JavaScript/TypeScript: function_declaration, arrow_function, class_declaration
        def walk_node(node):
            if node.type in ['function_declaration', 'function_expression', 'arrow_function']:
                name_node = node.child_by_field_name('name')
                if name_node:
                    symbols.append({
                        'name': name_node.text.decode('utf-8'),
                        'kind': 'function',
                        'start': node.start_point[0] + 1,
                        'end': node.end_point[0] + 1
                    })
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
    
    calls = []
    
    def walk_node(node):
        # Look for call expressions
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
                    # Method call: obj.method()
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
