"""Common structured result contract for specialist agents.

Specialists write their output_key value as JSON matching AgentResult:
status + answer + findings + evidence + unresolved + limitations. Extra
fields (plan, patch, review, ...) are preserved so existing consumers keep
working.
"""
from typing import Any, Dict, List, Literal, Optional

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
