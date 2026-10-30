'''Graph fixtures: a hand-checked tiny graph and a synthetic generator for scale tests.'''
import random

TINY_NODES = [
    # id, file, start, end, cluster
    ('api.deleteAccount', 'src/api/account.ts', 5, 40, 'api'),
    ('api.login', 'src/api/auth.ts', 3, 30, 'api'),
    ('api.getProfile', 'src/api/auth.ts', 32, 50, 'api'),
    ('auth.validateSession', 'src/auth/session.ts', 12, 48, 'auth'),
    ('auth.createSession', 'src/auth/session.ts', 50, 80, 'auth'),
    ('auth.checkOwnership', 'src/auth/ownership.ts', 1, 20, 'auth'),
    ('auth.hashPassword', 'src/auth/password.ts', 1, 15, 'auth'),
    ('db.getUser', 'src/db/users.ts', 1, 25, 'db'),
    ('db.deleteUser', 'src/db/users.ts', 27, 45, 'db'),
    ('db.saveSession', 'src/db/sessions.ts', 1, 20, 'db'),
    ('util.log', 'src/util/log.ts', 1, 10, 'util'),
    ('util.retry', 'src/util/retry.ts', 1, 15, 'util'),
    ('util.backoff', 'src/util/retry.ts', 17, 30, 'util'),
    ('util.formatError', 'src/util/errors.ts', 1, 8, 'util'),
    ('orphan.unused', 'src/orphan.ts', 1, 5, 'misc'),
]

# src, dst, type, kind
TINY_EDGES = [
    ('api.deleteAccount', 'auth.validateSession', 'calls', 'confirmed'),
    ('api.deleteAccount', 'db.deleteUser', 'calls', 'confirmed'),
    ('api.deleteAccount', 'auth.checkOwnership', 'calls', 'inferred'),
    ('api.login', 'auth.hashPassword', 'calls', 'confirmed'),
    ('api.login', 'auth.createSession', 'calls', 'confirmed'),
    ('api.login', 'auth.createSession', 'imports', 'confirmed'),   # parallel edge, different type
    ('api.login', 'db.getUser', 'calls', 'confirmed'),
    ('api.login', 'util.formatError', 'calls', 'inferred'),
    ('api.getProfile', 'auth.validateSession', 'calls', 'confirmed'),
    ('api.getProfile', 'db.getUser', 'calls', 'confirmed'),
    ('auth.validateSession', 'db.getUser', 'calls', 'confirmed'),
    ('auth.validateSession', 'util.log', 'calls', 'confirmed'),
    ('auth.createSession', 'db.saveSession', 'calls', 'confirmed'),
    ('auth.createSession', 'util.log', 'calls', 'confirmed'),
    ('db.getUser', 'util.retry', 'calls', 'confirmed'),
    ('db.deleteUser', 'util.retry', 'calls', 'confirmed'),
    ('util.retry', 'util.backoff', 'calls', 'confirmed'),
    ('util.backoff', 'util.retry', 'calls', 'confirmed'),          # cycle
    ('util.retry', 'util.log', 'calls', 'confirmed'),
]

TINY_TESTS = [
    {'id': 'test.session.expired', 'file': 'tests/session.test.ts', 'covers': ['auth.validateSession']},
    {'id': 'test.login.ok', 'file': 'tests/login.test.ts',
     'covers': ['api.login', 'auth.createSession', 'auth.hashPassword']},
    {'id': 'test.profile.ok', 'file': 'tests/profile.test.ts', 'covers': ['api.getProfile']},
]

TINY_COVERAGE = {
    'auth.validateSession': 0.82, 'api.login': 0.9, 'auth.createSession': 0.7,
    'auth.hashPassword': 1.0, 'api.getProfile': 0.6, 'api.deleteAccount': 0.0,
    'db.deleteUser': 0.0, 'auth.checkOwnership': 0.0,
}


def tiny_graph():
    nodes = [{'id': i, 'name': i.split('.')[1], 'kind': 'function', 'file': f, 'start': s, 'end': e,
              'cluster': c, 'complexity': 3, 'churn': 1} for i, f, s, e, c in TINY_NODES]
    edges = [{'src': a, 'dst': b, 'type': t, 'kind': k} for a, b, t, k in TINY_EDGES]
    return {'nodes': nodes, 'edges': edges, 'tests': [dict(t) for t in TINY_TESTS],
            'coverage': dict(TINY_COVERAGE)}


def tiny_ids():
    return [n[0] for n in TINY_NODES]


def synthetic_graph(n_nodes, seed=7, hub_callers=3000, chain_depth=60, inferred_p=0.05,
                    fanout=3, clusters=20, back_edge_p=0.01):
    '''Large graph with a hub node called by many nodes and a long call chain.'''
    rnd = random.Random(seed)
    nodes, edges = [], []

    def add_node(node_id, cluster):
        nodes.append({'id': node_id, 'name': node_id.split('.')[-1], 'kind': 'function',
                      'file': 'src/%s.ts' % node_id.replace('.', '_'), 'start': 1, 'end': 5,
                      'cluster': cluster, 'complexity': 1, 'churn': 0})

    base = max(n_nodes - hub_callers - chain_depth - 1, 10)
    ids = []
    for i in range(base):
        nid = 'm%d.f%d' % (i % clusters, i)
        add_node(nid, 'm%d' % (i % clusters))
        ids.append(nid)
    for i in range(1, base):
        for _ in range(rnd.randint(1, fanout)):
            j = rnd.randrange(0, i)
            edges.append({'src': ids[i], 'dst': ids[j], 'type': rnd.choice(['calls', 'calls', 'imports']),
                          'kind': 'inferred' if rnd.random() < inferred_p else 'confirmed'})
        if rnd.random() < back_edge_p:
            edges.append({'src': ids[rnd.randrange(0, i)], 'dst': ids[i], 'type': 'calls', 'kind': 'confirmed'})
    add_node('hub.core', 'hub')
    for k in range(hub_callers):
        nid = 'hub.caller%d' % k
        add_node(nid, 'hub')
        edges.append({'src': nid, 'dst': 'hub.core', 'type': 'calls', 'kind': 'confirmed'})
    for d in range(chain_depth):
        add_node('chain.c%d' % d, 'chain')
    for d in range(chain_depth - 1):
        edges.append({'src': 'chain.c%d' % d, 'dst': 'chain.c%d' % (d + 1), 'type': 'calls', 'kind': 'confirmed'})
    tests = [{'id': 'test.%d' % i, 'file': 'tests/t%d.ts' % i, 'covers': rnd.sample(ids, 3)}
             for i in range(max(base // 20, 1))]
    return {'nodes': nodes, 'edges': edges, 'tests': tests, 'coverage': {}}
