"""Graph storage and repository management."""
import json
import subprocess
from pathlib import Path, PurePosixPath

from ... import config
from ..languages import SOURCE_EXTS

# Constants
MAX_FN_LINES = 400


def list_repos():
    """List all repositories under /repository."""
    root = config.REPOSITORY_DIR
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir() and not d.is_symlink() and not d.name.startswith('.'))


def build_graph(name):
    """Hand-written <name>.graph.json next to the repo wins; otherwise index the files."""
    from .indexer import index_repo
    curated = config.REPOSITORY_DIR / (name + '.graph.json')
    graph = json.loads(curated.read_text()) if curated.is_file() else index_repo(name)
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    out = config.INDEX_DIR / (name + '.json')
    out.write_text(json.dumps(graph, indent=1))
    return out, graph


def info(name):
    """Get repository information."""
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
    from ...tools import graph_tools, git_tools        # these imported the constants by value, so update them too
    for mod in (graph_tools, git_tools):
        mod.REPO_ROOT = config.REPO_ROOT
    graph_tools.GRAPH_PATH = path
    graph_tools._graph.cache_clear()
    # Clear CodeGraph cache
    from ... import codegraph
    codegraph.clear_cache()
    # Per-function data-flow facts are keyed on repo/graph/source; drop them too.
    try:
        from ...tools.data_flow_intelligence_tools import clear_facts_cache
        clear_facts_cache()
    except Exception:
        pass
    return graph


# ---------------------------------------------------------------------------
# Source file helpers (used by both indexer and browser API)
# These are shared utilities

SKIP_DIRS = {'.git', 'node_modules', 'dist', 'build', 'out', 'coverage', '__pycache__', '.venv', 'venv',
             'env', '.next', '.idea', '.vscode', 'target', 'vendor'}
JS_EXT = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
# All languages with a tree-sitter grammar and structural extraction support.
# Semantic call resolution is only claimed for languages with a resolver;
# the rest are indexed structurally and their call sites recorded as unresolved.
EXTS = SOURCE_EXTS
MAX_FILE_BYTES = 400_000
MAX_BROWSER_FILE_BYTES = 512_000


def _source_files(repo):
    """Yield (path, rel) for all source files in repo."""
    for p in sorted(repo.rglob('*')):
        if not p.is_file() or p.suffix not in EXTS:
            continue
        rel = p.relative_to(repo)
        if any(part in SKIP_DIRS for part in rel.parts) or p.stat().st_size > MAX_FILE_BYTES:
            continue
        yield p, rel.as_posix()


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
    return target


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
