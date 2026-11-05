"""Repository catalogue: lists repos under /repository, indexes one into a graph, makes it the active repo."""
import ast
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

from . import config
from .tree_sitter_parser import extract_symbols_with_tree_sitter, extract_calls_with_tree_sitter

SKIP_DIRS = {'.git', 'node_modules', 'dist', 'build', 'out', 'coverage', '__pycache__', '.venv', 'venv',
             'env', '.next', '.idea', '.vscode', 'target', 'vendor'}
JS_EXT = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
EXTS = JS_EXT | {'.py'}
MAX_FILE_BYTES = 400_000
MAX_FN_LINES = 400
MAX_BROWSER_FILE_BYTES = 512_000

_FN = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)')
_ARROW = re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s+)?'
                    r'(?:function\b|\([^)]*\)\s*(?::[^=]+)?=>|[A-Za-z_$][\w$]*\s*=>)')
_CLASS = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)')
_CALL = re.compile(r'\b([A-Za-z_$][\w$]*)\s*\(')
_METHOD_CALL = re.compile(r'\b(?:self|this|[A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\s*\(')
_CONSTRUCTOR = re.compile(r'\bnew\s+([A-Za-z_$][\w$]*)\s*\(')
_IMPORT = re.compile(r'''(?:from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)|^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+)))''', re.M)


def list_repos():
    root = config.REPOSITORY_DIR
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir() and not d.is_symlink() and not d.name.startswith('.'))


def _source_files(repo):
    for p in sorted(repo.rglob('*')):
        if not p.is_file() or p.suffix not in EXTS:
            continue
        rel = p.relative_to(repo)
        if any(part in SKIP_DIRS for part in rel.parts) or p.stat().st_size > MAX_FILE_BYTES:
            continue
        yield p, rel.as_posix()


def _is_test(rel):
    name = rel.rsplit('/', 1)[-1]
    return ('.test.' in name or '.spec.' in name or name.startswith('test_') or name.endswith('_test.py')
            or rel.startswith(('tests/', 'test/', '__tests__/')) or '/__tests__/' in rel or '/tests/' in rel)


def _dotted(rel):
    return re.sub(r'\.[^./]+$', '', rel).replace('/', '.')


def _cluster(rel):
    parts = rel.split('/')
    return parts[0] if len(parts) > 1 else 'root'


def _js_end(lines, start):
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
    for path, rel in _source_files(repo):
        try:
            text = path.read_text(errors='replace')
        except OSError:
            continue
        texts[rel] = text
        if _is_test(rel):
            tests.append({'id': 'test.' + _dotted(rel), 'file': rel, 'covers': []})
            continue
        lines = text.splitlines()
        for sym, kind, start, end in _symbols(rel, text):
            # Determine node level based on kind and file structure
            level = 'function'
            if kind == 'object':
                level = 'class'
            elif 'route' in rel.lower() or 'controller' in rel.lower() or 'api' in rel.lower():
                level = 'route'
            elif 'service' in rel.lower() or 'business' in rel.lower():
                level = 'service'
            elif 'repository' in rel.lower() or 'repo' in rel.lower() or 'dao' in rel.lower() or 'database' in rel.lower():
                level = 'repository'
            elif 'test' in rel.lower() or _is_test(rel):
                level = 'test'
            
            # Determine parent based on file path
            parts = rel.split('/')
            parent = None
            if len(parts) > 1:
                parent = '.'.join(parts[:-1])
            elif len(parts) == 1:
                parent = 'root'
            
            nodes.append({
                'id': _dotted(rel) + '.' + sym, 
                'name': sym.split('.')[-1], 
                'kind': kind, 
                'file': rel,
                'start': start, 
                'end': end, 
                'cluster': _cluster(rel), 
                'loc': max(end - start + 1, 1),
                'level': level,
                'parent': parent
            })

    by_name = {}
    for n in nodes:
        by_name.setdefault(n['name'], []).append(n)
    edges, seen = [], set()
    
    # Add contains edges for hierarchy
    for n in nodes:
        if n.get('parent'):
            parent_id = n['parent'] + '.' + n.get('file', '').rsplit('/', 1)[-1].rsplit('.', 1)[0]
            edges.append({
                'src': parent_id,
                'dst': n['id'],
                'type': 'contains',
                'kind': 'confirmed'
            })
    
    # Add imports edges based on file imports
    for n in nodes:
        file_path = n.get('file', '')
        if file_path:
            imports = _imports(texts.get(file_path, ''))
            for imp in imports:
                # Find matching nodes in the imported module
                for target_node in nodes:
                    target_file = target_node.get('file', '')
                    if imp in target_file or imp in target_file.rsplit('/', 1)[-1]:
                        edges.append({
                            'src': n['id'],
                            'dst': target_node['id'],
                            'type': 'imports',
                            'kind': 'confirmed',
                            'file': n['file'],
                            'line': 1
                        })
                        break
    
    # Add call edges with improved resolution using tree-sitter
    for n in nodes:
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
        
        # Get imports for this file to resolve ambiguous calls
        file_imports = _imports(texts.get(file_path, ''))
        
        # Resolve each call
        for call in function_calls:
            callee = call['name']
            call_type = call.get('type', 'direct')
            line_idx = call['line'] - 1  # Convert to 0-based
            
            targets = [t for t in by_name.get(callee, []) if t['id'] != n['id'] and (n['id'], t['id']) not in seen]
            if not targets:
                continue
            
            # Disambiguate: prefer targets in the same file, then targets whose
            # module the caller imports, then a single remaining candidate.
            same_file = [t for t in targets if t['file'] == n['file']]
            if same_file:
                chosen, kind = same_file[0], 'confirmed'
            else:
                imported = [t for t in targets
                            if t['file'].rsplit('/', 1)[-1].rsplit('.', 1)[0] in file_imports
                            or _dotted(t['file']) in file_imports
                            or any(_dotted(t['file']).endswith('.' + imp) or imp.endswith('.' + _dotted(t['file']))
                                   for imp in file_imports)]
                if len(imported) == 1:
                    chosen, kind = imported[0], 'confirmed'
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
                'call_type': call_type
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
    return {'nodes': nodes, 'edges': edges, 'tests': tests, 'coverage': {}, 'external_services': list(external_services)}


