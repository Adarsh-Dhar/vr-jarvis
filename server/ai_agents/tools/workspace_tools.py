"""Workspace editing helpers: per-file syntax checks, line-range edits and
symbol extraction for files inside the sandbox worktree.

These are plain functions (not ADK tools): the /workspace/* routes call them
directly so a human edit gets the same fast feedback an agent patch would.
"""
from pathlib import Path

# Extensions worth parsing for the outline panel after a save.
_SYMBOL_EXTS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
                '.go', '.rs', '.java', '.cs', '.cpp', '.cc', '.cxx', '.hpp', '.h'}

# JavaScript/TypeScript per-edit check stays cheap: tsc is too slow to run on
# every save, so these files report checked=False and the full run_typecheck
# (or an on-demand CHECK) covers them.
_TS_EXTS = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}


def quick_syntax_check(worktree, rel):
    """Cheap syntax check of one saved file.

    Returns {'checked': bool, 'errors': [{'line', 'col', 'message'}], 'detail': str}.
    .py files are compile()d; JS/TS files are not checked per edit (checked=False);
    everything else is unchecked.
    """
    path = Path(worktree) / rel
    ext = path.suffix.lower()
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError as exc:
        return {'checked': False, 'errors': [], 'detail': str(exc)}
    if ext == '.py':
        try:
            compile(text, rel, 'exec')
            return {'checked': True, 'errors': [], 'detail': ''}
        except SyntaxError as exc:
            return {'checked': True, 'errors': [{
                'line': exc.lineno or 0, 'col': exc.offset or 0,
                'message': exc.msg or 'syntax error'}], 'detail': ''}
        except Exception as exc:
            return {'checked': True, 'errors': [{
                'line': 0, 'col': 0, 'message': str(exc)}], 'detail': ''}
    if ext in _TS_EXTS:
        return {'checked': False, 'errors': [],
                'detail': 'not checked per edit; run the type check to verify'}
    return {'checked': False, 'errors': [], 'detail': ''}


def apply_line_edit(text, op, start, end, new_text):
    """Apply a 1-based line-range edit to `text`.

    op: 'replace' (lines[start-1:end] become new_text's lines),
        'insert_after' (new_text's lines go after line `start`),
        'delete' (lines[start-1:end] are removed).
    Line endings are preserved (\\r\\n stays \\r\\n) and the file keeps its
    trailing-newline property. Returns (new_text, error); error is None on success.
    """
    lines = text.splitlines()
    eol = '\r\n' if '\r\n' in text else '\n'
    trailing = text.endswith(('\n', '\r'))
    n = len(lines)
    if not isinstance(start, int) or not (1 <= start <= n + 1):
        return None, 'start line %r is out of range (file has %d lines)' % (start, n)
    inserted = new_text.splitlines() if new_text else []
    if op == 'insert_after':
        idx = min(start, n)
        new_lines = lines[:idx] + inserted + lines[idx:]
    elif op in ('replace', 'delete'):
        if end is None:
            end = start      # single-line op: replace/delete just line `start`
        if not isinstance(end, int) or not (start <= end <= n):
            return None, 'end line must satisfy %d <= end <= %d' % (start, n)
        if op == 'replace':
            new_lines = lines[:start - 1] + inserted + lines[end:]
        else:
            new_lines = lines[:start - 1] + lines[end:]
    else:
        return None, 'unknown op: %r' % (op,)
    out = eol.join(new_lines)
    if trailing and new_lines:
        out += eol
    return out, None


def worktree_symbols(worktree, rel):
    """Symbols of a saved file parsed from the worktree copy, so the outline
    panel reflects edits before promote. Returns [] for unsupported types or
    on any parse failure — the graph itself is only rebuilt on /promote."""
    try:
        ext = Path(rel).suffix.lower()
        if ext not in _SYMBOL_EXTS:
            return []
        from ..intelligence.parsers.tree_sitter_parser import (
            EXT_TO_LANG, extract_symbols_with_tree_sitter)
        if ext not in EXT_TO_LANG:
            return []
        text = (Path(worktree) / rel).read_text(encoding='utf-8', errors='replace')
        return extract_symbols_with_tree_sitter(rel, text)
    except Exception:
        return []
