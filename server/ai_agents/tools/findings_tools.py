"""
Findings Tools
Tools for recording and managing findings across agents.
"""

from typing import Dict, Any, List, Optional
from google.adk.tools import ToolContext
from ._safe import safe


@safe
def record_finding(
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
    Record a finding from the current agent.
    
    This tool allows agents to record structured findings with evidence.
    Findings are stored in state['findings'] and can be retrieved by other agents.
    
    Args:
        claim: The claim or assertion being made
        status: Status (confirmed, inferred, unresolved)
        confidence: Confidence score 0.0-1.0
        evidence: List of evidence dicts with file, start, end, node_id, tool
        unknowns: List of unknowns or assumptions
        tool_context: Tool context with state
        repository_id: Repository identifier (optional)
        repository_revision: Git commit hash or revision (optional)
        
    Returns:
        Success message
        
    Example:
        record_finding(
            claim="authenticateUser calls comparePassword",
            status="confirmed",
            confidence=1.0,
            evidence=[{
                "file": "src/auth.ts",
                "start": 30,
                "end": 42,
                "node_id": "node_123",
                "tool": "find_callers"
            }],
            unknowns=[],
            tool_context=tool_context
        )
    """
    from ..agents.findings import record_finding as _record_finding
    
    # Get the current agent name from tool context
    agent = tool_context.agent_name or "unknown"
    
    return _record_finding(
        agent=agent,
        claim=claim,
        status=status,
        confidence=confidence,
        evidence=evidence,
        unknowns=unknowns,
        tool_context=tool_context,
        repository_id=repository_id,
        repository_revision=repository_revision,
    )


@safe
def get_findings(
    tool_context: ToolContext,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get findings from state, optionally filtered by status.
    
    Args:
        tool_context: Tool context with state
        status: Optional status filter (confirmed, inferred, unresolved)
        
    Returns:
        List of findings
    """
    from ..agents.findings import get_findings as _get_findings
    from ..agents.findings import filter_findings_by_status
    
    findings = _get_findings(tool_context)
    
    if status:
        findings = filter_findings_by_status(findings, status)
    
    return findings


@safe
def verify_finding(
    claim: str,
    verification_status: str,
    verification_notes: str,
    tool_context: ToolContext,
) -> str:
    """
    Verify a finding by an independent agent or process.
    
    This tool allows a verification agent (or manual review) to mark
    a finding as verified or rejected based on independent evidence.
    
    Args:
        claim: The claim to verify (must match existing finding)
        verification_status: Verification status (verified, rejected, needs_review)
        verification_notes: Notes explaining the verification decision
        tool_context: Tool context with state
        
    Returns:
        Success message
    """
    findings = tool_context.state.get("findings", [])
    
    for finding in findings:
        if finding.get("claim") == claim:
            finding["verification_status"] = verification_status
            finding["verification_notes"] = verification_notes
            finding["verification_agent"] = tool_context.agent_name
            return f"Verified finding: {claim[:50]}..."
    
    return f"Finding not found: {claim[:50]}..."
