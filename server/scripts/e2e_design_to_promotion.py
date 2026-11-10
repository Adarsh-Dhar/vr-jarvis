#!/usr/bin/env python3
"""
End-to-end demo: idea -> requirements -> architecture -> repository
comparison -> approval -> implementation plan -> code patch -> tests ->
commit approval -> promotion -> re-indexed graph.

Runs entirely against a throwaway COPY of a repository under /repository, so
the real checkout is never modified. The LLM calls are replaced by a small
stub (the point is to exercise the workflow plumbing, not the model), but
everything else is real: the repository graph, the comparison engine, the
plan tasks, the git worktree/patch/test/commit/promote pipeline and the
session endpoints.

Usage (from server/):
    python3 scripts/e2e_design_to_promotion.py [--repo demo-account-service] [--keep]
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

from fastapi.testclient import TestClient  # noqa: E402

import jarvis_server  # noqa: E402
from ai_agents import config, repository  # noqa: E402
from ai_agents.tools.git_tools import (  # noqa: E402
    apply_patch_to_worktree, create_worktree, get_worktree_diff)
from ai_agents.tools.exec_tools import run_tests, run_typecheck  # noqa: E402

PASS, FAIL = 'PASS', 'FAIL'
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print('  [%s] %s%s' % (PASS if ok else FAIL, name,
                          (' — ' + str(detail)[:160]) if detail else ''))
    return ok


def sh(cmd, cwd, timeout=30):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


def copy_repo(src: Path, dst: Path):
    """Copy a repository including .git and untracked dirs like node_modules.
    Uses APFS clonefile when available (copy-on-write, fast)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    p = sh(['cp', '-Rc', str(src), str(dst)], cwd='/', timeout=600)
    if p.returncode != 0:
        shutil.copytree(src, dst, symlinks=True)


def unified_patch(rel: str, old: str, new: str) -> str:
    """Build a git-apply-able unified diff for one file."""
    import difflib
    diff = difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile='a/' + rel, tofile='b/' + rel, lineterm='\n')
    body = ''.join(diff)
    # difflib omits the 'diff --git' header git apply likes to see.
    if not body.startswith('diff --git'):
        body = 'diff --git a/%s b/%s\n' % (rel, rel) + body
    return body


# ---------------------------------------------------------------------------
# Stubbed model layer: deterministic requirements + architecture that maps
# onto the real modules of the demo repository.


def stub_extract_requirements(idea_text, tool_context=None):
    return {'status': 'ok', 'source': 'stub',
            'requirements': {
                'goals': ['Expose a health-check endpoint for the account service'],
                'functional': ['Add a GET /healthz route that returns ok'],
                'non_functional': [], 'constraints': [], 'assumptions': [],
                'open_questions': ['Which module should own the health endpoint?']}}


def stub_propose_architecture(requirements, tool_context=None):
    comps = [
        {'id': 'c_auth', 'name': 'auth', 'responsibility': 'token verification',
         'kind': 'service', 'requirement_ids': []},
        {'id': 'c_lib', 'name': 'lib', 'responsibility': 'shared helpers',
         'kind': 'library', 'requirement_ids': []},
        {'id': 'c_db', 'name': 'db', 'responsibility': 'user persistence',
         'kind': 'data', 'requirement_ids': []},
        {'id': 'c_routes', 'name': 'routes', 'responsibility': 'HTTP endpoints',
         'kind': 'ui', 'requirement_ids': []},
        {'id': 'c_services', 'name': 'services', 'responsibility': 'account logic',
         'kind': 'service', 'requirement_ids': []},
    ]
    rels = [
        {'id': 'e1', 'src': 'c_routes', 'dst': 'c_services', 'kind': 'calls', 'label': ''},
        {'id': 'e2', 'src': 'c_services', 'dst': 'c_db', 'kind': 'reads', 'label': ''},
        {'id': 'e3', 'src': 'c_auth', 'dst': 'c_lib', 'kind': 'calls', 'label': ''},
    ]
    return {'status': 'ok', 'source': 'heuristic',
            'components': comps, 'relationships': rels}


