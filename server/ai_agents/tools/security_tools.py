"""Deterministic security scan of Python files changed in the worktree."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from google.adk.tools import ToolContext

from ._safe import safe
from ._security_rules import (RULESET_VERSION, RULES, rule_for_bandit,
                              category_for, title_for, custom_findings)

SCANNER = 'python_static_security'


def _bandit(files: List[str], root) -> List[Dict[str, Any]]:
    """Run bandit JSON over files; exit 0/1 are normal, anything else raises."""
    if not files:
        return []
    rel = [str(Path(root) / f) for f in files]
    proc = subprocess.run(
        [sys.executable, '-m', 'bandit', '-q', '-f', 'json', *rel],
        capture_output=True, text=True, timeout=120)
    if proc.returncode not in (0, 1):
        raise RuntimeError('bandit exited %s: %s' % (proc.returncode,
                                                     proc.stderr[-500:]))
    try:
        data = json.loads(proc.stdout or '{}')
    except Exception:
        raise RuntimeError('bandit produced invalid JSON')
    if data.get('errors'):
        raise RuntimeError('bandit errors: %s' % data['errors'])
    return data.get('results') or []


def _line_evidence(root, rel, line):
    try:
        text = (Path(root) / rel).read_text(encoding='utf-8').splitlines()
        if 1 <= line <= len(text):
            return text[line - 1].strip()[:200]
    except Exception:
        pass
    return ''


def _map_bandit(results: List[Dict[str, Any]], root) -> tuple:
    findings, unsupported = [], 0
    for r in results:
        rid = rule_for_bandit(r.get('test_id', ''))
        if rid is None:
            unsupported += 1
            continue
        sev = str(r.get('severity', 'low')).lower()
        findings.append({
            'rule_id': rid, 'category': category_for(rid),
            'severity': sev if sev in ('low', 'medium', 'high', 'critical')
                        else 'low',
            'file': r.get('filename', ''), 'line': int(r.get('line_number') or 1),
            'title': title_for(rid),
            'evidence': _line_evidence(root, r.get('filename', ''),
                                       int(r.get('line_number') or 1))
                        or str(r.get('code', ''))[:200],
            'description': r.get('issue_text', ''),
            'remediation': 'Review and remediate per bandit %s.'
                           % r.get('test_id', ''),
            'confidence': 'medium',
            'introduced_by_current_change': True,
            '_key_extra': r.get('test_id'),
        })
    return findings, unsupported


def _key(f):
    import re
    ev = re.sub(r'\s+', ' ', (f.get('evidence') or '')).strip()
    return (f['rule_id'], f['file'], ev)


def _scan(wt) -> Dict[str, Any]:
    subprocess.run(['git', 'add', '-N', '.'], cwd=wt,
                   capture_output=True, text=True)
    diff = subprocess.run(['git', 'diff', '--name-only', '--diff-filter=AM',
                           'HEAD'], cwd=wt, capture_output=True, text=True,
                          timeout=60)
    files = [f for f in diff.stdout.split() if f.endswith('.py')]

    bandit_findings, unsupported = _map_bandit(_bandit(files, wt), wt)
    custom = custom_findings(files, wt)
    current = bandit_findings + custom

    # Baseline: scan the same files at HEAD in a temp dir.
    baseline = []
    if files:
        with tempfile.TemporaryDirectory() as td:
            base_files = []
            for rel in files:
                show = subprocess.run(['git', 'show', 'HEAD:%s' % rel],
                                      cwd=wt, capture_output=True, text=True)
                if show.returncode != 0:
                    continue  # new file: no baseline
                p = Path(td) / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(show.stdout, encoding='utf-8')
                base_files.append(rel)
            if base_files:
                bf, _ = _map_bandit(_bandit(base_files, td), td)
                baseline = bf + custom_findings(base_files, td)

    from collections import Counter
    base_keys = Counter(_key(f) for f in baseline)
    introduced, preexisting = [], []
    for f in current:
        k = _key(f)
        if base_keys.get(k, 0) > 0:
            base_keys[k] -= 1
            f['introduced_by_current_change'] = False
            preexisting.append(f)
        else:
            preexisting_flag = False
            introduced.append(f)
    for f in current:
        f.pop('_key_extra', None)

    try:
        import bandit
        version = getattr(bandit, '__version__', 'unknown')
    except Exception:
        version = 'unknown'
    return {'status': 'completed', 'scanner': SCANNER,
            'scanner_version': version, 'ruleset_version': RULESET_VERSION,
            'files_scanned': len(files),
            'unsupported_rules_ignored': unsupported,
            'findings': current,
            'counts': {'introduced': len(introduced),
                       'preexisting': len(preexisting)}}


@safe
def run_security_scan(tool_context: ToolContext) -> dict:
    """Deterministic security scan of Python files changed in the worktree."""
    wt = tool_context.state.get('worktree')
    if not wt:
        return {'status': 'error', 'error': 'No worktree yet.'}
    if importlib.util.find_spec('bandit') is None:
        res = {'status': 'unavailable', 'scanner': SCANNER, 'findings': [],
               'error': 'bandit is not installed'}
    else:
        try:
            res = _scan(wt)
        except Exception as exc:
            res = {'status': 'failed', 'scanner': SCANNER, 'findings': [],
                   'error': str(exc)}
    try:
        from .exec_tools import _worktree_fingerprint
        res['diff_hash'] = _worktree_fingerprint(wt)['diff_hash']
    except Exception:
        res['diff_hash'] = ''
    tool_context.state['security_scan'] = res
    return res
