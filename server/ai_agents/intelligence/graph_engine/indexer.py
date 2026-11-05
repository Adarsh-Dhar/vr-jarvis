"""Graph indexing - builds the call graph from source files."""
import ast
import json
import re
import subprocess
from pathlib import Path

from ... import config
from ..parsers.tree_sitter_parser import extract_symbols_with_tree_sitter, extract_calls_with_tree_sitter
from ..resolvers.registry import get_resolver
from ..resolvers.bindings import Binding
from .store import _source_files, SKIP_DIRS, EXTS, MAX_FN_LINES

# Regex patterns for fallback parsing
_FN = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)')
_ARROW = re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s+)?'
                    r'(?:function\b|\([^)]*\)\s*(?::[^=]+)?=>|[A-Za-z_$][\w$]*\s*=>)')
_CLASS = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)')
_CALL = re.compile(r'\b([A-Za-z_$][\w$]*)\s*\(')
_METHOD_CALL = re.compile(r'\b(?:self|this|[A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\s*\(')
_CONSTRUCTOR = re.compile(r'\bnew\s+([A-Za-z_$][\w$]*)\s*\(')
_IMPORT = re.compile(r'''(?:from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)|^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+)))''', re.M)


def _is_test(rel):
    """Check if a file is a test file."""
    name = rel.rsplit('/', 1)[-1]
    return ('.test.' in name or '.spec.' in name or name.startswith('test_') or name.endswith('_test.py')
            or rel.startswith(('tests/', 'test/', '__tests__/')) or '/__tests__/' in rel or '/tests/' in rel)


def _dotted(rel):
    """Convert path to dotted notation."""
    return re.sub(r'\.[^./]+$', '', rel).replace('/', '.')


def _cluster(rel):
    """Extract cluster name from path."""
    parts = rel.split('/')
    return parts[0] if len(parts) > 1 else 'root'


def _compute_layer(rel, texts):
    """
    Compute the architectural layer for a file based on:
    - Folder names
    - Framework hints (route decorators, Express router)
    - Import direction (files that import many but are imported by few are higher)
    """
    rel_lower = rel.lower()

    # Folder-based heuristics
    if any(p in rel_lower for p in ['api', 'route', 'controller', 'handler', 'endpoint']):
        return 'api'
    if any(p in rel_lower for p in ['service', 'business', 'logic', 'domain']):
        return 'service'
    if any(p in rel_lower for p in ['repository', 'repo', 'dao', 'database', 'db', 'model', 'entity']):
        return 'database'
    if any(p in rel_lower for p in ['auth', 'security', 'middleware']):
        return 'auth'
    if any(p in rel_lower for p in ['util', 'helper', 'common', 'shared']):
        return 'shared'

    # Framework hints (check file content)
    if rel in texts:
        text = texts[rel].lower()
        if '@app.route' in text or '@router' in text or 'express.router' in text:
            return 'api'
        if 'class ' in text and 'repository' in text or 'dao' in text:
            return 'database'

    # Import direction heuristic (would need full graph, skip for now)
    # Fallback: use top-level package as layer
    parts = rel.split('/')
    return parts[0] if len(parts) > 1 else 'other'


def _js_end(lines, start):
    """Find end line of a JavaScript function."""
    depth, seen = 0, False
    for i in range(start, min(len(lines), start + MAX_FN_LINES)):
        for ch in re.sub(r'(["\'`])(?:\\.|(?!\1).)*\1', '', lines[i]):
            if ch == '{':
                depth += 1; seen = True
            elif ch == '}':
                depth -= 1
        if seen and depth <= 0:
            return i + 1
        if not seen and i > start and lines[i].rstrip().endswith(';'):
            return i + 1
    return start + 1 if not seen else min(len(lines), start + MAX_FN_LINES)


