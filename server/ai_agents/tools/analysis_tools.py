"""
Universal Analysis Tools - Shared Superpowers (Part C)
These tools provide static analysis capabilities for code understanding.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import ast
import re
from google.adk.tools import ToolContext
from ._safe import safe
from ._common import resolve_in_repo


def _is_python_file(file_path: str) -> bool:
    """Check if a file is a Python file."""
    return file_path.endswith('.py')


def _parse_python_ast(file_path: str) -> Optional[ast.AST]:
    """Parse Python file into AST."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return ast.parse(f.read())
    except Exception:
        return None


def _ast_to_dict(node: ast.AST) -> Dict:
    """Convert AST node to dictionary representation."""
    if not hasattr(node, '__dict__'):
        return str(node)
    
    result = {'type': node.__class__.__name__}
    for key, value in node.__dict__.items():
        if key == 'ctx':
            continue
        if isinstance(value, list):
            result[key] = [_ast_to_dict(item) if hasattr(item, '__dict__') else str(item) for item in value]
        elif hasattr(value, '__dict__'):
            result[key] = _ast_to_dict(value)
        else:
            result[key] = str(value)
    return result


@safe
def parse_source_code(file_path: str, tool_context: ToolContext) -> dict:
    """Parse source code into syntax trees."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        if _is_python_file(file_path):
            tree = _parse_python_ast(file_path)
            if tree:
                return {
                    'status': 'ok',
                    'file_path': file_path,
                    'language': 'python',
                    'ast': _ast_to_dict(tree)
                }
        
        # For other languages, return basic info
        content = path.read_text(encoding='utf-8')
        return {
            'status': 'ok',
            'file_path': file_path,
            'language': 'unknown',
            'ast': None,
            'note': 'AST parsing only implemented for Python'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def extract_ast(file_path: str, tool_context: ToolContext) -> dict:
    """Extract abstract syntax trees."""
    return parse_source_code(file_path, tool_context)


@safe
def extract_symbols(file_path: str, tool_context: ToolContext) -> dict:
    """Extract functions, classes, methods, fields and variables."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        symbols = []
        
        if _is_python_file(file_path):
            tree = _parse_python_ast(file_path)
            if tree:
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        symbols.append({
                            'name': node.name,
                            'type': 'function',
                            'line': node.lineno,
                            'parameters': [arg.arg for arg in node.args.args]
                        })
                    elif isinstance(node, ast.ClassDef):
                        symbols.append({
                            'name': node.name,
                            'type': 'class',
                            'line': node.lineno,
                            'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                        })
                    elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                        symbols.append({
                            'name': node.id,
                            'type': 'variable',
                            'line': node.lineno
                        })
        else:
            # Fallback to regex for other languages
            content = path.read_text(encoding='utf-8')
            
            # Match function definitions
            func_pattern = r'(?:def|function)\s+(\w+)'
            for match in re.finditer(func_pattern, content):
                symbols.append({
                    'name': match.group(1),
                    'type': 'function',
                    'line': content[:match.start()].count('\n') + 1
                })
            
            # Match class definitions
            class_pattern = r'class\s+(\w+)'
            for match in re.finditer(class_pattern, content):
                symbols.append({
                    'name': match.group(1),
                    'type': 'class',
                    'line': content[:match.start()].count('\n') + 1
                })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'symbols': symbols
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def resolve_types(file_path: str, tool_context: ToolContext) -> dict:
    """Resolve types and type relationships."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        type_relationships = []
        
        if _is_python_file(file_path):
            tree = _parse_python_ast(file_path)
            if tree:
                for node in ast.walk(tree):
                    # Extract type annotations
                    if isinstance(node, ast.AnnAssign):
                        if node.annotation:
                            type_name = ast.unparse(node.annotation) if hasattr(ast, 'unparse') else str(node.annotation)
                            target_name = ast.unparse(node.target) if hasattr(ast, 'unparse') else str(node.target)
                            type_relationships.append({
                                'symbol': target_name,
                                'type': type_name,
                                'confidence': 1.0,
                                'line': node.lineno
                            })
                    elif isinstance(node, ast.FunctionDef):
                        # Extract parameter types
                        for arg in node.args.args:
                            if arg.annotation:
                                type_name = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)
                                type_relationships.append({
                                    'symbol': arg.arg,
                                    'type': type_name,
                                    'confidence': 1.0,
                                    'line': node.lineno
                                })
                        # Extract return type
                        if node.returns:
                            type_name = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
                            type_relationships.append({
                                'symbol': f'{node.name}()',
                                'type': type_name,
                                'confidence': 1.0,
                                'line': node.lineno
                            })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'type_relationships': type_relationships
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def resolve_references(file_path: str, tool_context: ToolContext) -> dict:
    """Resolve references between code elements."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        references = []
        
        if _is_python_file(file_path):
            tree = _parse_python_ast(file_path)
            if tree:
                # Build symbol table
                symbols = {}
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        symbols[node.name] = {'type': 'function', 'line': node.lineno}
                    elif isinstance(node, ast.ClassDef):
                        symbols[node.name] = {'type': 'class', 'line': node.lineno}
                
                # Find references
                for node in ast.walk(tree):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                        if node.id in symbols:
                            references.append({
                                'from': f'line {node.lineno}',
                                'to': f'{symbols[node.id]["type"]} {node.id}',
                                'type': 'reference',
                                'line': node.lineno
                            })
                    elif isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id in symbols:
                            references.append({
                                'from': f'line {node.lineno}',
                                'to': f'function {node.func.id}',
                                'type': 'call',
                                'line': node.lineno
                            })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'references': references
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_control_flow(function_name: str, tool_context: ToolContext) -> dict:
    """Generate control-flow information with basic blocks for Python functions."""
    try:
        from .. import codegraph

        # Use CodeGraph to resolve the function (handles dotted IDs, short names, paths)
        graph = codegraph.load_current_graph()
        node = graph.get(function_name)

        if not node:
            return {
                'status': 'not_found',
                'function_name': function_name,
                'message': 'Function not found in graph'
            }

        file_path = node.get('file', '')
        if not file_path:
            return {
                'status': 'error',
                'error': 'Node has no file path'
            }

        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'function_name': function_name,
                'message': 'Control flow analysis only implemented for Python'
            }

        tree = _parse_python_ast(file_path)
        if not tree:
            return {
                'status': 'error',
                'error': 'Could not parse file'
            }

        # Find the function node
        func_node = None
        # Extract simple name from node id or name
        simple_name = node.get('name', '')
        if not simple_name and '.' in node.get('id', ''):
            simple_name = node['id'].split('.')[-1]
        
        for node_ast in ast.walk(tree):
            if isinstance(node_ast, ast.FunctionDef) and node_ast.name == simple_name:
                func_node = node_ast
                break

        if not func_node:
            return {
                'status': 'not_found',
                'function_name': function_name,
                'message': f'Function {simple_name} not found in AST'
            }

        # Build basic blocks
        blocks = []
        edges = []
        block_id_counter = 0

        def create_block(start_line, end_line, label, block_type='sequence'):
            nonlocal block_id_counter
            block_id = f"{simple_name}#B{block_id_counter}"
            block_id_counter += 1
            return {
                'id': block_id,
                'start': start_line,
                'end': end_line,
                'label': label,
                'type': block_type,
                'file': file_path
            }

        # Entry block
        entry_block = create_block(func_node.lineno, func_node.lineno, 'entry', 'entry')
        blocks.append(entry_block)

        # Process function body
        for stmt in func_node.body:
            if isinstance(stmt, ast.If):
                # Create blocks for if-else
                condition_line = stmt.lineno
                if_block = create_block(condition_line, condition_line, f'if condition', 'condition')
                blocks.append(if_block)

                # Process if body
                if stmt.body:
                    then_start = stmt.body[0].lineno
                    then_end = stmt.body[-1].end_lineno if stmt.body[-1].end_lineno else then_start
                    then_block = create_block(then_start, then_end, 'then branch', 'sequence')
                    blocks.append(then_block)
                    edges.append({'src': if_block['id'], 'dst': then_block['id'], 'type': 'controlflow', 'kind': 'confirmed', 'edge_type': 'true'})

                # Process else body
                if stmt.orelse:
                    else_start = stmt.orelse[0].lineno
                    else_end = stmt.orelse[-1].end_lineno if stmt.orelse[-1].end_lineno else else_start
                    else_block = create_block(else_start, else_end, 'else branch', 'sequence')
                    blocks.append(else_block)
                    edges.append({'src': if_block['id'], 'dst': else_block['id'], 'type': 'controlflow', 'kind': 'confirmed', 'edge_type': 'false'})

            elif isinstance(stmt, (ast.For, ast.While)):
                # Create blocks for loops
                loop_type = 'for' if isinstance(stmt, ast.For) else 'while'
                condition_line = stmt.lineno
                loop_block = create_block(condition_line, condition_line, f'{loop_type} condition', 'loop')
                blocks.append(loop_block)

                # Process loop body
                if stmt.body:
                    body_start = stmt.body[0].lineno
                    body_end = stmt.body[-1].end_lineno if stmt.body[-1].end_lineno else body_start
                    body_block = create_block(body_start, body_end, 'loop body', 'sequence')
                    blocks.append(body_block)
                    edges.append({'src': loop_block['id'], 'dst': body_block['id'], 'type': 'controlflow', 'kind': 'confirmed', 'edge_type': 'loop'})

            elif isinstance(stmt, ast.Return):
                return_block = create_block(stmt.lineno, stmt.lineno, 'return', 'return')
                blocks.append(return_block)

            elif isinstance(stmt, ast.Raise):
                raise_block = create_block(stmt.lineno, stmt.lineno, 'raise', 'exception')
                blocks.append(raise_block)

            elif isinstance(stmt, ast.Try):
                # Create blocks for try-except
                try_start = stmt.lineno
                try_end = stmt.body[-1].end_lineno if stmt.body else try_start
                try_block = create_block(try_start, try_end, 'try block', 'sequence')
                blocks.append(try_block)

                for handler in stmt.handlers:
                    except_start = handler.lineno
                    except_end = handler.body[-1].end_lineno if handler.body else except_start
                    except_block = create_block(except_start, except_end, f'except {handler.type}', 'exception')
                    blocks.append(except_block)
                    edges.append({'src': try_block['id'], 'dst': except_block['id'], 'type': 'controlflow', 'kind': 'confirmed', 'edge_type': 'exception'})

        # Link entry to first block
        if len(blocks) > 1:
            edges.append({'src': entry_block['id'], 'dst': blocks[1]['id'], 'type': 'controlflow', 'kind': 'confirmed', 'edge_type': 'next'})

        return {
            'status': 'ok',
            'function_name': function_name,
            'simple_name': simple_name,
            'blocks': blocks,
            'edges': edges,
            'block_count': len(blocks)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_data_flow(variable_name: str, tool_context: ToolContext) -> dict:
    """Track data propagation."""
    try:
        # This is a simplified implementation
        # Real data flow analysis would require more sophisticated tracking
        return {
            'status': 'ok',
            'variable_name': variable_name,
            'data_flow': [],
            'note': 'Full data flow analysis requires additional infrastructure'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_dependencies(file_path: str, tool_context: ToolContext) -> dict:
    """Identify dependency relationships."""
    try:
        from .navigation_tools import get_imports
        imports_result = get_imports(file_path, tool_context)
        
        if imports_result.get('status') != 'ok':
            return imports_result
        
        dependencies = []
        for imp in imports_result['imports']:
            module = imp['module']
            # Determine if external or internal
            dep_type = 'external' if '.' in module or module in ['os', 'sys', 'json', 're', 'pathlib'] else 'internal'
            dependencies.append({
                'module': module,
                'type': dep_type
            })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'dependencies': dependencies
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_code_complexity(file_path: str, tool_context: ToolContext) -> dict:
    """Calculate complexity metrics."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        content = path.read_text(encoding='utf-8')
        lines = content.splitlines()
        lines_of_code = len([line for line in lines if line.strip()])
        
        cyclomatic = 1
        cognitive = 0
        
        if _is_python_file(file_path):
            tree = _parse_python_ast(file_path)
            if tree:
                for node in ast.walk(tree):
                    # Cyclomatic complexity: count decision points
                    if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                        cyclomatic += 1
                    elif isinstance(node, ast.BoolOp):
                        cyclomatic += len(node.values) - 1
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'complexity': {
                'cyclomatic': cyclomatic,
                'cognitive': cognitive,
                'lines_of_code': lines_of_code
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_repo_complexity(tool_context: ToolContext) -> dict:
    """Calculate complexity ranking across the repository."""
    try:
        from .. import codegraph
        
        graph = codegraph.load_current_graph()
        
        complexities = []
        for node_id, node in graph._nodes.items():
            if node.get('level') == 'function':
                file_path = node.get('file', '')
                complexity_result = analyze_code_complexity(file_path, tool_context)
                if complexity_result.get('status') == 'ok':
                    complexities.append({
                        'id': node_id,
                        'name': node.get('name'),
                        'cyclomatic': complexity_result['complexity']['cyclomatic'],
                        'lines_of_code': complexity_result['complexity']['lines_of_code']
                    })
        
        # Sort by cyclomatic complexity
        complexities.sort(key=lambda x: x['cyclomatic'], reverse=True)
        
        return {
            'status': 'ok',
            'complexities': complexities[:50],  # Top 50 most complex
            'total_functions': len(complexities)
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


@safe
def detect_code_duplication(tool_context: ToolContext, directory: Optional[str] = None) -> dict:
    """Identify duplicate or similar code (repeated lines) inside one repository."""
    try:
        from pathlib import Path
        from ._common import repo_root
        root = Path(directory).resolve() if directory else repo_root()
        skip = {'__pycache__', 'node_modules', 'venv', '.venv', 'target', 'dist', 'build'}
        code_blocks = {}
        duplicates = []
        for file_path in sorted(root.rglob('*.py')):
            parts = file_path.relative_to(root).parts
            if any(p.startswith('.') or p in skip for p in parts):
                continue
            rel = str(Path(*parts))
            for i, line in enumerate(file_path.read_text(errors='replace').splitlines()):
                key = line.strip()
                if len(key) <= 10:      # ignore short lines
                    continue
                code_blocks.setdefault(key, []).append({'file': rel, 'line': i + 1})
                if len(code_blocks[key]) == 3:
                    duplicates.append({'code': key[:100], 'occurrences': code_blocks[key]})
        for d in duplicates:
            d['count'] = len(d['occurrences'])
        return {
            'status': 'ok',
            'duplicates': duplicates[:20],  # limit to 20
            'note': 'Simple line-based detection - advanced detection requires diff algorithms'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def detect_dead_code(file_path: str, tool_context: ToolContext) -> dict:
    """Find potentially unused code."""
    try:
        from .navigation_tools import get_symbol_references
        from .analysis_tools import extract_symbols
        
        symbols_result = extract_symbols(file_path, tool_context)
        if symbols_result.get('status') != 'ok':
            return symbols_result
        
        dead_code = []
        
        for symbol in symbols_result['symbols']:
            if symbol['type'] in ['function', 'class']:
                # Check if symbol has references
                ref_result = get_symbol_references(symbol['name'], tool_context)
                if ref_result.get('status') == 'ok' and len(ref_result['references']) == 0:
                    dead_code.append({
                        'symbol': symbol['name'],
                        'line': symbol['line'],
                        'reason': 'no references'
                    })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'dead_code': dead_code
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_exceptions(file_path: str, tool_context: ToolContext) -> dict:
    """Identify exception paths and propagation."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        exception_paths = []
        
        if _is_python_file(file_path):
            tree = _parse_python_ast(file_path)
            if tree:
                for node in ast.walk(tree):
                    if isinstance(node, ast.Raise):
                        exc_name = 'unknown'
                        if node.exc:
                            if isinstance(node.exc, ast.Name):
                                exc_name = node.exc.id
                            elif isinstance(node.exc, ast.Call):
                                if isinstance(node.exc.func, ast.Name):
                                    exc_name = node.exc.func.id
                        
                        # Check if handled
                        handled = False
                        for parent in ast.walk(tree):
                            if isinstance(parent, ast.ExceptHandler):
                                if parent.type:
                                    if isinstance(parent.type, ast.Name) and parent.type.id == exc_name:
                                        handled = True
                                    elif isinstance(parent.type, ast.Attribute) and parent.type.attr == exc_name:
                                        handled = True
                        
                        exception_paths.append({
                            'line': node.lineno,
                            'exception': exc_name,
                            'handled': handled
                        })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'exception_paths': exception_paths
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_annotations(file_path: str, tool_context: ToolContext) -> dict:
    """Inspect decorators, attributes and annotations."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        annotations = []
        
        if _is_python_file(file_path):
            tree = _parse_python_ast(file_path)
            if tree:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        for decorator in node.decorator_list:
                            decorator_name = ast.unparse(decorator) if hasattr(ast, 'unparse') else str(decorator)
                            annotations.append({
                                'symbol': node.name,
                                'decorator': f'@{decorator_name}',
                                'line': node.lineno
                            })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'annotations': annotations
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_macros(file_path: str, tool_context: ToolContext) -> dict:
    """Inspect macro usage where supported."""
    try:
        # Python doesn't have traditional macros
        # This is for languages like C, Rust, Lisp
        return {
            'status': 'ok',
            'file_path': file_path,
            'macros': [],
            'note': 'Macro analysis not applicable for Python'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def analyze_generated_code(file_path: str, tool_context: ToolContext) -> dict:
    """Connect generated code to its source or generator."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        # Check for common generated code patterns
        content = path.read_text(encoding='utf-8')
        
        generator = None
        source = None
        
        # Check for common generated code markers
        if 'DO NOT EDIT' in content or 'Auto-generated' in content:
            generator = 'auto-detected'
        
        # Check for specific generators
        if 'protobuf' in content.lower() or 'proto' in content:
            generator = 'protoc'
        elif 'swagger' in content.lower():
            generator = 'swagger-codegen'
        elif 'graphql' in content.lower():
            generator = 'graphql-codegen'
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'generator': generator,
            'source': source,
            'is_generated': generator is not None
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
