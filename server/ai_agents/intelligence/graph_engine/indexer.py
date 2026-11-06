"""Graph indexing - builds the call graph from source files.

Pipeline per file (parsed exactly once):
    source -> symbols + call sites (with lexical owners)
    -> per-call-site semantic resolution -> nodes / edges / call_sites

Edge semantics (schema v3):
    calls    - statically resolved call (kind 'confirmed')
    may_call - polymorphic/ambiguous candidate (kind 'possible'/'ambiguous')
    unresolved/dynamic/external calls produce NO internal edge; they are still
    recorded in the top-level ``call_sites`` collection.
"""
import ast
import json
import re
import subprocess
from pathlib import Path

from ... import config
from ..languages import language_for_path
from ..parsers.python_ast import analyze_python_source
from ..parsers.tree_sitter_parser import (
    extract_symbols_structured, extract_calls_structured,
    extract_imports_with_tree_sitter,
)
from ..resolvers.registry import get_resolver
from ..resolvers.python_resolver import PythonResolver
from .store import _source_files, SKIP_DIRS, EXTS, MAX_FN_LINES

# Regex patterns kept for the file-level imports aggregation and test coverage.
_CALL = re.compile(r'\b([A-Za-z_$][\w$]*)\s*\(')
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
    """Yield (name, kind, start_line, end_line) 1-based. Compatibility wrapper."""
    language = language_for_path(rel)
    if language == 'python':
        analysis = analyze_python_source(text, rel)
        for sym in analysis.get('symbols', []):
            yield sym['qualname'], sym['kind'], sym['start'], sym['end']
        return
    try:
        for sym in extract_symbols_structured(rel, text):
            yield sym['qualname'], sym['kind'], sym['start'], sym['end']
    except Exception:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith((' ', '\t')) and not line.lstrip().startswith(('export', 'function', 'async', 'const', 'class')):
                continue
            for rx, kind in ((re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)'), 'function'),
                             (re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*(?::[^=]+)?=>|[A-Za-z_$][\w$]*\s*=>)'), 'function'),
                             (re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)'), 'object')):
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


def _module_name_for(rel: str, language: str) -> str:
    """Dotted module path for a source file (Python only meaningful)."""
    if language != 'python':
        return ''
    mod = re.sub(r'\.py$', '', rel).replace('/', '.')
    if mod.endswith('.__init__'):
        mod = mod[:-len('.__init__')]
    return mod


def index_repo(name):
    """Build {nodes, edges, tests, coverage, call_sites} for repository/<name>."""
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

    # First pass: collect files, build file/module/symbol nodes, parse once.
    module_nodes = {}
    file_nodes = {}
    symbol_nodes = []
    analyses = {}        # rel -> parser analysis dict
    file_calls = {}      # rel -> [callsite dicts]

    for path, rel in _source_files(repo):
        try:
            text = path.read_text(errors='replace')
        except OSError:
            continue
        texts[rel] = text
        if _is_test(rel):
            tests.append({'id': 'test.' + _dotted(rel), 'file': rel, 'covers': []})
            continue

        language = language_for_path(rel)

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
            'parent': f'module::{module_name}',
            'language': language,
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
                'parent': None,
                'language': language,
            }

        # Parse once: symbols + call sites with lexical owners.
        if language == 'python':
            analysis = analyze_python_source(text, rel)
            raw_symbols = analysis.get('symbols', [])
            raw_calls = analysis.get('call_sites', [])
        else:
            try:
                raw_symbols = extract_symbols_structured(rel, text)
            except Exception:
                raw_symbols = []
            try:
                raw_calls = extract_calls_structured(rel, text)
            except Exception:
                raw_calls = []
            analysis = {
                'symbols': raw_symbols,
                'call_sites': raw_calls,
                'imports': extract_imports_with_tree_sitter(rel, text),
                'classes': {}, 'scopes': {}, 'ok': True,
            }
        analyses[rel] = analysis
        file_calls[rel] = raw_calls

        # Symbol nodes with canonical ids: <rel>::<qualified.name>
        for sym in raw_symbols:
            qualname = sym.get('qualname') or sym.get('name', '')
            if not qualname:
                continue
            kind = sym.get('kind', 'function')
            node_id = sym.get('id') or f'{rel}::{qualname}'
            legacy_id = sym.get('legacy_id') or (_dotted(rel) + '.' + qualname)
            start = sym.get('start', 1)
            end = sym.get('end', start)
            layer = _compute_layer(rel, texts)

            symbol_nodes.append({
                'id': node_id,
                'legacy_id': legacy_id,
                'qualname': qualname,
                'name': sym.get('name', qualname.split('.')[-1]),
                'kind': kind,
                'class_name': sym.get('class_name', ''),
                'class_qualname': sym.get('class_qualname', ''),
                'module': module_name,
                'file': rel,
                'start': start,
                'end': end,
                'signature': sym.get('signature', ''),
                'parameters': sym.get('parameters', []),
                'decorators': sym.get('decorators', []),
                'cluster': _cluster(rel),
                'loc': max(end - start + 1, 1),
                'level': 'class' if kind == 'object' else 'function',
                'layer': layer,
                'parent': file_id,
                'language': language,
            })

    # Combine all nodes
    nodes = list(module_nodes.values()) + list(file_nodes.values()) + symbol_nodes

    # ----- repository-wide graph context for resolvers ---------------------
    symbol_by_id = {n['id']: n for n in symbol_nodes}
    node_ids = {n['id'] for n in nodes}
    module_files = {}
    class_by_name = {}
    classes_info = {}
    for rel, analysis in analyses.items():
        language = language_for_path(rel)
        if language == 'python':
            mod = _module_name_for(rel, language)
            if mod:
                module_files[mod] = rel
        for sym in analysis.get('symbols', []):
            if sym.get('kind') == 'object':
                sid = sym.get('id') or f"{rel}::{sym.get('qualname', sym.get('name',''))}"
                class_by_name.setdefault(sym.get('name', ''), []).append(sid)
                classes_info[sid] = {
                    'name': sym.get('name', ''),
                    'qualname': sym.get('qualname', ''),
                    'file': rel,
                    'bases': sym.get('bases', []),
                    'base_ids': [],
                }

    graph_ctx = {
        'nodes': nodes,
        'node_ids': node_ids,
        'symbol_by_id': symbol_by_id,
        'module_files': module_files,
        'file_symbols': {rel: a.get('symbols', []) for rel, a in analyses.items()},
        'analyses': analyses,
        'class_by_name': class_by_name,
        'classes_info': classes_info,
        'subclasses': {},
    }

    by_name = {}
    for n in nodes:
        by_name.setdefault(n['name'], []).append(n)
    edges, seen = [], set()

    # Add contains edges for hierarchy (module -> file -> class/function)
    for n in nodes:
        parent_id = n.get('parent')
        if parent_id and (parent_id in module_nodes or parent_id in file_nodes):
            edges.append({
                'src': parent_id,
                'dst': n['id'],
                'type': 'contains',
                'kind': 'confirmed'
            })

    # Add aggregated imports edges at file level
    for file_id, file_node in file_nodes.items():
        file_path = file_node['file']
        imports = _imports(texts.get(file_path, ''))
        for imp in imports:
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
            src, dst = edge['src'], edge['dst']
            if src.startswith('module.') and dst.startswith('module.'):
                key = (src, dst)
                module_imports[key] = module_imports.get(key, 0) + 1
    for (src, dst), count in module_imports.items():
        edges.append({
            'src': src, 'dst': dst, 'type': 'imports',
            'kind': 'confirmed', 'count': count
        })

    # ----- inheritance edges + subclass index (Python) ---------------------
    py_resolver = PythonResolver()
    for n in symbol_nodes:
        if n.get('kind') != 'object' or n.get('language') != 'python':
            continue
        class_id = n['id']
        info = classes_info.get(class_id)
        if not info:
            continue
        for base_expr in info.get('bases', []):
            base_ids = py_resolver.resolve_base_class_ids([base_expr], n['file'], graph_ctx)
            info['base_ids'].extend(base_ids)
            for bid in base_ids:
                graph_ctx['subclasses'].setdefault(bid, set()).add(class_id)
                edges.append({
                    'src': class_id,
                    'dst': bid,
                    'type': 'inherits',
                    'kind': 'confirmed' if len(base_ids) == 1 else 'likely',
                    'file': n['file'],
                    'line': n.get('start', 0),
                })
    graph_ctx['subclasses'] = {k: sorted(v) for k, v in graph_ctx['subclasses'].items()}
    # dedupe base_ids preserving declaration order
    for info in classes_info.values():
        seen_b, ordered = set(), []
        for b in info['base_ids']:
            if b not in seen_b:
                seen_b.add(b)
                ordered.append(b)
        info['base_ids'] = ordered

    # ----- call-site resolution -------------------------------------------
    call_sites = []
    resolvers = {}

    for rel, calls in file_calls.items():
        if not calls:
            continue
        language = language_for_path(rel)
        resolver = get_resolver(language)
        if resolver is None:
            resolver = None
        file_ctx = None
        if resolver is not None:
            resolvers[language] = resolver
            try:
                file_ctx = resolver.build_context(rel, texts.get(rel, ''), nodes,
                                                  analyses.get(rel))
            except Exception:
                file_ctx = None

        for call in calls:
            caller_id = call.get('caller_id')
            caller_invalid = False
            # validate caller endpoint: must be a real symbol node or file node.
            # A genuinely module-level call has caller_id=None; a non-None id
            # that fails validation means ownership extraction failed — record
            # it instead of silently pretending it was module-level.
            if caller_id and caller_id not in node_ids:
                caller_invalid = True
                caller_id = None
            if not caller_id:
                caller_id = f'file::{rel}'
            callee_name = call.get('name', '')
            line_no = call.get('line', 0)
            column = call.get('column', 0)
            callsite_id = call.get('callsite_id') or f'{rel}:{line_no}:{column}'

            if resolver is not None and file_ctx is not None:
                try:
                    result = resolver.resolve(call, file_ctx, graph_ctx)
                except Exception as exc:
                    result = None
                    resolve_error = str(exc)
                else:
                    resolve_error = None
            else:
                result = None
                resolve_error = None

            if result is None:
                from ..resolvers.base import ResolutionResult, STATUS_UNRESOLVED
                result = ResolutionResult(
                    status=STATUS_UNRESOLVED,
                    reason=(f'No semantic resolver for language "{language}"'
                            if resolver is None else f'Resolver error: {resolve_error}'),
                    diagnostics=['no_semantic_resolver' if resolver is None else 'resolver_error'],
                )

            cs_record = {
                'id': callsite_id,
                'caller_id': call.get('caller_id'),
                'caller_node_id': caller_id,
                'expression': call.get('full_expression') or callee_name,
                'callee_name': callee_name,
                'receiver': call.get('receiver', ''),
                'receiver_root': call.get('receiver_root', ''),
                'call_type': call.get('call_type', 'direct'),
                'arg_count': call.get('arg_count', 0),
                'file': rel,
                'line': line_no,
                'column': column,
                'end_line': call.get('end_line', line_no),
                'language': language,
                'resolution': result.status,
                'targets': list(result.targets),
                'candidates': list(result.candidates),
                'reason': result.reason,
                'confidence': result.confidence,
                'resolution_method': result.resolution_method,
                'dispatch_kind': result.dispatch_kind,
                'diagnostics': list(result.diagnostics) + (['invalid_caller_id'] if caller_invalid else []),
                'evidence': list(result.evidence),
            }
            call_sites.append(cs_record)

            # ----- edges -------------------------------------------------
            if result.status == 'static_resolved':
                edge_targets = result.targets
                edge_type, edge_kind = 'calls', 'confirmed'
            elif result.status in ('polymorphic', 'ambiguous'):
                # dedupe targets+candidates preserving order
                seen_t = set()
                edge_targets = []
                for t in list(result.targets) + list(result.candidates):
                    if t not in seen_t:
                        seen_t.add(t)
                        edge_targets.append(t)
                edge_type = 'may_call'
                edge_kind = 'possible' if result.status == 'polymorphic' else 'ambiguous'
            else:
                edge_targets = []
                edge_type = edge_kind = None

            for target_id in edge_targets or []:
                if target_id not in node_ids:
                    continue
                key = (callsite_id, target_id, edge_type)
                if key in seen:
                    continue
                seen.add(key)
                edges.append({
                    'id': f'edge:{callsite_id}:{target_id}',
                    'src': caller_id,
                    'dst': target_id,
                    'type': edge_type,
                    'kind': edge_kind,
                    'callsite_id': callsite_id,
                    'resolution': result.status,
                    'confidence': result.confidence,
                    'call_type': call.get('call_type', 'direct'),
                    'file': rel,
                    'line': line_no,
                    'column': column,
                    'reason': result.reason,
                    'resolution_method': result.resolution_method,
                    'evidence': list(result.evidence),
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
            'parent': None,
            'language': 'external',
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
        'call_sites': call_sites,
        'external_services': list(external_services),
        'meta': {
            'schema_version': 3,
            'revision': revision,
            'indexed_at': time.time(),
            'languages': sorted(languages)
        }
    }
