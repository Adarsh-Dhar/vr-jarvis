"""Rule table and custom rules for the deterministic security scan.

Bandit supplies most rules; PY-PATH-001 is a conservative AST rule for
path-handling sinks whose first argument derives from a function parameter
without a repository-containment guard.
"""
import ast
from pathlib import Path
from typing import Any, Dict, List

RULESET_VERSION = '1'

# rule_id -> (category, bandit ids)
RULES = {
    'PY-EXEC-001': ('dynamic_code_execution', {'B102', 'B307'}),
    'PY-CMD-001': ('command_execution', {'B602', 'B604', 'B605'}),
    'PY-DESER-001': ('unsafe_deserialization', {'B301', 'B302', 'B506'}),
    'PY-CRED-001': ('hardcoded_credentials', {'B105', 'B106', 'B107'}),
    'PY-CRYPTO-001': ('weak_crypto', {'B303', 'B304', 'B305', 'B324'}),
    'PY-TLS-001': ('certificate_verification_disabled', {'B501', 'B323'}),
    'PY-PATH-002': ('file_handling', {'B202'}),
    'PY-PATH-001': ('file_handling', set()),  # custom AST rule below
}
_BANDIT_TO_RULE = {bid: rid for rid, (_, bids) in RULES.items()
                   for bid in bids}

_CATEGORIES = {rid: cat for rid, (cat, _) in RULES.items()}

_SINKS = {'open', 'remove', 'unlink', 'rmtree', 'copy', 'copyfile', 'move'}
_GUARDS = {'resolve_in_repo', 'abs_repo_path', '_safe_worktree_path',
           'resolve_repo_read', 'resolve_repo_write',
           'resolve_worktree_read', 'resolve_worktree_write',
           'path_resolver.resolve', 'realpath'}

_TITLE = {
    'PY-EXEC-001': 'Dynamic code execution',
    'PY-CMD-001': 'Command execution',
    'PY-DESER-001': 'Unsafe deserialization',
    'PY-CRED-001': 'Possible hardcoded credential',
    'PY-CRYPTO-001': 'Weak cryptography',
    'PY-TLS-001': 'TLS certificate verification disabled',
    'PY-PATH-001': 'File operation on unguarded parameter path',
    'PY-PATH-002': 'Unsafe archive member extraction',
}


def rule_for_bandit(bandit_id: str):
    return _BANDIT_TO_RULE.get(bandit_id)


def category_for(rule_id: str) -> str:
    return _CATEGORIES.get(rule_id, 'file_handling')


def title_for(rule_id: str) -> str:
    return _TITLE.get(rule_id, rule_id)


def _name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ''


def _uses_param(node, params) -> bool:
    return any(isinstance(n, ast.Name) and n.id in params
               for n in ast.walk(node))


def custom_findings(files: List[str], root) -> List[Dict[str, Any]]:
    """PY-PATH-001: flag open/remove/unlink/rmtree/copy/copyfile/move calls
    whose first argument contains a parameter of the enclosing function,
    unless that function also calls a repository-containment guard."""
    out = []
    for rel in files:
        try:
            tree = ast.parse((Path(root) / rel).read_text(encoding='utf-8'))
        except Exception:
            continue
        for fn in (n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            params = {a.arg for a in
                      list(fn.args.args) + list(fn.args.kwonlyargs)} \
                - {'self', 'cls', 'tool_context'}
            if not params:
                continue
            calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)]
            if {_name(c.func) for c in calls} & _GUARDS:
                continue
            for c in calls:
                if _name(c.func) in _SINKS and c.args \
                        and _uses_param(c.args[0], params):
                    out.append(_finding('PY-PATH-001', rel, c.lineno, c))
    return out


def _finding(rule_id, rel, line, node) -> Dict[str, Any]:
    try:
        evidence = ast.unparse(node)[:200]
    except Exception:
        evidence = ''
    return {'rule_id': rule_id, 'category': category_for(rule_id),
            'severity': 'medium', 'file': rel, 'line': line,
            'title': title_for(rule_id), 'evidence': evidence,
            'description': title_for(rule_id),
            'remediation': 'Validate the path against the repository root '
                           'before use (resolve_in_repo / _safe_worktree_path).',
            'confidence': 'low',
            'introduced_by_current_change': True}
