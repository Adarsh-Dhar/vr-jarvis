#!/usr/bin/env python3
'''python scripts/eval_compare.py BASE/summary.json NEW/summary.json [--max-drop 0.03]'''
import argparse, json, sys

ap = argparse.ArgumentParser()
ap.add_argument('base'); ap.add_argument('new')
ap.add_argument('--max-drop', type=float, default=0.03)
a = ap.parse_args()
b, n = json.load(open(a.base)), json.load(open(a.new))
for k in ('success_rate', 'fabricated_total', 'unstable_cases', 'latency_ms_p50',
          'latency_ms_p95', 'model_calls_mean', 'tokens_mean', 'infra_errors'):
    print('%-18s %10s -> %-10s' % (k, b.get(k), n.get(k)))
bad = (n['success_rate'] < b['success_rate'] - a.max_drop) or (n['fabricated_total'] > b['fabricated_total'])
print('REGRESSION' if bad else 'OK')
sys.exit(1 if bad else 0)
