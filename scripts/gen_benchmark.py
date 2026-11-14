#!/usr/bin/env python3
'''Generate benchmark cases from a JARVIS graph index.
   python scripts/gen_benchmark.py GRAPH.json REPO_NAME [--per-kind 15]'''
import argparse, hashlib, json, sys
from collections import Counter
from pathlib import Path
import yaml

FUNC_KINDS = {'function', 'method'}   # node kind values in the graph JSON


def split_of(key):
    return 'test' if int(hashlib.sha1(key.encode()).hexdigest(), 16) % 10 < 3 else 'dev'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('graph')
    ap.add_argument('repo')
    ap.add_argument('--per-kind', type=int, default=15)
    ap.add_argument('--out', default='jarvis-agent-evaluation/benchmarks')
    a = ap.parse_args()

    raw = json.loads(Path(a.graph).read_text())
    nodes = {n['id']: n for n in raw['nodes']}
    name_count = Counter(n['name'] for n in nodes.values())
    unique = {i: n for i, n in nodes.items()
              if n.get('kind') in FUNC_KINDS and name_count[n['name']] == 1}

    callers, callees = {}, {}
    for e in raw['edges']:
        if e.get('type') != 'calls' or e.get('kind') != 'confirmed':
            continue
        if e['src'] in unique and e['dst'] in unique:
            callers.setdefault(e['dst'], set()).add(unique[e['src']]['name'])
            callees.setdefault(e['src'], set()).add(unique[e['dst']]['name'])

    cases = []
    def add(cat, key, question, expect):
        cid = '%s-%s' % (cat, hashlib.sha1(key.encode()).hexdigest()[:8])
        cases.append({'id': cid, 'repo': a.repo, 'category': cat,
                      'split': split_of(cid), 'question': question, 'expect': expect})

    for nid in sorted(callers)[:a.per_kind]:
        t = unique[nid]['name']
        names = sorted(callers[nid])[:8]
        add('callers', nid, 'Which functions call %s? List them.' % t,
            {'target': t, 'names': names})
    for nid in sorted(callees)[:a.per_kind]:
        t = unique[nid]['name']
        names = sorted(callees[nid])[:8]
        add('callees', nid, 'Which functions does %s call? List them.' % t,
            {'target': t, 'names': names})
    for nid in sorted(unique)[:a.per_kind]:
        n = unique[nid]
        add('where_defined', nid, 'In which file is %s defined?' % n['name'],
            {'target': n['name'], 'file': n['file']})
    existing = {n['name'] for n in nodes.values()}
    made = 0
    for stem in ('processRefund', 'syncLedger', 'rotateKeys', 'buildReport', 'purgeCache',
                 'mergeProfiles', 'retryQueue', 'signPayload', 'exportInvoices', 'healAccount'):
        if stem not in existing and made < min(10, a.per_kind):
            add('negative', stem, 'Which functions call %s?' % stem, {'target': stem})
            made += 1

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    path = out / ('benchmark_%s.yaml' % a.repo)
    path.write_text(yaml.safe_dump({'repo': a.repo, 'cases': cases}, sort_keys=False))
    print('wrote %d cases to %s' % (len(cases), path),
          Counter(c['category'] for c in cases), Counter(c['split'] for c in cases))


if __name__ == '__main__':
    sys.exit(main())
