"""Common structured result contract for specialist agents.

Specialists write their output_key value as JSON matching AgentResult:
status + answer + findings + evidence + unresolved + limitations. Extra
fields (plan, patch, review, ...) are preserved so existing consumers keep
working.
"""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator
from pathlib import Path


class Evidence(BaseModel):
    file: str
    line: int
    description: str = ''


class AgentResult(BaseModel):
    model_config = ConfigDict(extra='allow')   # preserve plan / patch / review fields
    status: Literal['completed', 'partial', 'unsupported', 'failed']
    answer: str = ''
    findings: List[Dict[str, Any]] = []
    evidence: List[Evidence] = []
    unresolved: List[str] = []
    limitations: List[str] = []
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
    with an in-range line number."""
    errs = []
    root = repo_root.resolve()
    for ev in result.evidence:
        p = (root / ev.file).resolve()
        if root not in p.parents and p != root:
            errs.append('evidence path outside repository: %s' % ev.file)
        elif not p.is_file():
            errs.append('evidence file not found: %s' % ev.file)
        elif ev.line < 1 or ev.line > sum(1 for _ in p.open(errors='ignore')):
            errs.append('evidence line out of range: %s:%d' % (ev.file, ev.line))
    return errs
