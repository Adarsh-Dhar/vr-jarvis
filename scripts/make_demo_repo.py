#!/usr/bin/env python3
"""Build repository/demo-account-service (a real git repo with a real authorization bug) and regenerate
ai_agents/data/graph.json and demo_change.json from it, using the SAME node ids as the Unity UI."""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / 'repository' / 'demo-account-service'
DATA = ROOT / 'ai_agents' / 'data'

FILES = {
'package.json': '''{
  "name": "demo-account-service",
  "private": true,
  "scripts": { "test": "jest" },
  "devDependencies": { "@types/jest": "^29.5.0", "jest": "^29.7.0", "ts-jest": "^29.1.0", "typescript": "^5.4.0" }
}
''',
'jest.config.js': "module.exports = { preset: 'ts-jest', testEnvironment: 'node', testMatch: ['<rootDir>/tests/**/*.test.ts'] };\n",
'tsconfig.json': '{ "compilerOptions": { "target": "es2020", "module": "commonjs", "strict": true, "esModuleInterop": true, "skipLibCheck": true, "types": ["jest", "node"] }, "include": ["**/*.ts"] }\n',
'.gitignore': 'node_modules\npackage-lock.json\n',
'lib/token.ts': '''export function verifyToken(header?: string): { id: string } | null {
  if (!header || !header.startsWith('Bearer ')) return null;
  return { id: header.slice(7) };
}
''',
'auth/requireAuth.ts': '''import { verifyToken } from '../lib/token';

type Req = { headers: { authorization?: string }; user?: { id: string } };
type Res = { sendStatus(code: number): void };

export function requireAuth(req: Req, res: Res, next: () => void) {
  const user = verifyToken(req.headers.authorization);
  if (!user) return res.sendStatus(401);
  req.user = user;
  next();
}
''',
'auth/owner.ts': '''// Returns true when the signed-in user owns the account.
export function checkOwner(userId: string, accountId: string): boolean {
  return userId === accountId;
}
''',
'db/users.repo.ts': '''import { query } from './client';

export async function deleteUser(id: string) {
  await query('DELETE FROM users WHERE id = $1', [id]);
}

export const users = {
  repo: { delete: deleteUser },
};
''',
'db/client.ts': '''export async function query(_sql: string, _params: unknown[]) {
  return { rowCount: 1 };
}
''',
'services/account.ts': '''import { users } from '../db/users.repo';

export async function getAccount(id: string) {
  return { id };
}

export async function deleteAccount(id: string) {
  await users.repo.delete(id);
  return { ok: true };
}
''',
'routes/account.ts': '''import { requireAuth } from '../auth/requireAuth';
import { deleteAccount } from '../services/account';

type Route = (req: any, res: any) => Promise<void>;
const routes: Record<string, { middleware: unknown; handler: Route }> = {};

routes['DELETE /account/:id'] = {
  middleware: requireAuth,
  handler: async (req, res) => {
    await deleteAccount(req.params.id);
    res.sendStatus(204);
  },
};

export { routes };
''',
'tests/account.test.ts': '''import { deleteAccount } from '../services/account';

jest.mock('../db/users.repo', () => ({ users: { repo: { delete: jest.fn() } } }));

describe('deleteAccount', () => {
  it('deletes own account', async () => {
    await expect(deleteAccount('u1')).resolves.toEqual({ ok: true });
  });
});
''',
}

AUDIT_PATCH = [("import { users } from '../db/users.repo';\n",
                "import { users } from '../db/users.repo';\nimport { audit } from '../lib/audit';\n"),
               ("  await users.repo.delete(id);\n", "  await audit.log('delete', id);\n  await users.repo.delete(id);\n")]
AUDIT = "export const audit = { log: async (_a: string, _id: string) => {} };\n"

def sh(*a, cwd=REPO):
    return subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True).stdout

def span(file, start_re):
    lines = (REPO / file).read_text().splitlines()
    for i, l in enumerate(lines):
        if re.search(start_re, l):
            indent = len(l) - len(l.lstrip())
            for j in range(i, len(lines)):
                if len(lines[j]) - len(lines[j].lstrip()) == indent and re.match(r'\s*(\}|\},|\}\);|\};)\s*$', lines[j]):
                    return i + 1, j + 1
    raise SystemExit('no span for ' + start_re)

