import os
import statistics

TRIALS = int(os.getenv('JARVIS_TRIALS', '5'))
SCALE = float(os.getenv('STRESS_SCALE', '1'))
LATENCY_FACTOR = float(os.getenv('STRESS_LATENCY_FACTOR', '1'))


def percentile(values, p):
    if not values:
        return 0.0
    v = sorted(values)
    k = min(len(v) - 1, int(round((p / 100) * (len(v) - 1))))
    return v[k]


def summarize(values):
    return {'n': len(values), 'p50': percentile(values, 50), 'p95': percentile(values, 95),
            'max': max(values) if values else 0.0, 'mean': statistics.fmean(values) if values else 0.0}


def assert_rate(results, minimum, label=''):
    '''results is a list of bools. Fails with the pass rate and how many trials failed.'''
    rate = sum(1 for r in results if r) / max(len(results), 1)
    assert rate >= minimum, '%s pass rate %.2f below %.2f (%d of %d failed)' % (
        label, rate, minimum, sum(1 for r in results if not r), len(results))
    return rate
