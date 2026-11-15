#!/usr/bin/env python3
'''Aggregate http_runner shard results into one row per tag prefix.

Each shard run writes reports/<ts>_<tag>/results.jsonl + summary.json. Tags that
share a prefix before "-s" (e.g. baseline-3.5-s0, baseline-3.5-s1) are merged.

Usage: python3 scripts/eval_report.py [reports_dir]
'''
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPORTS = Path(sys.argv[1] if len(sys.argv) > 1 else 'jarvis-agent-evaluation/reports')


def group_tag(tag):
    # strip a trailing -s<k> shard suffix
    if '-s' in tag and tag.rsplit('-s', 1)[1].isdigit():
        return tag.rsplit('-s', 1)[0]
    return tag


def main():
    runs = defaultdict(list)   # group -> [row dicts]
    metas = {}
    for d in sorted(REPORTS.iterdir()):
        rj = d / 'results.jsonl'
        sj = d / 'summary.json'
        if not rj.exists():
            continue
        tag = d.name.split('_', 1)[1] if '_' in d.name else d.name
        group = group_tag(tag)
        meta = json.loads(sj.read_text()) if sj.exists() else {}
        metas.setdefault(group, meta)
        for line in rj.read_text().splitlines():
            if line.strip():
                runs[group].append(json.loads(line))

    out = Path('jarvis-agent-evaluation/reports/eval_summary.csv')
    with out.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['group', 'runs', 'infra', 'success_rate', 'fabricated',
                    'unstable_cases', 'latency_p50_ms', 'latency_p95_ms',
                    'model_calls_mean', 'tokens_mean',
                    'full_model', 'lite_model'])
        for g in sorted(runs):
            rows = runs[g]
            scored = [r for r in rows if not r.get('infra')]
            lat = [r['metrics'].get('latency_ms', 0) for r in scored if r.get('metrics')]
            calls = [r['metrics'].get('model_calls', 0) for r in scored if r.get('metrics')]
            toks = [r['metrics'].get('prompt_tokens', 0) + r['metrics'].get('output_tokens', 0)
                    for r in scored if r.get('metrics')]
            by_case = defaultdict(list)
            for r in scored:
                by_case[r['id']].append(r['passed'])
            env = metas.get(g, {}).get('env', {})
            w.writerow([g, len(rows), len(rows) - len(scored),
                        round(sum(r['passed'] for r in scored) / max(1, len(scored)), 4),
                        sum(r.get('fabricated', 0) for r in scored),
                        sum(1 for v in by_case.values() if len(set(v)) > 1),
                        int(statistics.median(lat)) if lat else 0,
                        sorted(lat)[int(len(lat) * 0.95) - 1] if lat else 0,
                        round(statistics.mean(calls), 2) if calls else 0,
                        round(statistics.mean(toks)) if toks else 0,
                        env.get('JARVIS_MODEL', ''), env.get('JARVIS_MODEL_LITE', '')])
            print('%-28s runs=%d infra=%d acc=%.3f fab=%d p50=%dms tok=%d' % (
                g, len(rows), len(rows) - len(scored),
                sum(r['passed'] for r in scored) / max(1, len(scored)),
                sum(r.get('fabricated', 0) for r in scored),
                int(statistics.median(lat)) if lat else 0,
                round(statistics.mean(toks)) if toks else 0))


if __name__ == '__main__':
    main()