def main():
    if REPO.exists():
        shutil.rmtree(REPO)
    for rel, text in FILES.items():
        p = REPO / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
    sh('git', 'init', '-q', '-b', 'main')
    sh('git', 'config', 'user.email', 'jarvis@example.com'); sh('git', 'config', 'user.name', 'jarvis')
    sh('git', 'add', '-A'); sh('git', 'commit', '-qm', 'baseline')

    # ---- graph.json: ids are identical to the Unity fixtures ----
    spec = [  # id, label, cluster, file, start regex, kind
        ('route.delete',     'DELETE /account/:id', 'api',      'routes/account.ts',  r"routes\['DELETE", 'route'),
        ('auth.require',     'requireAuth',         'auth',     'auth/requireAuth.ts', r'export function requireAuth', 'function'),
        ('service.delete',   'deleteAccount',       'services', 'services/account.ts', r'export async function deleteAccount', 'function'),
        ('auth.owner',       'checkOwner',          'auth',     'auth/owner.ts',      r'export function checkOwner', 'function'),
        ('db.delete',        'users.repo.delete',   'db',       'db/users.repo.ts',   r'export async function deleteUser', 'function'),
        ('db.repo',          'users.repo',          'db',       'db/users.repo.ts',   r'export const users', 'object'),
    ]
    nodes = []
    for nid, name, cluster, f, rx, kind in spec:
        s, e = span(f, rx)
        nodes.append({'id': nid, 'name': name, 'file': f, 'cluster': cluster, 'start': s, 'end': e, 'kind': kind})
    ts, te = span('tests/account.test.ts', r"it\('deletes own account'")
    nodes.append({'id': 'test.own-account', 'name': 'deletes own account', 'file': 'tests/account.test.ts',
                  'cluster': 'tests', 'start': ts, 'end': te, 'kind': 'test'})
    E = lambda s, d, t, k: {'src': s, 'dst': d, 'type': t, 'kind': k}
    edges = [
        E('route.delete', 'auth.require', 'calls', 'confirmed'),     # registered as middleware
        E('route.delete', 'service.delete', 'calls', 'confirmed'),
        E('service.delete', 'db.repo', 'calls', 'confirmed'),
        E('db.repo', 'db.delete', 'calls', 'inferred'),              # resolved through an object property
    ]
    graph = {'nodes': nodes, 'edges': edges,
             'tests': [{'id': 'test.own-account', 'name': 'deletes own account', 'file': 'tests/account.test.ts',
                        'covers': ['service.delete', 'db.repo']}],
             'coverage': {'route.delete': 0.0, 'auth.require': 0.0, 'service.delete': 1.0, 'auth.owner': 0.0,
                          'db.delete': 0.0, 'db.repo': 1.0}}
    # ---- the change under review: a real branch + real diff ----
    sh('git', 'checkout', '-q', '-b', 'feature/account-audit')
    (REPO / 'lib/audit.ts').write_text(AUDIT)
    p = REPO / 'services/account.ts'; t = p.read_text()
    for a, b in AUDIT_PATCH: t = t.replace(a, b)
    p.write_text(t)
    sh('git', 'add', '-A'); sh('git', 'commit', '-qm', 'Add audit log to deleteAccount')
    diff = sh('git', 'diff', 'main', 'feature/account-audit')
    sh('git', 'checkout', '-q', 'main')
    (DATA / 'graph.json').write_text(json.dumps(graph, indent=2))
    (REPO.parent / (REPO.name + '.graph.json')).write_text(json.dumps(graph, indent=2))   # curated graph wins over auto-index
    (DATA / 'demo_change.json').write_text(json.dumps({
        'branch': 'feature/account-audit', 'base': 'main', 'message': 'Add audit log to deleteAccount',
        'changed_nodes': ['service.delete'], 'diff': diff}, indent=2))
    (DATA / 'cached_test_results.json').write_text(json.dumps({
        'status': 'passed', 'passed': ['test.own-account'], 'failed': [], 'not_run': []}, indent=2))
    print('demo_repo + graph.json written;', len(nodes), 'nodes', len(edges), 'edges')

if __name__ == '__main__':
    main()
