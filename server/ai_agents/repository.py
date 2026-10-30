"""Repository catalogue: lists repos under /repository, indexes one into a graph, makes it the active repo."""
import ast
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

from . import config

SKIP_DIRS = {'.git', 'node_modules', 'dist', 'build', 'out', 'coverage', '__pycache__', '.venv', 'venv',
             'env', '.next', '.idea', '.vscode', 'target', 'vendor'}
JS_EXT = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
EXTS = JS_EXT | {'.py'}
MAX_FILE_BYTES = 400_000
MAX_NODES = 400          # keep the VR scene readable
MAX_FN_LINES = 400
MAX_BROWSER_FILE_BYTES = 512_000

_FN = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)')
_ARROW = re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s+)?'
                    r'(?:function\b|\([^)]*\)\s*(?::[^=]+)?=>|[A-Za-z_$][\w$]*\s*=>)')
_CLASS = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)')
_CALL = re.compile(r'\b([A-Za-z_$][\w$]*)\s*\(')
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
            nodes.append({'id': _dotted(rel) + '.' + sym, 'name': sym.split('.')[-1], 'kind': kind, 'file': rel,
                          'start': start, 'end': end, 'cluster': _cluster(rel), 'loc': max(end - start + 1, 1)})

    by_name = {}
    for n in nodes:
        by_name.setdefault(n['name'], []).append(n)
    edges, seen = [], set()
    for n in nodes:
        if n['kind'] == 'object':
            continue
        body = '\n'.join(texts[n['file']].splitlines()[n['start']:n['end']])   # skips the definition line itself
        imported = _imports(texts[n['file']])
        for callee in set(_CALL.findall(body)):
            targets = by_name.get(callee, [])
            if not targets or len(targets) > 3:
                continue
            for t in targets:
                if t['id'] == n['id'] or (n['id'], t['id']) in seen:
                    continue
                seen.add((n['id'], t['id']))
                stem = t['file'].rsplit('/', 1)[-1].rsplit('.', 1)[0]
                sure = t['file'] == n['file'] or stem in imported
                edges.append({'src': n['id'], 'dst': t['id'], 'type': 'calls', 'kind': 'confirmed' if sure else 'inferred'})

    if len(nodes) > MAX_NODES:       # keep the best connected symbols
        deg = {}
        for e in edges:
            deg[e['src']] = deg.get(e['src'], 0) + 1; deg[e['dst']] = deg.get(e['dst'], 0) + 1
        keep = {n['id'] for n in sorted(nodes, key=lambda n: -deg.get(n['id'], 0))[:MAX_NODES]}
        nodes = [n for n in nodes if n['id'] in keep]
        edges = [e for e in edges if e['src'] in keep and e['dst'] in keep]

    ids = {n['id'] for n in nodes}
    for t in tests:
        called = set(_CALL.findall(texts[t['file']]))
        t['covers'] = sorted({x['id'] for c in called for x in by_name.get(c, []) if x['id'] in ids and len(by_name[c]) <= 3})
    return {'nodes': nodes, 'edges': edges, 'tests': tests, 'coverage': {}}


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
