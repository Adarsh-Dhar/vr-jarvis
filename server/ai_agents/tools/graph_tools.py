import json
from collections import deque
from functools import lru_cache

from google.adk.tools import ToolContext

from ..config import GRAPH_PATH, REPO_ROOT
from ._common import record_evidence
from ._safe import safe

MAX_RESULTS = 200          # most items any one tool call returns
MAX_SOURCE_LINES = 400     # most source lines get_source returns


@lru_cache(maxsize=1)
def _graph():
    raw = json.loads(GRAPH_PATH.read_text())
    nodes = {n['id']: n for n in raw['nodes']}
    out_edges, in_edges = {}, {}
    for e in raw['edges']:
        out_edges.setdefault(e['src'], []).append(e)
        in_edges.setdefault(e['dst'], []).append(e)
    return {'nodes': nodes, 'out': out_edges, 'in': in_edges,
            'tests': raw.get('tests', []), 'coverage': raw.get('coverage', {})}


def _brief(node_id):
    n = _graph()['nodes'].get(node_id, {})
    return {'id': node_id, 'name': n.get('name'), 'file': n.get('file'), 'cluster': n.get('cluster')}


def _cap(items):
    '''Return (items cut to MAX_RESULTS, total count, truncated flag).'''
    return items[:MAX_RESULTS], len(items), len(items) > MAX_RESULTS


def _missing(node_id):
    if node_id not in _graph()['nodes']:
        return {'status': 'error', 'error': 'Unknown node id: ' + node_id}
    return None


def _walk(start, adjacency, neighbor_key, max_depth, edge_types=None):
    seen = {start: 0}
    queue = deque([start])
    found = []
    while queue:
        current = queue.popleft()
        if seen[current] >= max_depth:
            continue
        for edge in adjacency.get(current, []):
            if edge_types and edge['type'] not in edge_types:
                continue
            nxt = edge[neighbor_key]
            if nxt in seen:
                continue
            seen[nxt] = seen[current] + 1
            queue.append(nxt)
            found.append({**_brief(nxt), 'depth': seen[nxt], 'via': current,
                          'edge_type': edge['type'], 'edge_kind': edge['kind']})
    return found


@safe
def search_graph_symbols(query: str, tool_context: ToolContext, limit: int = 8) -> dict:
    '''Find code symbols whose name, id or file path matches the query words.
    Returns up to `limit` matches with id, name, file and cluster. Use this first
    when you do not yet know a node id.'''
    words = query.lower().split()
    scored = []
    for n in _graph()['nodes'].values():
        hay = ' '.join([n['id'], n['name'], n['file']]).lower()
        score = sum(1 for w in words if w in hay)
        if score:
            scored.append((score, n))
    scored.sort(key=lambda pair: -pair[0])
    limit = max(0, min(limit, MAX_RESULTS))
    return {'status': 'ok', 'matches': [_brief(n['id']) for _, n in scored[:limit]]}


@safe
def get_node(node_id: str, tool_context: ToolContext) -> dict:
    '''Return details for one node: file, line range, cluster, complexity, churn and coverage.'''
    if (err := _missing(node_id)):
        return err
    n = _graph()['nodes'][node_id]
    cov = _graph()['coverage'].get(node_id)
    record_evidence(tool_context, [node_id])
    return {'status': 'ok', **n, 'coverage': cov}


@safe
def get_callers(node_id: str, tool_context: ToolContext, depth: int = 1) -> dict:
    '''Return functions that call node_id, up to `depth` hops away.
    Each item has id, name, file, depth and edge_kind (confirmed or inferred).'''
    if (err := _missing(node_id)):
        return err
    found, total, cut = _cap(_walk(node_id, _graph()['in'], 'src', depth, {'calls'}))
    record_evidence(tool_context, [node_id] + [f['id'] for f in found])
    return {'status': 'ok', 'node': node_id, 'callers': found, 'total': total, 'truncated': cut}


@safe
def get_callees(node_id: str, tool_context: ToolContext, depth: int = 1) -> dict:
    '''Return functions that node_id calls, up to `depth` hops away.
    Each item has id, name, file, depth and edge_kind (confirmed or inferred).'''
    if (err := _missing(node_id)):
        return err
    found, total, cut = _cap(_walk(node_id, _graph()['out'], 'dst', depth, {'calls'}))
    record_evidence(tool_context, [node_id] + [f['id'] for f in found])
    return {'status': 'ok', 'node': node_id, 'callees': found, 'total': total, 'truncated': cut}


