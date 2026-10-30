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
            path = Path.cwd() / path
        
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
            path = Path.cwd() / path
        
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
            path = Path.cwd() / path
        
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
            path = Path.cwd() / path
        
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
    """Generate control-flow information."""
    try:
        # Find the function definition
        from .navigation_tools import get_symbol_definition
        def_result = get_symbol_definition(function_name, tool_context)
        
        if def_result.get('status') != 'ok':
            return {
                'status': 'not_found',
                'function_name': function_name,
                'message': 'Function definition not found'
            }
        
        file_path = def_result['definition']['file']
        
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
        
        branches = []
        loops = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                for child in ast.walk(node):
                    if isinstance(child, ast.If):
                        branches.append({
                            'condition': 'if statement',
                            'line': child.lineno
                        })
                    elif isinstance(child, (ast.For, ast.While)):
                        loops.append({
                            'type': 'for' if isinstance(child, ast.For) else 'while',
                            'line': child.lineno
                        })
                break
        
        return {
            'status': 'ok',
            'function_name': function_name,
            'control_flow': {
                'branches': branches,
                'loops': loops
            }
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
            path = Path.cwd() / path
        
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
def detect_code_duplication(tool_context: ToolContext) -> dict:
    """Identify duplicate or similar code."""
    try:
        from .repository_tools import list_files, read_file
        from pathlib import Path
        
        # Get all Python files
        files_result = list_files(tool_context, directory='.', pattern='.py', recursive=True)
        if files_result.get('status') != 'ok':
            return files_result
        
        # Simple duplicate detection based on line similarity
        code_blocks = {}
        duplicates = []
        
        for file_info in files_result['files']:
            if file_info['type'] == 'file':
                file_path = file_info['path']
                file_result = read_file(file_path, tool_context)
                
                if file_result.get('status') == 'ok':
                    content = file_result['content']
                    lines = content.splitlines()
                    
                    # Look for repeated line patterns
                    for i, line in enumerate(lines):
                        if len(line.strip()) > 10:  # Ignore short lines
                            if line.strip() in code_blocks:
                                code_blocks[line.strip()].append({
                                    'file': file_path,
                                    'line': i + 1
                                })
                                if len(code_blocks[line.strip()]) >= 3:
                                    duplicates.append({
                                        'code': line.strip()[:100],
                                        'occurrences': code_blocks[line.strip()],
                                        'count': len(code_blocks[line.strip()])
                                    })
                            else:
                                code_blocks[line.strip()] = [{
                                    'file': file_path,
                                    'line': i + 1
                                }]
        
        return {
            'status': 'ok',
            'duplicates': duplicates[:20],  # Limit to 20
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
            path = Path.cwd() / path
        
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
            path = Path.cwd() / path
        
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
            path = Path.cwd() / path
        
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
