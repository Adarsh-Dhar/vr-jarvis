"""
Findings Schema and Recording
Shared findings format for all specialist agents.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from google.adk.tools import ToolContext


class EvidenceType(str):
    """Types of evidence supporting a finding."""
    STATIC = "static"  # From static analysis (code, AST, graph)
    RUNTIME = "runtime"  # From runtime instrumentation
    AI_INFERENCE = "ai_inference"  # From AI model reasoning
    UNRESOLVED = "unresolved"  # Evidence type could not be determined


class Evidence(BaseModel):
    """Single piece of evidence supporting a finding."""
    file: str = Field(..., description="File path")
    start: int = Field(..., description="Start line number")
    end: int = Field(..., description="End line number")
    node_id: str = Field(..., description="Graph node ID")
    tool: str = Field(..., description="Tool that provided this evidence")
    evidence_type: str = Field(default="static", description="Type of evidence: static, runtime, ai_inference, unresolved")
    snippet: Optional[str] = Field(None, description="Relevant code snippet")


class Finding(BaseModel):
    """A finding from a specialist agent."""
    agent: str = Field(..., description="Agent that made this finding")
    claim: str = Field(..., description="The claim or assertion")
    status: str = Field(..., description="Status: confirmed, inferred, or unresolved")
    confidence: float = Field(..., description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    evidence: List[Evidence] = Field(default_factory=list, description="Supporting evidence")
    unknowns: List[str] = Field(default_factory=list, description="What remains unknown")
    repository_id: Optional[str] = Field(None, description="Repository identifier")
    repository_revision: Optional[str] = Field(None, description="Git commit hash or revision")
    verification_status: str = Field(default="unverified", description="Verification status: verified, unverified, needs_review")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Provenance information: who, when, how")


def record_finding(
    agent: str,
    claim: str,
    status: str,
    confidence: float,
    evidence: List[Dict[str, Any]],
    unknowns: List[str],
    tool_context: ToolContext,
    repository_id: Optional[str] = None,
    repository_revision: Optional[str] = None,
) -> str:
    """
    Record a finding to state['findings'] list.

    Args:
        agent: Agent name
        claim: The claim or assertion
        status: Status (confirmed, inferred, unresolved)
        confidence: Confidence score 0.0-1.0
        evidence: List of evidence dicts
        unknowns: List of unknowns
        tool_context: Tool context with state
        repository_id: Repository identifier
        repository_revision: Git commit hash or revision

    Returns:
        Success message
    """
    # Validate status
    valid_statuses = ["confirmed", "inferred", "unresolved"]
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

    # Validate confidence
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

    # Convert evidence dicts to Evidence objects
    evidence_objects = []
    for ev in evidence:
        if isinstance(ev, dict):
            evidence_objects.append(Evidence(**ev))
        else:
            evidence_objects.append(ev)

    # Create finding with verification status
    # AI claims start as unverified unless they have strong static evidence
    verification_status = "unverified"
    if status == "confirmed" and evidence_objects:
        # If agent claims "confirmed" but we're in Phase 3, still mark as needs_review
        # Independent verification will determine final status
        verification_status = "needs_review"

    finding = Finding(
        agent=agent,
        claim=claim,
        status=status,
        confidence=confidence,
        evidence=evidence_objects,
        unknowns=unknowns,
        repository_id=repository_id,
        repository_revision=repository_revision,
        verification_status=verification_status,
        provenance={
            "agent": agent,
            "timestamp": tool_context.state.get("timestamp", "unknown"),
        }
    )

    # Add to state
    state = tool_context.state
    if "findings" not in state:
        state["findings"] = []

    state["findings"].append(finding.model_dump())

    return f"Recorded finding: {claim[:50]}..." if len(claim) > 50 else f"Recorded finding: {claim}"


def get_findings(tool_context: ToolContext) -> List[Dict[str, Any]]:
    """
    Get all findings from state.

    Args:
        tool_context: Tool context with state

    Returns:
        List of findings
    """
    state = tool_context.state
    return state.get("findings", [])


def filter_findings_by_status(
    findings: List[Dict[str, Any]],
    status: str
) -> List[Dict[str, Any]]:
    """
    Filter findings by status.

    Args:
        findings: List of findings
        status: Status to filter by

    Returns:
        Filtered findings
    """
    return [f for f in findings if f.get("status") == status]


def merge_findings(
    findings1: List[Dict[str, Any]],
    findings2: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge two lists of findings, removing duplicates.

    Args:
        findings1: First list of findings
        findings2: Second list of findings

    Returns:
        Merged findings
    """
    # Use a set to track unique claims
    seen = set()
    merged = []

    for finding in findings1 + findings2:
        claim = finding.get("claim", "")
        if claim not in seen:
            seen.add(claim)
            merged.append(finding)

    return merged
