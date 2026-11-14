import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location(
    'http_runner', pathlib.Path(__file__).parents[2] / 'jarvis-agent-evaluation' / 'runner' / 'http_runner.py')
hr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hr)

NAMES = {'a', 'b', 'c', 'target'}


def case(cat, **expect):
    return {'category': cat, 'expect': expect}


def test_callers_full_recall_passes():
    r = hr.score(case('callers', target='target', names=['a', 'b']), {'reply': 'a and b call target'}, NAMES)
    assert r['passed'] and r['recall'] == 1.0


def test_callers_missing_name_fails():
    r = hr.score(case('callers', target='target', names=['a', 'b']), {'reply': 'a calls target'}, NAMES)
    assert not r['passed'] and r['recall'] == 0.5


def test_unverified_evidence_is_fabrication():
    r = hr.score(case('callers', target='target', names=['a']),
                 {'reply': 'a', 'unverified_evidence': ['ghost']}, NAMES)
    assert r['fabricated'] == 1 and not r['passed']


def test_negative_needs_not_found_and_no_evidence():
    ok = hr.score(case('negative', target='x'), {'reply': 'Function x was not found.'}, NAMES)
    bad = hr.score(case('negative', target='x'), {'reply': 'x is called by a.'}, NAMES)
    assert ok['passed'] and not bad['passed']


def test_word_boundary_matching():
    assert hr.names_in('alpha_beta', {'alpha', 'beta'}) == set()
