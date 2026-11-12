"""Semantic (cross-argument / filesystem) validation for tool contracts.

JSON schemas cannot compare two arguments or touch the filesystem, so these
rules run after schema validation on both call arguments and results.
"""
from typing import Any, Dict, List

PATH_PARAMS = ('file_path', 'path', 'directory')

# Per-tool argument rules: each returns an error string or None.
ARG_RULES: Dict[str, List] = {
    'read_file_range': [
        lambda a: 'start_line must be <= end_line'
        if a.get('start_line', 0) > a.get('end_line', 0) else None],
}

# Per-tool result rules.
RESULT_RULES: Dict[str, List] = {
    'read_file_range': [
        lambda r: 'end_line < start_line'
        if r.get('status') == 'ok' and r.get('end_line', 0) < r.get('start_line', 0)
        else None],
}


def _inside_repo(args):
    from ..tools._common import resolve_in_repo
    for k in PATH_PARAMS:
        if isinstance(args.get(k), str):
            try:
                resolve_in_repo(args[k])
            except Exception:
                yield '%s escapes the repository: %s' % (k, args[k])


def semantic_errors(tool_name: str, args: Dict[str, Any]) -> List[str]:
    """Argument rules: generic repository-containment check for path
    parameters (skipped for worktree tools, which legitimately address
    paths outside the main checkout), then per-tool rules."""
    errors = []
    if 'worktree' not in tool_name:
        errors.extend(_inside_repo(args or {}))
    for rule in ARG_RULES.get(tool_name, []):
        try:
            msg = rule(args or {})
        except Exception:
            msg = None
        if msg:
            errors.append(msg)
    return errors


def semantic_result_errors(tool_name: str, result: Any) -> List[str]:
    """Result rules: per-tool checks that need more than a schema."""
    errors = []
    if not isinstance(result, dict):
        return errors
    for rule in RESULT_RULES.get(tool_name, []):
        try:
            msg = rule(result)
        except Exception:
            msg = None
        if msg:
            errors.append(msg)
    return errors
