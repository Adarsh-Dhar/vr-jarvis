"""Common structured result contract for specialist agents.

Specialists write their output_key value as JSON matching AgentResult:
status + answer + findings + evidence + unresolved + limitations. Extra
fields (plan, patch, review, ...) are preserved so existing consumers keep
working.
"""
import json
import re
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pathlib import Path


class Evidence(BaseModel):
    file: str
    line: int = Field(ge=1)
    end_line: Optional[int] = Field(default=None, ge=1)
    description: str = ''
    source_tool: Optional[str] = None
    evidence_id: Optional[str] = None

    @model_validator(mode='after')
    def _end_line_after_line(self):
        if self.end_line is not None and self.end_line < self.line:
            raise ValueError('end_line must be >= line')
        return self


class AgentResult(BaseModel):
    model_config = ConfigDict(extra='allow')   # preserve plan / patch / review fields
    status: Literal['completed', 'partial', 'unsupported', 'failed']
    answer: str = ''
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    unresolved: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = Field(default_factory=list)
    reason: Optional[str] = None

    @model_validator(mode='after')
    def _reason_required(self):
        if self.status in ('partial', 'unsupported', 'failed') \
                and not (self.reason or self.limitations):
            raise ValueError('reason or limitations required for status %s'
                             % self.status)
        return self


def validate_evidence_paths(result: AgentResult, repo_root: Path) -> List[str]:
    """Every evidence entry must point at a real file inside the repository
    with an in-range line number.

    Fail-closed rules:
    - evidence paths must be repository-relative: absolute paths and '..'
      components are rejected before resolution;
    - symlinks are resolved and the canonical path must stay inside the
      active repository root;
    - the target must be an existing regular file;
    - line must be >= 1 and <= the file's line count;
    - end_line, when present, must be in range and not before line.

    This proves the path/line are real in the active repository; it does not
    by itself prove the agent actually inspected the source.
    """
    errs = []
    root = Path(repo_root).resolve()
    for ev in result.evidence:
        raw = ev.file or ''
        p = Path(raw)
        if p.is_absolute():
            errs.append('evidence path must be repository-relative: %s' % raw)
            continue
        parts = p.parts
        if '..' in parts:
            errs.append('evidence path must not contain ..: %s' % raw)
            continue
        resolved = (root / p).resolve()
        if resolved != root and root not in resolved.parents:
            errs.append('evidence path outside repository: %s' % raw)
            continue
        if not resolved.is_file():
            errs.append('evidence file not found: %s' % raw)
            continue
        try:
            n_lines = sum(1 for _ in resolved.open(errors='ignore'))
        except OSError:
            n_lines = 0
        if ev.line < 1 or ev.line > n_lines:
            errs.append('evidence line out of range: %s:%d' % (raw, ev.line))
            continue
        if ev.end_line is not None and (ev.end_line < ev.line or ev.end_line > n_lines):
            errs.append('evidence end_line out of range: %s:%d-%d'
                        % (raw, ev.line, ev.end_line))
    return errs


# ---------------------------------------------------------------------------
# Repair of near-miss specialist output
# ---------------------------------------------------------------------------
# Models often send the right content in the wrong envelope: JSON inside a code
# fence or after a sentence of prose, findings as plain strings, evidence entries
# without a usable file/line. coerce_agent_result() fixes those cases so the answer
# is not thrown away, and it NEVER invents evidence: unusable evidence entries are
# dropped and reported in `limitations`. Payloads that still cannot be understood
# (for example '{broken json') are returned unchanged and fail validation as before.

_STATUS_ALIASES = {'success': 'completed', 'succeeded': 'completed', 'complete': 'completed',
                   'done': 'completed', 'ok': 'completed', 'error': 'failed', 'incomplete': 'partial'}
_MAX_PROSE = 4000


def _extract_json_object(text: str) -> Optional[dict]:
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else None
    except ValueError:
        pass
    fence = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.S)
    if fence:
        try:
            v = json.loads(fence.group(1))
            if isinstance(v, dict):
                return v
        except ValueError:
            pass
    dec = json.JSONDecoder()
    for n, m in enumerate(re.finditer(r'\{', text)):
        if n >= 200:
            break
        try:
            v, _ = dec.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(v, dict) and ({'status', 'answer', 'findings'} & set(v)):
            return v
    return None