@safe
def get_dependents(node_id: str, tool_context: ToolContext, max_depth: int = 4) -> dict:
    '''Return everything that transitively depends on node_id through calls or imports.
    Use for change-impact questions. Items include depth, the node they were reached via,
    and edge_kind (confirmed or inferred) of the last hop.'''
    if (err := _missing(node_id)):
        return err
    found, total, cut = _cap(_walk(node_id, _graph()['in'], 'src', max_depth))
    record_evidence(tool_context, [node_id] + [f['id'] for f in found])
    return {'status': 'ok', 'node': node_id, 'dependents': found, 'total': total, 'truncated': cut}


@safe
def trace_path(src_id: str, dst_id: str, tool_context: ToolContext) -> dict:
    '''Find the shortest call or import path from src_id to dst_id.
    Returns the ordered node ids and each hop with its edge_kind, or status no_path.'''
    for node_id in (src_id, dst_id):
        if (err := _missing(node_id)):
            return err
    g = _graph()
    parents = {src_id: None}
    queue = deque([src_id])
    while queue:
        cur = queue.popleft()
        if cur == dst_id:
            break
        for e in g['out'].get(cur, []):
            if e['dst'] not in parents:
                parents[e['dst']] = (cur, e)
                queue.append(e['dst'])
    if dst_id not in parents:
        return {'status': 'no_path'}
    path, hops, cur = [], [], dst_id
    while True:
        path.append(cur)
        link = parents[cur]
        if link is None:
            break
        hops.append({'from': link[0], 'to': cur, 'type': link[1]['type'], 'kind': link[1]['kind']})
        cur = link[0]
    path.reverse()
    hops.reverse()
    record_evidence(tool_context, path)
    return {'status': 'ok', 'path': path, 'hops': hops}


@safe
def get_cluster(cluster: str, tool_context: ToolContext) -> dict:
    '''List all nodes in a named cluster (for example auth, api, db).'''
    members, total, cut = _cap([_brief(i) for i, n in _graph()['nodes'].items() if n.get('cluster') == cluster])
    return {'status': 'ok', 'cluster': cluster, 'members': members, 'total': total, 'truncated': cut}


@safe
def get_source(node_id: str, tool_context: ToolContext, context_lines: int = 0) -> dict:
    '''Return the source text of a node from the repository, with optional extra lines around it.
    Always call this before making claims about what a function does.'''
    if (err := _missing(node_id)):
        return err
    n = _graph()['nodes'][node_id]
    root = REPO_ROOT.resolve()
    path = (REPO_ROOT / n['file']).resolve()
    if not path.is_relative_to(root):
        return {'status': 'error', 'error': 'Source path is outside the repository: ' + n['file']}
    if not path.is_file():
        return {'status': 'error', 'error': 'Source file not found: ' + n['file']}
    lines = path.read_text().splitlines()
    start = max(n['start'] - 1 - max(context_lines, 0), 0)
    end = min(n['end'] + max(context_lines, 0), len(lines))
    chunk = lines[start:end]
    cut = len(chunk) > MAX_SOURCE_LINES
    record_evidence(tool_context, [node_id])
    return {'status': 'ok', 'id': node_id, 'file': n['file'], 'first_line': start + 1,
            'source': '\n'.join(chunk[:MAX_SOURCE_LINES]), 'truncated': cut, 'total_lines': len(chunk)}


@safe
def find_tests_for_node(node_id: str, tool_context: ToolContext) -> dict:
    '''Return tests that cover node_id. An empty list means the node is untested.'''
    tests = [t for t in _graph()['tests'] if node_id in t.get('covers', [])]
    return {'status': 'ok', 'node': node_id, 'tests': tests, 'untested': not tests}


@safe
def get_coverage(node_id: str, tool_context: ToolContext) -> dict:
    '''Return line coverage (0 to 1) for node_id, or null if unknown.'''
    return {'status': 'ok', 'node': node_id, 'coverage': _graph()['coverage'].get(node_id)}


@safe
def verify_citations(node_ids: list[str], tool_context: ToolContext) -> dict:
    '''Check that each node id exists in the graph. Returns valid and invalid lists.
    Used by the grounding critic to reject claims that cite nothing real.'''
    nodes = _graph()['nodes']
    return {'status': 'ok',
            'valid': [i for i in node_ids if i in nodes],
            'invalid': [i for i in node_ids if i not in nodes]}