def _symbols(rel, text):
    """Yield (name, kind, start_line, end_line) 1-based."""
    lines = text.splitlines()
    if rel.endswith('.py'):
        # Use tree-sitter for Python
        try:
            symbols = extract_symbols_with_tree_sitter(rel, text)
            for sym in symbols:
                yield sym['name'], sym['kind'], sym['start'], sym['end']
        except Exception:
            # Fallback to AST
            try:
                tree = ast.parse(text)
            except SyntaxError:
                return
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield node.name, 'function', node.lineno, node.end_lineno
                elif isinstance(node, ast.ClassDef):
                    yield node.name, 'object', node.lineno, node.end_lineno
                    for m in node.body:
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            yield node.name + '.' + m.name, 'function', m.lineno, m.end_lineno
        return
    
    # Use tree-sitter for JavaScript/TypeScript
    try:
        symbols = extract_symbols_with_tree_sitter(rel, text)
        for sym in symbols:
            yield sym['name'], sym['kind'], sym['start'], sym['end']
    except Exception:
        # Fallback to regex
        for i, line in enumerate(lines):
            if line.startswith((' ', '\t')) and not line.lstrip().startswith(('export', 'function', 'async', 'const', 'class')):
                continue
            for rx, kind in ((_FN, 'function'), (_ARROW, 'function'), (_CLASS, 'object')):
                m = rx.match(line)
                if m:
                    yield m.group(1), kind, i + 1, _js_end(lines, i)
                    break


def _imports(text):
    """Extract import statements from text."""
    out = set()
    for m in _IMPORT.finditer(text):
        spec = next((g for g in m.groups() if g), '')
        if spec:
            out.add(spec.replace('\\', '/').rstrip('/').rsplit('/', 1)[-1].rsplit('.', 1)[-1] if '/' in spec else spec.rsplit('.', 1)[-1])
    return out


