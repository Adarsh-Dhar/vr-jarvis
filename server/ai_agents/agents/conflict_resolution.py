"""
Conflict Resolution
Resolves contradictions between agent findings.
"""

from typing import List, Dict, Any
from .findings import Finding, merge_findings


def resolve_conflicting_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Resolve contradictions between agent findings.

    Args:
        findings: List of findings from multiple agents

    Returns:
        Resolved findings with conflicts addressed
    """
    # Group findings by claim subject
    claim_groups = {}
    for finding in findings:
        claim = finding.get("claim", "")
        # Simple grouping by first few words
        key = " ".join(claim.split()[:5])
        if key not in claim_groups:
            claim_groups[key] = []
        claim_groups[key].append(finding)

    resolved = []
    for key, group in claim_groups.items():
        if len(group) == 1:
            # No conflict
            resolved.append(group[0])
        else:
            # Conflict detected
            # Choose the one with highest confidence
            highest_confidence = max(group, key=lambda f: f.get("confidence", 0))
            # Mark others as inferred if they have lower confidence
            for finding in group:
                if finding != highest_confidence:
                    finding["status"] = "inferred"
                    finding["resolved_from"] = highest_confidence.get("agent")
            resolved.append(highest_confidence)

    return resolved
