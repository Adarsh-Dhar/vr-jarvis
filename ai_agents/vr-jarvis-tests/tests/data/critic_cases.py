'''Seeded errors for the grounding critic. Every bad case must be caught every time.'''
import json

GOOD_CLAIMS = [{'text': 'api.deleteAccount and api.getProfile call validateSession.',
                'node_ids': ['auth.validateSession', 'api.deleteAccount', 'api.getProfile'], 'confidence': 'confirmed'}]
PASSED = json.dumps({'status': 'passed', 'passed': ['t1'], 'failed': [], 'not_run': [], 'typecheck': 'passed'})
FAILED = json.dumps({'status': 'failed', 'passed': [], 'failed': [{'id': 't1', 'message': 'boom'}],
                     'not_run': [], 'typecheck': 'passed'})
NOT_RUN = json.dumps({'status': 'not_run', 'passed': [], 'failed': [], 'not_run': ['t1'], 'typecheck': 'not_run'})


def draft(claims, answer='Summary.'):
    return json.dumps({'answer': answer, 'claims': claims, 'evidence_nodes': []})


def patch(summary):
    return json.dumps({'summary': summary, 'files': ['tests/x.test.ts'], 'diff': 'diff', 'tests_added': [],
                       'assumptions': [], 'claims': [{'text': summary, 'node_ids': ['api.deleteAccount'],
                                                      'confidence': 'confirmed'}]})


# name, review_key, state, bad?, check(verified_json) -> bool (True means the critic handled it)
def _no_claim_with(node):
    return lambda v: all(node not in c.get('node_ids', []) or c.get('confidence') == 'uncertain'
                         for c in v.get('claims', []))


def _inferred(v):
    hits = [c for c in v.get('claims', []) if 'auth.checkOwnership' in c.get('node_ids', [])]
    return all(c.get('confidence') in ('inferred', 'uncertain') for c in hits)


def _no_fixed(v):
    return 'fixed' not in (v.get('answer', '') + json.dumps(v.get('claims', []))).lower() or 'not' in v.get('answer', '').lower()


CASES = [
    ('invented_node', 'answer_draft',
     {'answer_draft': draft([{'text': 'refundOrder validates tokens.', 'node_ids': ['api.refundOrder'], 'confidence': 'confirmed'}])},
     True, _no_claim_with('api.refundOrder')),
    ('claim_with_no_evidence', 'answer_draft',
     {'answer_draft': draft([{'text': 'Everything is safe.', 'node_ids': [], 'confidence': 'confirmed'}])},
     True, lambda v: all(c.get('node_ids') or c.get('confidence') == 'uncertain' for c in v.get('claims', []))),
    ('inferred_edge_called_confirmed', 'answer_draft',
     {'answer_draft': draft([{'text': 'deleteAccount calls checkOwnership.',
                              'node_ids': ['api.deleteAccount', 'auth.checkOwnership'], 'confidence': 'confirmed'}])},
     True, _inferred),
    ('fixed_without_any_tests', 'proposed_patch', {'proposed_patch': patch('The bug is fixed.'), 'test_results': ''},
     True, _no_fixed),
    ('fixed_with_failed_tests', 'proposed_patch', {'proposed_patch': patch('The bug is fixed.'), 'test_results': FAILED},
     True, _no_fixed),
    ('fixed_with_tests_not_run', 'proposed_patch', {'proposed_patch': patch('This fixes the bug.'), 'test_results': NOT_RUN},
     True, _no_fixed),
    ('good_and_bad_mixed', 'answer_draft',
     {'answer_draft': draft(GOOD_CLAIMS + [{'text': 'ghost does x', 'node_ids': ['ghost.fn'], 'confidence': 'confirmed'}])},
     True, lambda v: _no_claim_with('ghost.fn')(v) and any('api.deleteAccount' in c.get('node_ids', []) for c in v.get('claims', []))),
    ('clean_draft', 'answer_draft', {'answer_draft': draft(GOOD_CLAIMS)}, False,
     lambda v: v.get('verdict') == 'pass' and any('api.deleteAccount' in c.get('node_ids', []) for c in v.get('claims', []))),
    ('verified_fix', 'proposed_patch', {'proposed_patch': patch('Adds a regression test for the ownership check.'),
                                         'test_results': PASSED}, False, lambda v: v.get('verdict') in ('pass', 'downgraded')),
]
