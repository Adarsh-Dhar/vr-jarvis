"""Pure /graph response shaping, split out so it can be tested without the server.

Levels:
    'full'    - every node and edge (small repositories only)
    'module'  - module overview: module nodes plus module-level edges
    'cluster' - one page of a single cluster's member nodes
"""


def graph_view(data, level=None, cluster=None, offset=0, cap=2000, page_limit=2000):
    """Build the /graph response body for a loaded graph dict."""
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    meta = data.get('meta', {})
    cap = max(1, int(cap or 0))
    page_limit = max(1, int(page_limit or cap))

    if cluster:
        members = [n for n in nodes
                   if (n.get('cluster') or 'other') == cluster and n.get('level') != 'module']
        page = members[offset:offset + cap]
        ids = {n['id'] for n in page}
        return {
            'nodes': page,
            'edges': [e for e in edges if e.get('src') in ids and e.get('dst') in ids],
            'meta': meta, 'level': 'cluster', 'cluster': cluster,
            'total_nodes': len(members),
            'truncated': offset + cap < len(members),
            'next_offset': offset + cap if offset + cap < len(members) else 0,
        }

    mods = [n for n in nodes if n.get('level') == 'module']
    if level == 'module' or (level is None and len(nodes) > page_limit):
        ids = {n['id'] for n in mods}
        return {
            'nodes': mods,
            'edges': [e for e in edges if e.get('src') in ids and e.get('dst') in ids],
            'meta': meta, 'level': 'module',
            'total_nodes': len(nodes), 'total_edges': len(edges),
            'truncated': len(nodes) > len(mods),
        }

    return {
        'nodes': nodes, 'edges': edges, 'meta': meta, 'level': 'full',
        'total_nodes': len(nodes), 'total_edges': len(edges),
        'truncated': False,
    }
