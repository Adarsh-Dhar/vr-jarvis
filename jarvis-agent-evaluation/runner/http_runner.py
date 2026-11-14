#!/usr/bin/env python3
'''Run benchmark cases against a live JARVIS server and score them.
   python http_runner.py --benchmark B.yaml --graph GRAPH.json --split dev --repeats 3 --tag baseline'''
import argparse, csv, json, os, re, statistics, subprocess, sys, time, uuid
import urllib.error, urllib.request
from pathlib import Path
import yaml

NOT_FOUND = re.compile('(not found|no such|does not exist|doesn.t exist|could not find|'
                       'couldn.t find|cannot find|can.t find|no match|no function)', re.I)
INFRA = re.compile('(timed out|429|quota|rate limit|503|unavailable|resource.?exhausted)', re.I)


def call(base, token, method, path, body=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or '{}')
        except Exception:
            return e.code, {'detail': str(e)}
    except Exception as e:
        return 0, {'detail': str(e)}


def names_in(text, names):
    return {n for n in names
            if re.search('(?<![A-Za-z0-9_])' + re.escape(n) + '(?![A-Za-z0-9_])', text)}


def score(case, resp, all_names):
    reply = resp.get('reply') or ''
    ev = resp.get('evidence_items') or []
    unverified = resp.get('unverified_evidence') or []
    fabricated = len(unverified) + sum(1 for e in ev if e.get('kind') != 'confirmed')
    exp, cat = case['expect'], case['category']
    out = {'fabricated': fabricated}
    if cat in ('callers', 'callees'):
        want = set(exp['names'])
        got = names_in(reply, all_names) - {exp['target']}
        tp = len(want & got)
        out['recall'] = tp / len(want) if want else 1.0
        out['precision'] = tp / len(got) if got else 0.0   # approximate: reply may name other functions
        out['passed'] = tp == len(want) and fabricated == 0
    elif cat == 'where_defined':
        out['passed'] = exp['file'] in reply and fabricated == 0
    elif cat == 'negative':
        out['passed'] = bool(NOT_FOUND.search(reply)) and fabricated == 0   # heuristic; read failures by hand
    else:
        out['passed'] = False
    return out


def pct(values, q):
    if not values:
        return 0
    if len(values) < 2:
        return values[0]
    return statistics.quantiles(values, n=100)[q - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--benchmark', required=True)
    ap.add_argument('--graph', required=True)
    ap.add_argument('--split', default='dev', choices=['dev', 'test', 'all'])
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--tag', default='run')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    token = os.environ.get('JARVIS_TOKEN', '')
    if not token:
        sys.exit('Set JARVIS_TOKEN')

    bench = yaml.safe_load(Path(a.benchmark).read_text())
    raw = json.loads(Path(a.graph).read_text())
    all_names = {n['name'] for n in raw['nodes'] if n.get('name')}
    cases = [c for c in bench['cases'] if a.split == 'all' or c['split'] == a.split]
    if a.limit:
        cases = cases[:a.limit]

    run_dir = Path('jarvis-agent-evaluation/reports') / (time.strftime('%Y%m%d-%H%M%S') + '_' + a.tag)
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with (run_dir / 'results.jsonl').open('w') as f:
        for case in cases:
            for rep in range(a.repeats):
                st, s = call(a.base_url, token, 'POST', '/session')
                if st != 200:
                    row = {'id': case['id'], 'category': case['category'], 'rep': rep,
                           'infra': True, 'passed': False, 'detail': str(s)[:200]}
                else:
                    st, resp = call(a.base_url, token, 'POST', '/ask', {
                        'session_id': s['session_id'], 'text': case['question'],
                        'request_id': uuid.uuid4().hex})
                    err = (resp.get('error') or resp.get('detail') or '') if isinstance(resp, dict) else ''
                    infra = st != 200 or bool(INFRA.search(str(err)))
                    sc = {'passed': False, 'fabricated': 0} if infra else score(case, resp, all_names)
                    row = {'id': case['id'], 'category': case['category'], 'rep': rep,
                           'infra': infra, **sc, 'metrics': resp.get('metrics', {}),
                           'reply': (resp.get('reply') or '')[:400]}
                rows.append(row)
                print(json.dumps(row), file=f); f.flush()
                print('%-22s rep%d %s' % (case['id'], rep,
                      'INFRA' if row['infra'] else ('PASS' if row['passed'] else 'FAIL')))

    scored = [r for r in rows if not r['infra']]
    lat = [r['metrics'].get('latency_ms', 0) for r in scored if r.get('metrics')]
    calls = [r['metrics'].get('model_calls', 0) for r in scored if r.get('metrics')]
    toks = [r['metrics'].get('prompt_tokens', 0) + r['metrics'].get('output_tokens', 0)
            for r in scored if r.get('metrics')]
    by_case = {}
    for r in scored:
        by_case.setdefault(r['id'], []).append(r['passed'])
    summary = {
        'tag': a.tag, 'split': a.split, 'repeats': a.repeats, 'cases': len(cases),
        'runs': len(rows), 'infra_errors': len(rows) - len(scored),
        'success_rate': round(sum(r['passed'] for r in scored) / max(1, len(scored)), 4),
        'fabricated_total': sum(r.get('fabricated', 0) for r in scored),
        'unstable_cases': sum(1 for v in by_case.values() if len(set(v)) > 1),
        'by_category': {c: round(sum(r['passed'] for r in scored if r['category'] == c) /
                                 max(1, sum(1 for r in scored if r['category'] == c)), 4)
                        for c in sorted({r['category'] for r in scored})},
        'latency_ms_p50': pct(lat, 50), 'latency_ms_p95': pct(lat, 95),
        'model_calls_mean': round(statistics.mean(calls), 2) if calls else 0,
        'tokens_mean': round(statistics.mean(toks)) if toks else 0,
        'commit': subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                                 capture_output=True, text=True).stdout.strip(),
        'env': {k: os.environ.get(k, '') for k in (
            'JARVIS_MODEL', 'JARVIS_LITE_MODEL', 'JARVIS_LLM_RPM',
            'JARVIS_LLM_ATTEMPTS', 'JARVIS_FAST_PATH')},
    }
    (run_dir / 'summary.json').write_text(json.dumps(summary, indent=2))
    hist = Path('jarvis-agent-evaluation/reports/history.csv')
    new = not hist.exists()
    with hist.open('a', newline='') as h:
        w = csv.writer(h)
        if new:
            w.writerow(['run', 'tag', 'split', 'success_rate', 'fabricated', 'p50_ms', 'p95_ms',
                        'calls', 'tokens', 'infra', 'commit'])
        w.writerow([run_dir.name, a.tag, a.split, summary['success_rate'], summary['fabricated_total'],
                    summary['latency_ms_p50'], summary['latency_ms_p95'], summary['model_calls_mean'],
                    summary['tokens_mean'], summary['infra_errors'], summary['commit']])
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