def build_graph(name):
    """Hand-written <name>.graph.json next to the repo wins; otherwise index the files."""
    curated = config.REPOSITORY_DIR / (name + '.graph.json')
    graph = json.loads(curated.read_text()) if curated.is_file() else index_repo(name)
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    out = config.INDEX_DIR / (name + '.json')
    out.write_text(json.dumps(graph, indent=1))
    return out, graph


def info(name):
    repo = config.REPOSITORY_DIR / name
    files = sum(1 for _ in _source_files(repo))
    try:
        branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo, capture_output=True,
                                text=True, timeout=3).stdout.strip()
    except Exception:
        branch = ''
    return {'name': name, 'files': files, 'branch': branch or '-'}


def activate(name):
    """Make repository/<name> the repo every tool, endpoint and the VR UI works on. Returns the graph."""
    if name not in list_repos():                     # also blocks path traversal: must be a direct child
        raise KeyError(name)
    path, graph = build_graph(name)
    config.REPO_ROOT = config.REPOSITORY_DIR / name
    config.GRAPH_PATH = path
    from .tools import graph_tools, git_tools        # these imported the constants by value, so update them too
    for mod in (graph_tools, git_tools):
        mod.REPO_ROOT = config.REPO_ROOT
    graph_tools.GRAPH_PATH = path
    graph_tools._graph.cache_clear()
    return graph


# ---------------------------------------------------------------------------
# Read-only IDE browser API. Keep this separate from the AST index: the tree
# exposes ordinary files too, while the graph intentionally indexes only code.

BROWSER_SKIP_DIRS = SKIP_DIRS | {'.cache', '.pytest_cache', '.mypy_cache', '.ruff_cache'}


def _browser_repo(name: str) -> Path:
    """Resolve a direct child repository without following repository symlinks."""
    root = config.REPOSITORY_DIR.resolve()
    if not name or name not in list_repos():
        raise KeyError(name)
    candidate = root / name
    if candidate.is_symlink():
        raise ValueError('Repository symlinks are not browsable.')
    resolved = candidate.resolve(strict=True)
    if resolved.parent != root or not resolved.is_dir():
        raise ValueError('Invalid repository path.')
    return resolved


def _browser_target(repo: Path, relative_path: str) -> Path:
    """Resolve a repository-relative POSIX path and reject traversal/symlinks."""
    relative_path = relative_path or ''
    if '\x00' in relative_path or '\\' in relative_path:
        raise ValueError('Invalid path.')
    rel = PurePosixPath(relative_path)
    if rel.is_absolute() or any(part in ('..', '.') for part in rel.parts):
        if relative_path not in ('', '.'):
            raise ValueError('Path must stay inside the repository.')
    target = repo
    for part in rel.parts:
        if part in ('', '.'):
            continue
        target = target / part
        if target.is_symlink():
            raise ValueError('Symbolic links are not browsable.')
    resolved = target.resolve(strict=True)
    if resolved != repo and repo not in resolved.parents:
        raise ValueError('Path must stay inside the repository.')
    return resolved


def list_tree(name: str, relative_path: str = '') -> dict:
    """List direct children of a repository folder, directories first."""
    repo = _browser_repo(name)
    folder = _browser_target(repo, relative_path)
    if not folder.is_dir():
        raise NotADirectoryError(relative_path)
    entries = []
    for item in folder.iterdir():
        if item.is_symlink():
            continue
        if item.is_dir():
            if item.name in BROWSER_SKIP_DIRS:
                continue
            entry_type, size = 'directory', 0
        elif item.is_file():
            try:
                size = item.stat().st_size
            except OSError:
                continue
            entry_type = 'file'
        else:
            continue
        rel = item.relative_to(repo).as_posix()
        entries.append({'name': item.name, 'path': rel, 'type': entry_type, 'size': size})
    entries.sort(key=lambda e: (e['type'] != 'directory', e['name'].lower()))
    return {'repo': name, 'path': relative_path or '', 'entries': entries}


def read_browser_file(name: str, relative_path: str) -> dict:
    """Read a bounded UTF-8 text file for the VR editor; never writes to disk."""
    repo = _browser_repo(name)
    if not relative_path:
        raise ValueError('A file path is required.')
    target = _browser_target(repo, relative_path)
    if not target.is_file():
        raise FileNotFoundError(relative_path)
    size = target.stat().st_size
    with target.open('rb') as handle:
        raw = handle.read(MAX_BROWSER_FILE_BYTES + 1)
    if b'\x00' in raw[:8192]:
        raise ValueError('Binary files cannot be opened in the code viewer.')
    truncated = len(raw) > MAX_BROWSER_FILE_BYTES or size > MAX_BROWSER_FILE_BYTES
    raw = raw[:MAX_BROWSER_FILE_BYTES]
    content = raw.decode('utf-8-sig', errors='replace')
    return {
        'status': 'ok', 'repo': name, 'path': target.relative_to(repo).as_posix(),
        'content': content, 'size': size, 'total_lines': content.count('\n') + (1 if content else 0),
        'truncated': truncated,
    }
