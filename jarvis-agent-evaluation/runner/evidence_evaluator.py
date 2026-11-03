#!/usr/bin/env python3
"""
Evidence Evaluator
Evaluates whether agent claims are supported by evidence
"""

import json
from typing import Dict, Any, List, Optional


class EvidenceEvaluator:
    """Evaluates whether agent claims are supported by evidence."""

    def __init__(self):
        self.unsupported_claims = []

    def evaluate_claim_evidence(self, claim: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate whether a claim is supported by evidence.

        Args:
            claim: The claim made by the agent
            evidence: The evidence provided

        Returns:
            Evidence evaluation result
        """
        if not evidence:
            return {
                'claim': claim,
                'supported': False,
                'reason': 'No evidence provided'
            }

        # Check for required evidence fields
        required_fields = ['source', 'type']
        missing_fields = [f for f in required_fields if f not in evidence]

        if missing_fields:
            return {
                'claim': claim,
                'supported': False,
                'reason': f'Missing evidence fields: {missing_fields}'
            }

        # Check if source location is valid
        source = evidence.get('source')
        if not source or not isinstance(source, str):
            return {
                'claim': claim,
                'supported': False,
                'reason': 'Invalid or missing source location'
            }

        # Check if evidence type is appropriate
        evidence_type = evidence.get('type')
        valid_types = ['source_location', 'function_call', 'data_flow', 'relationship', 'test_result']
        if evidence_type not in valid_types:
            return {
                'claim': claim,
                'supported': False,
                'reason': f'Invalid evidence type: {evidence_type}'
            }

        return {
            'claim': claim,
            'supported': True,
            'evidence': evidence,
            'reason': 'Evidence provided and valid'
        }

    def evaluate_all_claims(self, agent_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate all claims in agent output for evidence support.

        Args:
            agent_output: The complete output from the agent

        Returns:
            Overall evidence evaluation
        """
        # Extract claims from output
        claims = self._extract_claims(agent_output)
        evidence = agent_output.get('evidence', {})

        if not isinstance(evidence, dict):
            evidence = {}

        claim_evaluations = []
        unsupported_count = 0

        for claim in claims:
            # Find matching evidence for this claim
            claim_evidence = evidence.get(claim, None)
            evaluation = self.evaluate_claim_evidence(claim, claim_evidence)
            claim_evaluations.append(evaluation)

            if not evaluation['supported']:
                unsupported_count += 1
                self.unsupported_claims.append(claim)

        total_claims = len(claims)
        supported_claims = total_claims - unsupported_count

        return {
            'total_claims': total_claims,
            'supported_claims': supported_claims,
            'unsupported_claims': unsupported_count,
            'evidence_rate': supported_claims / total_claims if total_claims > 0 else 1.0,
            'claim_evaluations': claim_evaluations,
            'all_supported': unsupported_count == 0
        }

    def _extract_claims(self, agent_output: Dict[str, Any]) -> List[str]:
        """
        Extract factual claims from agent output.

        Args:
            agent_output: The agent's output

        Returns:
            List of claims
        """
        claims = []

        # Extract claims from different output fields
        # This is a simplified version - a real implementation would use NLP

        # From discovered_relationships
        relationships = agent_output.get('discovered_relationships', [])
        if isinstance(relationships, list):
            for rel in relationships:
                if isinstance(rel, dict):
                    claims.append(f"Relationship: {rel}")

        # From vulnerabilities
        vulnerabilities = agent_output.get('vulnerabilities', [])
        if isinstance(vulnerabilities, list):
            for vuln in vulnerabilities:
                if isinstance(vuln, dict):
                    claims.append(f"Vulnerability: {vuln.get('type', 'unknown')}")

        # From findings
        findings = agent_output.get('findings', [])
        if isinstance(findings, list):
            for finding in findings:
                if isinstance(finding, dict):
                    claims.append(f"Finding: {finding.get('description', 'unknown')}")

        return claims

    def grade_evidence_quality(self, agent_output: Dict[str, Any], weight: float) -> Dict[str, Any]:
        """
        Grade the quality of evidence in agent output.

        Args:
            agent_output: The agent's output
            weight: Weight for this dimension (0-100)

        Returns:
            Grading result
        """
        evaluation = self.evaluate_all_claims(agent_output)
        evidence_rate = evaluation['evidence_rate']

        score = evidence_rate * weight

        return {
            'dimension': 'evidence_quality',
            'weight': weight,
            'score': score,
            'max_score': weight,
            'passed': score >= weight * 0.9,  # 90% threshold for evidence
            'evidence_rate': evidence_rate,
            'total_claims': evaluation['total_claims'],
            'supported_claims': evaluation['supported_claims'],
            'unsupported_claims': evaluation['unsupported_claims']
        }

    def validate_source_location(self, source: str, repository_path: str) -> bool:
        """
        Validate that a source location actually exists in the repository.

        Args:
            source: Source location (e.g., "src/main.py:42")
            repository_path: Path to the repository

        Returns:
            True if source location is valid, False otherwise
        """
        from pathlib import Path

        # Parse source location
        # Expected format: "path/to/file:line" or "path/to/file"
        if ':' in source:
            file_path, line = source.rsplit(':', 1)
        else:
            file_path = source
            line = None

        full_path = Path(repository_path) / file_path

        if not full_path.exists():
            return False

        if line:
            try:
                line_num = int(line)
                # Check if line number is within file bounds
                with open(full_path) as f:
                    line_count = sum(1 for _ in f)
                return 1 <= line_num <= line_count
            except (ValueError, IOError):
                return False

        return True

    def get_unsupported_claims(self) -> List[str]:
        """Get list of unsupported claims detected."""
        return self.unsupported_claims
