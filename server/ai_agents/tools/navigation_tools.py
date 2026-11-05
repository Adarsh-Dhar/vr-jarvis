"""
Code Navigation Tools - Shared Superpowers (Part B)
These tools allow agents to navigate and understand code structure.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import re
import ast
import subprocess
import json
from google.adk.tools import ToolContext
from ._safe import safe
from ._common import repo_root, resolve_in_repo


# Graph index resolver - single source of truth for symbol resolution
def _load_graph_index():
    """Load the graph index from GRAPH_PATH."""
    try:
        from .. import config
        if config.GRAPH_PATH.exists():
            with open(config.GRAPH_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {'nodes': [], 'edges': []}


def resolve_symbol(symbol_id: str) -> Optional[Dict]:
    """
    Resolve a symbol ID from the graph index.
    
    Args:
        symbol_id: The symbol ID to resolve (e.g., "file.module.function")
    
    Returns:
        Dict with node data if found, None otherwise
    """
    graph = _load_graph_index()
    for node in graph.get('nodes', []):
        if node.get('id') == symbol_id:
            return node
    return None


def resolve_symbol_by_name(symbol_name: str) -> List[Dict]:
    """
    Resolve all symbols with a given name from the graph index.
    
    Args:
        symbol_name: The symbol name to resolve (e.g., "create_order")
    
    Returns:
        List of node dicts matching the name
    """
    graph = _load_graph_index()
    return [node for node in graph.get('nodes', []) if node.get('name') == symbol_name]


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


def _find_symbol_in_python(symbol_name: str, file_path: str) -> Optional[Dict]:
    """Find symbol definition in Python file using AST."""
    tree = _parse_python_ast(file_path)
    if not tree:
        return None
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == symbol_name:
            return {
                'file': file_path,
                'line': node.lineno,
                'column': node.col_offset,
                'symbol_type': 'function'
            }
        elif isinstance(node, ast.ClassDef) and node.name == symbol_name:
            return {
                'file': file_path,
                'line': node.lineno,
                'column': node.col_offset,
                'symbol_type': 'class'
            }
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == symbol_name:
            return {
                'file': file_path,
                'line': node.lineno,
                'column': node.col_offset,
                'symbol_type': 'variable'
            }
    return None


def _python_call_sites(symbol_name: str, root: Path) -> List[Dict]:
    """Every call to `symbol_name` (f(), obj.f()) in Python files under root, with the caller."""
    skip = {'__pycache__', 'node_modules', 'venv', '.venv'}
    sites = []
    for py in sorted(root.rglob('*.py')):
        if any(p.startswith('.') or p in skip for p in py.relative_to(root).parts):
            continue
        tree = _parse_python_ast(str(py))
        if not tree:
            continue
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if name != symbol_name:
                continue
            inner = None
            for fn in funcs:
                if fn.lineno <= node.lineno <= fn.end_lineno and (inner is None or fn.lineno >= inner.lineno):
                    inner = fn
            sites.append({'file': str(py), 'line': node.lineno, 'caller': inner.name if inner else '<module>'})
    sites.sort(key=lambda x: (x['file'], x['line']))
    return sites


@safe
def get_symbol_definition(symbol_name: str, tool_context: ToolContext) -> dict:
    """Find where a symbol is defined."""
    try:
        cwd = repo_root()
        
        # First try to find in Python files using AST
        for py_file in cwd.rglob('*.py'):
            result = _find_symbol_in_python(symbol_name, str(py_file))
            if result:
                return {
                    'status': 'ok',
                    'symbol_name': symbol_name,
                    'definition': result
                }
        
        # Fallback to grep for other languages
        patterns = [
            f'def {symbol_name}\\(',  # Python function
            f'class {symbol_name}:',  # Python class
            f'function {symbol_name}\\(',  # JavaScript function
            f'const {symbol_name}\\s*=',  # JavaScript const
            f'let {symbol_name}\\s*=',  # JavaScript let
            f'var {symbol_name}\\s*=',  # JavaScript var
        ]
        
        for pattern in patterns:
            result = subprocess.run(
                ['grep', '-rn', pattern, str(cwd)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines()[:1]:  # Take first match
                    parts = line.split(':', 2)
                    if len(parts) >= 2:
                        return {
                            'status': 'ok',
                            'symbol_name': symbol_name,
                            'definition': {
                                'file': parts[0],
                                'line': int(parts[1]),
                                'column': 0,
                                'symbol_type': 'unknown'
                            }
                        }
        
        return {
            'status': 'not_found',
            'symbol_name': symbol_name,
            'message': f'Symbol definition not found: {symbol_name}'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_symbol_references(symbol_name: str, tool_context: ToolContext) -> dict:
    """Find every reference to a symbol."""
    try:
        cwd = repo_root()
        references = []
        
        # Use grep to find all references
        result = subprocess.run(
            ['grep', '-rn', '--include=*.py', '--include=*.js', '--include=*.ts', symbol_name, str(cwd)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.split(':', 2)
                if len(parts) >= 2:
                    file_path = parts[0]
                    line_num = int(parts[1])
                    snippet = parts[2] if len(parts) > 2 else ''
                    
                    # Determine reference type
                    ref_type = 'unknown'
                    if 'import' in snippet or 'from' in snippet:
                        ref_type = 'import'
                    elif '(' in snippet or symbol_name + '(' in snippet:
                        ref_type = 'call'
                    elif '=' in snippet:
                        ref_type = 'assignment'
                    
                    references.append({
                        'file': file_path,
                        'line': line_num,
                        'type': ref_type
                    })
        
        return {
            'status': 'ok',
            'symbol_name': symbol_name,
            'references': references
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_symbol_hover_info(symbol_name: str, tool_context: ToolContext) -> dict:
    """Retrieve types, documentation and signatures."""
    try:
        # First try to find definition
        def_result = get_symbol_definition(symbol_name, tool_context)
        
        if def_result.get('status') != 'ok':
            return {
                'status': 'not_found',
                'symbol_name': symbol_name,
                'message': 'Symbol definition not found'
            }
        
        definition = def_result['definition']
        file_path = definition['file']
        line_num = definition['line']
        
        # Read the file to get signature and docstring
        path = Path(file_path)
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        lines = path.read_text(encoding='utf-8').splitlines()
        
        # Get the line with the definition
        if 0 < line_num <= len(lines):
            signature_line = lines[line_num - 1]
            
            # Try to get docstring (next non-empty line after definition)
            docstring = ''
            for i in range(line_num, min(line_num + 5, len(lines))):
                line = lines[i].strip()
                if line.startswith('"""') or line.startswith("'''"):
                    docstring = line.strip('"""').strip("'''")
                    break
                elif line and not line.startswith('#'):
                    break
            
            return {
                'status': 'ok',
                'symbol_name': symbol_name,
                'type': definition.get('symbol_type', 'unknown'),
                'documentation': docstring,
                'signature': signature_line.strip()
            }
        
        return {
            'status': 'error',
            'error': 'Could not read symbol information'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_call_hierarchy(
    symbol_name: str,
    tool_context: ToolContext,
    direction: str = 'both'
) -> dict:
    """Retrieve incoming and outgoing calls using the graph index."""
    try:
        # Try to resolve by ID first
        node = resolve_symbol(symbol_name)
        
        # If not found by ID, try by name
        if not node:
            nodes = resolve_symbol_by_name(symbol_name)
            if nodes:
                node = nodes[0]  # Use first match
            else:
                return {
                    'status': 'not_found',
                    'symbol_name': symbol_name,
                    'message': 'Symbol not found in graph index'
                }
        
        symbol_id = node.get('id')
        graph = _load_graph_index()
        
        incoming_calls = []
        outgoing_calls = []
        
        if direction in ['both', 'incoming']:
            # Find edges where this node is the destination (only call edges)
            for edge in graph.get('edges', []):
                if edge.get('dst') == symbol_id and edge.get('type') == 'calls':
                    src_node = resolve_symbol(edge.get('src'))
                    incoming_calls.append({
                        'from': edge.get('src'),
                        'file': src_node.get('file') if src_node else edge.get('file'),
                        'line': edge.get('line'),
                        'kind': edge.get('kind')
                    })
        
        if direction in ['both', 'outgoing']:
            # Find edges where this node is the source (only call edges)
            for edge in graph.get('edges', []):
                if edge.get('src') == symbol_id and edge.get('type') == 'calls':
                    dst_node = resolve_symbol(edge.get('dst'))
                    outgoing_calls.append({
                        'to': edge.get('dst'),
                        'file': dst_node.get('file') if dst_node else edge.get('file'),
                        'line': edge.get('line'),
                        'kind': edge.get('kind')
                    })
        
        return {
            'status': 'ok',
            'symbol_name': symbol_name,
            'symbol_id': symbol_id,
            'incoming_calls': incoming_calls,
            'outgoing_calls': outgoing_calls
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_type_hierarchy(symbol_name: str, tool_context: ToolContext) -> dict:
    """Retrieve inheritance and implementation relationships."""
    try:
        # Find the class definition
        def_result = get_symbol_definition(symbol_name, tool_context)
        if def_result.get('status') != 'ok':
            return {
                'status': 'not_found',
                'symbol_name': symbol_name,
                'message': 'Symbol definition not found'
            }
        
        definition = def_result['definition']
        if definition.get('symbol_type') != 'class':
            return {
                'status': 'not_applicable',
                'symbol_name': symbol_name,
                'message': 'Symbol is not a class'
            }
        
        file_path = definition['file']
        
        if _is_python_file(file_path):
            tree = _parse_python_ast(file_path)
            if tree:
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == symbol_name:
                        # Get base classes
                        superclasses = [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases]
                        
                        # Find subclasses (classes that inherit from this class)
                        subclasses = []
                        for child in ast.walk(tree):
                            if isinstance(child, ast.ClassDef) and child.name != symbol_name:
                                for base in child.bases:
                                    if isinstance(base, ast.Name) and base.id == symbol_name:
                                        subclasses.append(child.name)
                        
                        return {
                            'status': 'ok',
                            'symbol_name': symbol_name,
                            'superclasses': superclasses,
                            'subclasses': subclasses,
                            'implements': []
                        }
        
        return {
            'status': 'ok',
            'symbol_name': symbol_name,
            'superclasses': [],
            'subclasses': [],
            'implements': [],
            'note': 'Type hierarchy analysis requires AST parsing for Python'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_imports(file_path: str, tool_context: ToolContext) -> dict:
    """Identify imported modules and symbols."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        imports = []
        
        if _is_python_file(file_path):
            tree = _parse_python_ast(file_path)
            if tree:
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append({
                                'module': alias.name,
                                'symbols': [alias.asname] if alias.asname else None
                            })
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ''
                        symbols = [alias.name for alias in node.names]
                        imports.append({
                            'module': module,
                            'symbols': symbols
                        })
        else:
            # Fallback to regex for other languages
            content = path.read_text(encoding='utf-8')
            
            # Match various import patterns
            patterns = [
                r'import\s+([^\n;]+)',  # Python import
                r'from\s+(\S+)\s+import',  # Python from import
                r'require\([\'"]([^\'"]+)[\'"]\)',  # JavaScript require
                r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',  # JavaScript ES6 import
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    imports.append({
                        'module': match,
                        'symbols': None
                    })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'imports': imports
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_exports(file_path: str, tool_context: ToolContext) -> dict:
    """Identify exported symbols."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        exports = []
        
        if _is_python_file(file_path):
            tree = _parse_python_ast(file_path)
            if tree:
                for node in ast.walk(tree):
                    # Top-level functions and classes are exported
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        if node.col_offset == 0:  # Top-level
                            exports.append({
                                'name': node.name,
                                'type': 'class' if isinstance(node, ast.ClassDef) else 'function'
                            })
        else:
            # For JavaScript/TypeScript, look for export statements
            content = path.read_text(encoding='utf-8')
            
            # Match export patterns
            patterns = [
                r'export\s+(?:default\s+)?(?:function|class|const|let|var)\s+(\w+)',
                r'export\s*\{\s*([^}]+)\s*\}',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    exports.append({
                        'name': match.strip(),
                        'type': 'unknown'
                    })
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'exports': exports
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_scope_information(
    file_path: str,
    line: int,
    tool_context: ToolContext
) -> dict:
    """Understand local and enclosing scopes."""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_in_repo(path)
        
        if not path.exists():
            return {
                'status': 'error',
                'error': f'File not found: {file_path}'
            }
        
        if not _is_python_file(file_path):
            return {
                'status': 'not_applicable',
                'file_path': file_path,
                'message': 'Scope analysis only implemented for Python'
            }
        
        tree = _parse_python_ast(file_path)
        if not tree:
            return {
                'status': 'error',
                'error': 'Could not parse file'
            }
        
        # Find the scope at the given line
        local_variables = []
        enclosing_scopes = []
        
        for node in ast.walk(tree):
            if hasattr(node, 'lineno') and node.lineno <= line:
                if isinstance(node, ast.FunctionDef):
                    enclosing_scopes.append(f'function:{node.name}')
                    # Get local variables
                    for arg in node.args.args:
                        local_variables.append(arg.arg)
                elif isinstance(node, ast.ClassDef):
                    enclosing_scopes.append(f'class:{node.name}')
                elif isinstance(node, ast.Module):
                    enclosing_scopes.append('module')
        
        return {
            'status': 'ok',
            'file_path': file_path,
            'line': line,
            'local_variables': list(set(local_variables)),
            'enclosing_scopes': enclosing_scopes
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_symbol_documentation(symbol_name: str, tool_context: ToolContext) -> dict:
    """Retrieve associated documentation."""
    try:
        # Get hover info which includes docstring
        hover_result = get_symbol_hover_info(symbol_name, tool_context)
        
        if hover_result.get('status') == 'ok':
            return {
                'status': 'ok',
                'symbol_name': symbol_name,
                'documentation': hover_result.get('documentation', ''),
                'signature': hover_result.get('signature', '')
            }
        
        return hover_result
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def find_implementations(symbol_name: str, tool_context: ToolContext) -> dict:
    """Find implementations of interfaces, traits and abstract methods."""
    try:
        # For Python, look for classes that implement methods matching the symbol
        cwd = repo_root()
        implementations = []
        
        for py_file in cwd.rglob('*.py'):
            tree = _parse_python_ast(str(py_file))
            if tree:
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if this class has a method matching the symbol
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and item.name == symbol_name:
                                implementations.append({
                                    'file': str(py_file),
                                    'line': item.lineno,
                                    'class': node.name
                                })
                                break
        
        return {
            'status': 'ok',
            'symbol_name': symbol_name,
            'implementations': implementations
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