def _as_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _repair_evidence(items) -> Tuple[List[dict], int]:
    if not isinstance(items, list):
        return [], 0
    good, dropped = [], 0
    for ev in items:
        if not isinstance(ev, dict):
            dropped += 1
            continue
        file = ev.get('file') or ev.get('path')
        line = _as_int(ev.get('line', ev.get('start', ev.get('start_line'))))
        if not isinstance(file, str) or not file or line is None or line < 1:
            dropped += 1
            continue
        out = {'file': file, 'line': line}
        end = _as_int(ev.get('end_line', ev.get('end')))
        if end is not None and end >= line:
            out['end_line'] = end
        for k in ('description', 'source_tool', 'evidence_id'):
            if isinstance(ev.get(k), str):
                out[k] = ev[k]
        good.append(out)
    return good, dropped


def _str_list(v) -> List[str]:
    if isinstance(v, str):
        return [v] if v else []
    if isinstance(v, list):
        return [str(x) for x in v if x not in (None, '')]
    return []


def _repair_dict(obj: dict) -> Tuple[dict, List[str]]:
    obj = dict(obj)
    notes: List[str] = []
    st = obj.get('status')
    if isinstance(st, str):
        low = st.strip().lower()
        low = _STATUS_ALIASES.get(low, low)
        if low != st:
            obj['status'] = low
            notes.append('status normalised')
    elif st is None and (obj.get('answer') or obj.get('findings')):
        obj['status'] = 'partial'
        notes.append('status missing; marked partial')
    findings = obj.get('findings')
    if findings is not None and not isinstance(findings, list):
        obj['findings'] = [{'text': str(findings)}] if findings else []
        notes.append('findings was not a list')
    elif isinstance(findings, list) and any(not isinstance(f, dict) for f in findings):
        obj['findings'] = [f if isinstance(f, dict) else {'text': str(f)} for f in findings]
        notes.append('findings given as text; wrapped')
    if 'evidence' in obj:
        obj['evidence'], dropped = _repair_evidence(obj['evidence'])
        if dropped:
            notes.append('%d evidence entr%s without a usable file and line dropped'
                         % (dropped, 'y' if dropped == 1 else 'ies'))
    for key in ('unresolved', 'limitations'):
        if key in obj and not (isinstance(obj[key], list) and all(isinstance(x, str) for x in obj[key])):
            obj[key] = _str_list(obj[key])
    if 'diagnostics' in obj and not (isinstance(obj['diagnostics'], list)
                                     and all(isinstance(x, dict) for x in obj['diagnostics'])):
        obj['diagnostics'] = [x if isinstance(x, dict) else {'text': str(x)}
                              for x in (obj['diagnostics'] if isinstance(obj['diagnostics'], list) else [])]
    if notes:
        obj['limitations'] = _str_list(obj.get('limitations')) + ['output repaired: ' + '; '.join(notes)]
    if obj.get('status') in ('partial', 'unsupported', 'failed') \
            and not (obj.get('reason') or obj.get('limitations')):
        obj['limitations'] = ['specialist gave no reason']
    return obj, notes


def coerce_agent_result(raw: Any) -> Tuple[Any, List[str]]:
    """Return (value, notes). value is a repaired dict when raw was a near-miss,
    otherwise raw unchanged. notes lists what was repaired (empty = untouched)."""
    if isinstance(raw, dict):
        fixed, notes = _repair_dict(raw)
        return (fixed, notes) if notes else (raw, [])
    if not isinstance(raw, str) or not raw.strip():
        return raw, []
    text = raw.strip()
    obj = _extract_json_object(text)
    if obj is not None:
        fixed, notes = _repair_dict(obj)
        direct = False
        try:
            direct = isinstance(json.loads(text), dict)
        except ValueError:
            pass
        if direct and not notes:
            return raw, []                       # already valid JSON: leave untouched
        if not direct:
            notes = ['JSON found inside surrounding text'] + notes
        return fixed, notes
    if '{' not in text:                          # plain prose answer: keep the text, flag it
        return ({'status': 'partial', 'answer': text[:_MAX_PROSE],
                 'limitations': ['specialist replied in prose, not the JSON result format; '
                                 'text kept as the answer and not checked against evidence']},
                ['prose reply wrapped'])
    return raw, []                               # looks like broken JSON: fail closed