PATCH_FILE = 'services/account.ts'
PATCH_OLD = "import { users } from '../db/users.repo';\n"
PATCH_MARKER = 'jarvisHealthCheck'
PATCH_SNIPPET = ("\nexport function %s(): string {\n  return 'ok';\n}\n"
                 % PATCH_MARKER)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default='demo-account-service')
    ap.add_argument('--keep', action='store_true',
                    help='keep the temporary repository copy')
    ap.add_argument('--skip-tests', action='store_true',
                    help='skip the jest/tsc leg (faster, weaker verification)')
    args = ap.parse_args()

    src = config.REPOSITORY_DIR / args.repo
    if not src.is_dir():
        print('repository not found: %s' % src)
        return 2

    tmp = Path(tempfile.mkdtemp(prefix='jarvis-e2e-'))
    repo_copy = tmp / 'repository' / args.repo
    print('== copying %s -> %s' % (src, repo_copy))
    t0 = time.time()
    copy_repo(src, repo_copy)
    print('   copied in %.1fs' % (time.time() - t0))
    # The source checkout can carry untracked artifacts (e.g. .coverage) that
    # would make promote_branch refuse. Remove untracked files in the COPY
    # only; ignored dirs like node_modules are untouched.
    sh(['git', 'clean', '-fdq'], cwd=repo_copy, timeout=120)

    # Point the whole server at the copy.
    config.REPOSITORY_DIR = tmp / 'repository'
    config.INDEX_DIR = tmp / 'index'

    jarvis_server.extract_requirements = stub_extract_requirements
    jarvis_server.propose_architecture = stub_propose_architecture

    headers = {}
    if os.environ.get('JARVIS_TOKEN'):
        headers['authorization'] = 'Bearer ' + os.environ['JARVIS_TOKEN']
    client = TestClient(jarvis_server.app)

    worktree = None
    try:
        print('== indexing repository copy')
        graph = await asyncio.to_thread(repository.activate, args.repo)
        check('repository indexed', len(graph.get('nodes', [])) > 0,
              '%d nodes' % len(graph.get('nodes', [])))

        sid = client.post('/session', headers=headers).json()['session_id']
        print('== session', sid)

        # 1. idea -> requirements + architecture proposal
        r = client.post('/design/propose', headers=headers, json={
            'session_id': sid, 'idea_text': 'add a health endpoint'})
        check('design proposal', r.status_code == 200, r.text[:200])
        body = r.json()
        arch = body['architecture']
        check('provenance labelled (heuristic stub, not "model")',
              arch.get('provenance') == 'heuristic', arch.get('provenance'))
        check('open question carried into architecture',
              bool(arch.get('open_questions')))

        # 2. repository comparison
        r = client.post('/design/%s/compare' % sid, headers=headers)
        check('repository comparison', r.status_code == 200, r.text[:200])
        cmp = r.json()
        n_conf = sum(1 for x in cmp['relationships'] if x['status'] == 'confirmed')
        check('components matched to repository',
              len(cmp['matched']) >= 4,
              '%d matched, %d missing' % (len(cmp['matched']), len(cmp['missing'])))
        check('at least one relationship confirmed', n_conf >= 1,
              '%d/%d confirmed' % (n_conf, len(cmp['relationships'])))
        for rel in cmp['relationships']:
            print('     rel %s -> %s [%s]: %s' % (
                rel['src'], rel['dst'], rel['kind'], rel['status']))

        # 3. resolve the open question, approve
        q = arch['open_questions'][0]
        r = client.post('/design/%s/edit' % sid, headers=headers, json={
            'session_id': sid,
            'ops': [{'op': 'resolve_question', 'question': q,
                     'answer': 'the routes module owns HTTP endpoints'}]})
        check('open question resolved with answer', r.status_code == 200, r.text[:200])
        r = client.post('/design/%s/approve' % sid, headers=headers,
                        json={'session_id': sid, 'approved': True,
                              'approved_by': 'e2e'})
        check('architecture approved', r.status_code == 200, r.text[:200])

        # 4. implementation plan
        r = client.post('/plan/generate', headers=headers,
                        json={'session_id': sid})
        check('implementation plan', r.status_code == 200, r.text[:200])
        plan = r.json()
        grounded = [t for t in plan['tasks'] if t.get('repo_match') == 'repository']
        check('tasks grounded in repository files',
              len(grounded) >= 3,
              '%d/%d tasks have files+symbols' % (
                  len(grounded), len(plan['tasks'])))
        for t in plan['tasks'][:3]:
            print('     task %s %-12s files=%s symbols=%s' % (
                t['id'], t['component_id'], t.get('files'),
                [s['name'] for s in (t.get('symbols') or [])][:3]))

        # pick the routes task (owns HTTP endpoints); its dependencies must be
        # done first — mark them complete with recorded evidence, as a
        # developer working through the plan in order would.
        task = next((t for t in plan['tasks']
                     if t['component_id'] == 'c_routes'), plan['tasks'][0])
        tid = task['id']
        done_ids = set()
        for t in plan['tasks']:
            if t['id'] == tid:
                break
            r = client.patch('/plan/%s/tasks/%s' % (sid, t['id']), headers=headers,
                             json={'status': 'done',
                                   'evidence': 'e2e: prerequisite completed'})
            if r.status_code == 200:
                done_ids.add(t['id'])
        check('prerequisite tasks completed', len(done_ids) > 0,
              '%d done' % len(done_ids))
        r = client.patch('/plan/%s/tasks/%s' % (sid, tid), headers=headers,
                         json={'status': 'running'})
        check('task %s started' % tid, r.status_code == 200, r.text[:200])

        # 5. code change: worktree -> patch -> tests -> typecheck
        sess = await jarvis_server.ensure(sid)
        ctx = SimpleNamespace(state=sess.state, agent_name='e2e')

        r = await asyncio.to_thread(create_worktree, ctx, 'jarvis/e2e-healthz')
        check('sandbox worktree created', r.get('status') == 'ok',
              r.get('worktree') or r.get('stderr', ''))
        worktree = r.get('worktree')

        repo_file = Path(worktree) / PATCH_FILE
        old = repo_file.read_text()
        new = old + PATCH_SNIPPET
        diff = unified_patch(PATCH_FILE, old, new)
        r = await asyncio.to_thread(apply_patch_to_worktree, diff, ctx)
        check('patch applied in worktree', r.get('status') == 'ok',
              r.get('stderr', ''))

        r = await asyncio.to_thread(get_worktree_diff, ctx)
        check('worktree diff produced', PATCH_MARKER in (r.get('diff') or ''))

        if not args.skip_tests:
            r = await asyncio.to_thread(run_tests, ['tests/account.test.ts'], ctx)
            check('tests passed in worktree', r.get('status') == 'passed',
                  'runner=%s exit=%s' % (r.get('runner'), r.get('exit_code')))
            r = await asyncio.to_thread(run_typecheck, ctx)
            check('typecheck passed',
                  r.get('typecheck') in ('passed', 'not_applicable'),
                  r.get('typecheck'))

        # persist what the tools recorded into the session state so the
        # approval gate sees the passing test run
        await jarvis_server.set_state(sid, {
            'worktree': ctx.state.get('worktree', ''),
            'last_test_run': ctx.state.get('last_test_run'),
            'last_typecheck': ctx.state.get('last_typecheck'),
            'pending_approval': 'Commit the verified patch to a sandbox branch',
            'approved': False,
            'approval_type': 'commit',
        })

        # 6. human approval -> commit on sandbox branch
        r = client.post('/approve', headers=headers,
                        json={'session_id': sid, 'approved': True})
        check('commit approved', r.status_code == 200 and r.json().get('ok'),
              r.text[:200])

        # 7. promote to the (copied) main checkout + re-index + task done
        r = client.post('/promote', headers=headers,
                        json={'session_id': sid})
        check('promoted to main checkout', r.status_code == 200
              and r.json().get('ok'), r.text[:200])

        head = sh(['git', 'log', '-1', '--format=%s'], cwd=repo_copy).stdout.strip()
        check('main checkout has JARVIS commit', head.startswith('JARVIS:'), head)
        check('patched file present in main checkout',
              PATCH_MARKER in (repo_copy / PATCH_FILE).read_text())

        r = client.get('/task/' + sid, headers=headers)
        tasks = r.json().get('tasks', [])
        done = [t for t in tasks if t.get('status') == 'done']
        check('plan task auto-completed on promote',
              any(t['id'] == tid for t in done),
              '%d done of %d' % (len(done), len(tasks)))

        r = client.get('/graph', headers=headers)
        check('graph re-indexed after promote',
              r.status_code == 200 and len(r.json().get('nodes', [])) > 0)

    finally:
        # cleanup the sandbox worktree, then the whole temp copy
        if worktree:
            sh(['git', 'worktree', 'remove', '--force', worktree],
               cwd=repo_copy if repo_copy.exists() else tmp, timeout=60)
            shutil.rmtree(worktree, ignore_errors=True)
        if args.keep:
            print('== kept temp copy at %s' % tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
            print('== temp copy removed')

    failed = [n for n, ok, _ in results if not ok]
    print('\n== %d checks, %d failed ==' % (len(results), len(failed)))
    for n in failed:
        print('   FAILED: ' + n)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