def index_repo(name):
    """Build {nodes, edges, tests, coverage} for repository/<name>. Pure function of the files on disk."""
    repo = config.REPOSITORY_DIR / name
    nodes, texts, tests = [], {}, []

    # Get git revision for metadata
    revision = ''
    try:
        revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, capture_output=True,
                                text=True, timeout=3).stdout.strip()
    except Exception:
        # Fallback: hash of file sizes and mtimes
        import time
        file_hashes = []
        for path, rel in _source_files(repo):
            stat = path.stat()
            file_hashes.append(f"{rel}:{stat.st_size}:{stat.st_mtime}")
        revision = str(hash(tuple(sorted(file_hashes))))

    # First pass: collect all files and build module/file nodes
    module_nodes = {}
    file_nodes = {}
    symbol_nodes = []

    for path, rel in _source_files(repo):
        try:
            text = path.read_text(errors='replace')
        except OSError:
            continue
        texts[rel] = text
        if _is_test(rel):
            tests.append({'id': 'test.' + _dotted(rel), 'file': rel, 'covers': []})
            continue

        # Create file node
        file_id = f'file::{rel}'
        file_parts = rel.split('/')
        module_name = file_parts[0] if len(file_parts) > 1 else 'root'

        file_nodes[file_id] = {
            'id': file_id,
            'name': rel.rsplit('/', 1)[-1],
            'kind': 'file',
            'file': rel,
            'start': 1,
            'end': text.count('\n') + 1,
            'cluster': _cluster(rel),
            'loc': text.count('\n') + 1,
            'level': 'file',
            'parent': f'module::{module_name}'
        }

        # Create module node if not exists
        if module_name not in module_nodes:
            module_nodes[f'module::{module_name}'] = {
                'id': f'module::{module_name}',
                'name': module_name,
                'kind': 'module',
                'file': module_name,
                'start': 0,
                'end': 0,
                'cluster': module_name,
                'loc': 0,
                'level': 'module',
                'parent': None
            }

        # Extract symbols
        lines = text.splitlines()
        for sym, kind, start, end in _symbols(rel, text):
            # Determine layer based on folder names, framework hints, and import direction
            layer = _compute_layer(rel, texts)

            # Build node with new ID format: <rel_path>::<Class.>name
            # Example: shop/payments.py::CardPayment.process
            qualname = sym
            class_name = ''
            if '.' in sym:
                parts = sym.split('.')
                class_name = parts[0]
            
            node_id = f'{rel}::{sym}'
            legacy_id = _dotted(rel) + '.' + sym  # Old dotted format for backward compatibility
            
            symbol_nodes.append({
                'id': node_id,
                'legacy_id': legacy_id,
                'qualname': qualname,
                'module': module_name,
                'class_name': class_name,
                'name': sym.split('.')[-1],
                'kind': kind,
                'file': rel,
                'start': start,
                'end': end,
                'cluster': _cluster(rel),
                'loc': max(end - start + 1, 1),
                'level': 'function' if kind != 'object' else 'class',
                'layer': layer,
                'parent': file_id,
                'language': 'python' if rel.endswith('.py') else 'typescript'
            })

    # Combine all nodes
    nodes = list(module_nodes.values()) + list(file_nodes.values()) + symbol_nodes

    by_name = {}
    for n in nodes:
        by_name.setdefault(n['name'], []).append(n)
    edges, seen = [], set()

    # Add contains edges for hierarchy (module -> file -> class/function)
    for n in nodes:
        parent_id = n.get('parent')
        if parent_id and parent_id in module_nodes or parent_id in file_nodes:
            edges.append({
                'src': parent_id,
                'dst': n['id'],
                'type': 'contains',
                'kind': 'confirmed'
            })

    # Add aggregated imports edges at file level
    file_imports = {}
    for file_id, file_node in file_nodes.items():
        file_path = file_node['file']
        imports = _imports(texts.get(file_path, ''))
        file_imports[file_id] = imports

        for imp in imports:
            # Find target file
            for target_file_id, target_file_node in file_nodes.items():
                target_file = target_file_node['file']
                if imp in target_file or imp in target_file.rsplit('/', 1)[-1]:
                    if file_id != target_file_id:
                        edges.append({
                            'src': file_id,
                            'dst': target_file_id,
                            'type': 'imports',
                            'kind': 'confirmed',
                            'file': file_path,
                            'line': 1
                        })
                    break

    # Add aggregated imports edges at module level (with count)
    module_imports = {}
    for edge in edges:
        if edge['type'] == 'imports':
            src = edge['src']
            dst = edge['dst']
            if src.startswith('module.') and dst.startswith('module.'):
                key = (src, dst)
                module_imports[key] = module_imports.get(key, 0) + 1

    for (src, dst), count in module_imports.items():
        edges.append({
            'src': src,
            'dst': dst,
            'type': 'imports',
            'kind': 'confirmed',
            'count': count
        })
    
    # Add call edges with improved resolution using resolver
    # Only process symbol nodes (functions/classes), not module/file nodes
    
    # Build file contexts for resolver
    file_contexts = {}
    for n in symbol_nodes:
        if n['kind'] == 'object':
            continue
        file_path = n.get('file', '')
        if not file_path:
            continue
        
        # Build context once per file
        if file_path not in file_contexts:
            language = n.get('language', 'python')
            resolver = get_resolver(language)
            if resolver:
                file_contexts[file_path] = resolver.build_context(file_path, texts.get(file_path, ''), nodes)
            else:
                file_contexts[file_path] = None
    
    for n in symbol_nodes:
        if n['kind'] == 'object':
            continue
        file_path = n.get('file', '')
        if not file_path:
            continue

        # Use tree-sitter to extract calls from the entire file
        try:
            calls = extract_calls_with_tree_sitter(file_path, texts.get(file_path, ''))
        except Exception:
            # Fallback to regex
            calls = []
            lines = texts.get(file_path, '').splitlines()
            for offset, line in enumerate(lines):
                for callee in _CALL.findall(line):
                    calls.append({
                        'name': callee,
                        'line': offset + 1,
                        'type': 'direct'
                    })

        # Filter calls to only those within this function's line range
        function_calls = [c for c in calls if n['start'] <= c['line'] <= n['end']]

        # Get file context
        file_ctx = file_contexts.get(file_path)
        language = n.get('language', 'python')
        resolver = get_resolver(language)
        
        # Build graph context for resolver
        graph_ctx = {
            'nodes': nodes,
            'edges': edges
        }

        # Resolve each call using the resolver
        for call in function_calls:
            callee = call['name']
            call_type = call.get('call_type', 'direct')
            line_idx = call['line'] - 1  # Convert to 0-based
            
            # Use resolver if available
            if resolver and file_ctx:
                result = resolver.resolve(call, file_ctx, graph_ctx)
                
                # Map resolution status to edge kind
                status_to_kind = {
                    'static_resolved': 'confirmed',
                    'polymorphic': 'ambiguous',
                    'ambiguous': 'ambiguous',
                    'unresolved': 'unresolved',
                    'external': 'unresolved'
                }
                kind = status_to_kind.get(result.status, 'unresolved')
                
                # Add edges based on resolution result
                if result.status == 'static_resolved' and result.targets:
                    for target_id in result.targets:
                        if target_id in [node['id'] for node in nodes] and (n['id'], target_id) not in seen:
                            seen.add((n['id'], target_id))
                            edges.append({
                                'src': n['id'],
                                'dst': target_id,
                                'type': 'calls',
                                'kind': kind,
                                'file': n['file'],
                                'line': line_idx + 1,
                                'call_type': call_type,
                                'resolution': result.status,
                                'reason': result.reason
                            })
                elif result.status == 'polymorphic' and result.targets:
                    # Add edge to primary target with polymorphic status
                    target_id = result.targets[0]
                    if target_id in [node['id'] for node in nodes] and (n['id'], target_id) not in seen:
                        seen.add((n['id'], target_id))
                        edges.append({
                            'src': n['id'],
                            'dst': target_id,
                            'type': 'calls',
                            'kind': kind,
                            'file': n['file'],
                            'line': line_idx + 1,
                            'call_type': call_type,
                            'resolution': result.status,
                            'reason': result.reason,
                            'candidates': result.candidates
                        })
                elif result.status == 'ambiguous' and result.candidates:
                    # If there's an explicit binding in the binding table, use only that target
                    binding = None
                    if file_ctx:
                        from ..resolvers.bindings import BindingTable
                        table = BindingTable(file_ctx.file_path)
                        # Rebuild binding table for this check
                        module_symbols = {}
                        for node in nodes:
                            if node.get('file'):
                                file_path = node['file']
                                if '/' in file_path:
                                    module = file_path.rsplit('/', 1)[0]
                                else:
                                    module = file_path.rsplit('.', 1)[0] if '.' in file_path else file_path
                                if module not in module_symbols:
                                    module_symbols[module] = set()
                                module_symbols[module].add(node['name'])
                        
                        explicit_imports = set()
                        for imp in file_ctx.imports:
                            module = imp.get('module', '')
                            name = imp.get('name')
                            alias = imp.get('alias')
                            kind = imp.get('kind', 'import')
                            
                            if kind == 'from' and name:
                                binding_name = alias or name
                                module_file = None
                                for node in nodes:
                                    if node.get('file'):
                                        file_stem = node['file'].rsplit('.', 1)[0] if '.' in node['file'] else node['file']
                                        if file_stem == module or node['file'] == module:
                                            module_file = node['file']
                                            break
                                
                                if module_file:
                                    symbol_id = f"{module_file}::{name}"
                                else:
                                    symbol_id = f"{module.replace('.', '/')}::{name}" if '.' in module else f"{module}::{name}"
                                table.add_binding(Binding(binding_name, symbol_id, 'alias' if alias else 'import', imp.get('line', 0)))
                                explicit_imports.add(binding_name)
                        
                        binding = table.resolve_name(callee)
                    
                    if binding and binding.kind in ['import', 'alias']:
                        # Use the explicitly bound target
                        if binding.symbol_id in [node['id'] for node in nodes] and (n['id'], binding.symbol_id) not in seen:
                            seen.add((n['id'], binding.symbol_id))
                            edges.append({
                                'src': n['id'],
                                'dst': binding.symbol_id,
                                'type': 'calls',
                                'kind': 'confirmed',
                                'file': n['file'],
                                'line': line_idx + 1,
                                'call_type': call_type,
                                'resolution': 'static_resolved',
                                'reason': f'Explicit binding overrides ambiguity: {binding.kind}'
                            })
                    else:
                        # No explicit binding - add edges to all candidates
                        for candidate_id in result.candidates:
                            if candidate_id in [node['id'] for node in nodes] and (n['id'], candidate_id) not in seen:
                                seen.add((n['id'], candidate_id))
                                edges.append({
                                    'src': n['id'],
                                    'dst': candidate_id,
                                    'type': 'calls',
                                    'kind': kind,
                                    'file': n['file'],
                                    'line': line_idx + 1,
                                    'call_type': call_type,
                                    'resolution': result.status,
                                    'reason': result.reason
                                })
                elif result.status == 'external':
                    # External call - no edge to internal node
                    pass
                else:
                    # Unresolved - fall back to old heuristic
                    targets = [t for t in by_name.get(callee, []) if t['id'] != n['id'] and (n['id'], t['id']) not in seen]
                    if targets:
                        chosen = targets[0]
                        seen.add((n['id'], chosen['id']))
                        edges.append({
                            'src': n['id'],
                            'dst': chosen['id'],
                            'type': 'calls',
                            'kind': 'unresolved',
                            'file': n['file'],
                            'line': line_idx + 1,
                            'call_type': call_type,
                            'resolution': 'unresolved',
                            'reason': 'Fallback heuristic'
                        })
            else:
                # Fallback to old heuristic resolution for languages without resolver
                file_imports = _imports(texts.get(file_path, ''))
                
                targets = [t for t in by_name.get(callee, []) if t['id'] != n['id'] and (n['id'], t['id']) not in seen]
                if not targets:
                    continue
                
                # Disambiguate: prefer targets in the same file, then targets whose
                # module the caller imports, then targets in the same package.
                # Leave truly ambiguous cases as 'unresolved' instead of choosing the first.
                same_file = [t for t in targets if t['file'] == n['file']]
                if same_file:
                    chosen, kind = same_file[0], 'confirmed'
                else:
                    # Improved import-aware resolution
                    imported = []
                    for t in targets:
                        target_file = t['file']
                        target_module = target_file.rsplit('/', 1)[0] if '/' in target_file else target_file
                        target_module_name = target_module.replace('/', '.')

                        # Check if the target module is imported
                        for imp in file_imports:
                            # Exact module match
                            if imp == target_module_name:
                                imported.append(t)
                                break
                            # Target is a submodule of an import
                            if target_module_name.startswith(imp + '.'):
                                imported.append(t)
                                break
                            # Import is a submodule of target
                            if imp.startswith(target_module_name + '.'):
                                imported.append(t)
                                break
                            # Filename match (imported file name matches target file)
                            if imp == target_file.rsplit('/', 1)[-1].rsplit('.', 1)[0]:
                                imported.append(t)
                                break

                    if len(imported) == 1:
                        chosen, kind = imported[0], 'confirmed'
                    elif len(imported) > 1:
                        # Multiple imported matches - try to disambiguate by call context
                        # For now, mark as likely since we can't be sure
                        chosen, kind = imported[0], 'likely'
                    else:
                        # No imported matches - try same package
                        caller_module = n['file'].rsplit('/', 1)[0] if '/' in n['file'] else n['file']
                        same_package = []
                        for t in targets:
                            target_module = t['file'].rsplit('/', 1)[0] if '/' in t['file'] else t['file']
                            if target_module == caller_module:
                                same_package.append(t)

                        if len(same_package) == 1:
                            chosen, kind = same_package[0], 'likely'
                        elif len(same_package) > 1:
                            # Multiple in same package - mark as likely
                            chosen, kind = same_package[0], 'likely'
                        elif len(targets) == 1:
                            chosen, kind = targets[0], 'likely' if call_type != 'constructor' else 'confirmed'
                        else:
                            # Truly ambiguous: emit one unresolved edge to the first candidate
                            # rather than N edges, so callers/callees stay accurate.
                            chosen, kind = targets[0], 'unresolved'
                
                if call_type == 'method' and kind == 'confirmed':
                    kind = 'likely'   # method dispatch is never fully confirmed statically
                
                seen.add((n['id'], chosen['id']))
                edges.append({
                    'src': n['id'],
                    'dst': chosen['id'],
                    'type': 'calls',
                    'kind': kind,
                    'file': n['file'],
                    'line': line_idx + 1,
                    'call_type': call_type,
                    'resolution': 'unresolved'  # Fallback resolution
                })

    # Remove MAX_NODES cap - return all nodes for level-based graph serving
    # The server will handle pagination via /graph?focus=<id>&depth=2

    # Detect external services and libraries from imports
    external_services = set()
    for n in nodes:
        file_path = n.get('file', '')
        if file_path:
            imports = _imports(texts.get(file_path, ''))
            for imp in imports:
                # Check if it's a known external library
                if not any(imp in n2.get('file', '') for n2 in nodes):
                    external_services.add(imp)
    
    # Add external services as nodes
    for service in external_services:
        nodes.append({
            'id': f'external.{service}',
            'name': service,
            'kind': 'external',
            'file': 'external',
            'start': 0,
            'end': 0,
            'cluster': 'external',
            'loc': 0,
            'level': 'external',
            'parent': None
        })
    
    ids = {n['id'] for n in nodes}
    for t in tests:
        called = set(_CALL.findall(texts[t['file']]))
        t['covers'] = sorted({x['id'] for c in called for x in by_name.get(c, []) if x['id'] in ids and len(by_name[c]) <= 3})
    
    # Add graph metadata
    import time
    languages = set(n.get('language', 'unknown') for n in nodes)
    
    return {
        'nodes': nodes,
        'edges': edges,
        'tests': tests,
        'coverage': {},
        'external_services': list(external_services),
        'meta': {
            'schema_version': 2,
            'revision': revision,
            'indexed_at': time.time(),
            'languages': sorted(languages)
        }
    }
