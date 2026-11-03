#!/usr/bin/env python3
"""
Output Evaluator
Evaluates agent output against expected results and schema requirements
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path


class OutputEvaluator:
    """Evaluates agent output against expected results."""

    def __init__(self, agent_spec: Dict[str, Any]):
        self.agent_spec = agent_spec
        self.required_output_fields = self._extract_required_output_fields()

    def _extract_required_output_fields(self) -> List[Dict[str, Any]]:
        """Extract required output fields from agent specification."""
        required_output = self.agent_spec.get('required_output', [])
        return required_output

    def evaluate_schema_compliance(self, actual_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate whether the actual output complies with the required output schema.

        Args:
            actual_output: The actual output from the agent

        Returns:
            Schema compliance evaluation result
        """
        missing_fields = []
        unexpected_fields = []
        type_mismatches = []

        # Check for required fields
        for field_spec in self.required_output_fields:
            field_name = field_spec.get('name')
            required = field_spec.get('required', False)
            expected_type = field_spec.get('type')

            if required and field_name not in actual_output:
                missing_fields.append(field_name)
            elif field_name in actual_output:
                # Type checking (basic)
                actual_value = actual_output[field_name]
                if expected_type == 'string' and not isinstance(actual_value, str):
                    type_mismatches.append({
                        'field': field_name,
                        'expected_type': expected_type,
                        'actual_type': type(actual_value).__name__
                    })
                elif expected_type == 'array' and not isinstance(actual_value, list):
                    type_mismatches.append({
                        'field': field_name,
                        'expected_type': expected_type,
                        'actual_type': type(actual_value).__name__
                    })
                elif expected_type == 'object' and not isinstance(actual_value, dict):
                    type_mismatches.append({
                        'field': field_name,
                        'expected_type': expected_type,
                        'actual_type': type(actual_value).__name__
                    })
                elif expected_type == 'number' and not isinstance(actual_value, (int, float)):
                    type_mismatches.append({
                        'field': field_name,
                        'expected_type': expected_type,
                        'actual_type': type(actual_value).__name__
                    })

        # Check for unexpected fields
        expected_field_names = {f.get('name') for f in self.required_output_fields}
        for field_name in actual_output:
            if field_name not in expected_field_names:
                unexpected_fields.append(field_name)

        return {
            'compliant': len(missing_fields) == 0 and len(type_mismatches) == 0,
            'missing_fields': missing_fields,
            'unexpected_fields': unexpected_fields,
            'type_mismatches': type_mismatches
        }

    def evaluate_result_correctness(self, expected_results: Dict[str, Any], actual_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate whether the actual output matches expected results.

        Args:
            expected_results: Expected results from the test case
            actual_output: Actual output from the agent

        Returns:
            Result correctness evaluation
        """
        mismatches = []
        matches = []

        for key, expected_value in expected_results.items():
            if key not in actual_output:
                mismatches.append({
                    'field': key,
                    'expected': expected_value,
                    'actual': None,
                    'reason': 'Field missing from output'
                })
            else:
                actual_value = actual_output[key]
                if self._values_match(expected_value, actual_value):
                    matches.append(key)
                else:
                    mismatches.append({
                        'field': key,
                        'expected': expected_value,
                        'actual': actual_value,
                        'reason': 'Value mismatch'
                    })

        # Check for extra fields in actual output
        for key in actual_output:
            if key not in expected_results:
                mismatches.append({
                    'field': key,
                    'expected': None,
                    'actual': actual_output[key],
                    'reason': 'Unexpected field in output'
                })

        return {
            'correct': len(mismatches) == 0,
            'matches': matches,
            'mismatches': mismatches,
            'match_rate': len(matches) / len(expected_results) if expected_results else 0
        }

    def _values_match(self, expected: Any, actual: Any) -> bool:
        """
        Check if two values match.

        Args:
            expected: Expected value
            actual: Actual value

        Returns:
            True if values match, False otherwise
        """
        if expected is None and actual is None:
            return True
        if type(expected) != type(actual):
            return False
        if isinstance(expected, (list, dict)):
            return expected == actual
        return expected == actual

    def evaluate_output(self, test_case: Dict[str, Any], actual_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate agent output against test case expectations.

        Args:
            test_case: The test case definition
            actual_output: The actual output from the agent

        Returns:
            Complete output evaluation
        """
        expected_results = test_case.get('expected_results', {})

        schema_evaluation = self.evaluate_schema_compliance(actual_output)
        result_evaluation = self.evaluate_result_correctness(expected_results, actual_output)

        # Calculate overall score
        schema_score = 1.0 if schema_evaluation['compliant'] else 0.0
        result_score = result_evaluation['match_rate']

        overall_score = (schema_score + result_score) / 2

        return {
            'overall_score': overall_score,
            'schema_compliance': schema_evaluation,
            'result_correctness': result_evaluation,
            'passed': overall_score >= 0.8  # 80% threshold
        }


class DeterministicGrader:
    """Grades test results using deterministic checks."""

    def __init__(self):
        self.critical_violations = []

    def grade_result_correctness(self, expected: Dict[str, Any], actual: Dict[str, Any], weight: float) -> Dict[str, Any]:
        """
        Grade result correctness deterministically.

        Args:
            expected: Expected results
            actual: Actual results
            weight: Weight for this dimension (0-100)

        Returns:
            Grading result
        """
        if not expected or not actual:
            return {
                'dimension': 'result_correctness',
                'weight': weight,
                'score': 0,
                'max_score': weight,
                'passed': False,
                'reason': 'Missing expected or actual results'
            }

        # Count matching fields
        matches = 0
        total = len(expected)

        for key, expected_value in expected.items():
            if key in actual and actual[key] == expected_value:
                matches += 1

        score = (matches / total * weight) if total > 0 else 0

        return {
            'dimension': 'result_correctness',
            'weight': weight,
            'score': score,
            'max_score': weight,
            'passed': score >= weight * 0.8,
            'matches': matches,
            'total': total
        }

    def grade_output_schema(self, agent_spec: Dict[str, Any], actual_output: Dict[str, Any], weight: float) -> Dict[str, Any]:
        """
        Grade output schema compliance.

        Args:
            agent_spec: Agent specification
            actual_output: Actual output from agent
            weight: Weight for this dimension (0-100)

        Returns:
            Grading result
        """
        evaluator = OutputEvaluator(agent_spec)
        schema_eval = evaluator.evaluate_schema_compliance(actual_output)

        score = weight if schema_eval['compliant'] else 0

        return {
            'dimension': 'output_schema',
            'weight': weight,
            'score': score,
            'max_score': weight,
            'passed': schema_eval['compliant'],
            'missing_fields': schema_eval['missing_fields'],
            'type_mismatches': schema_eval['type_mismatches']
        }

    def grade_completeness(self, expected_behavior: List[str], actual_behavior: List[str], weight: float) -> Dict[str, Any]:
        """
        Grade completeness of agent behavior.

        Args:
            expected_behavior: Expected behaviors from test case
            actual_behavior: Actual behaviors observed
            weight: Weight for this dimension (0-100)

        Returns:
            Grading result
        """
        if not expected_behavior:
            return {
                'dimension': 'completeness',
                'weight': weight,
                'score': weight,
                'max_score': weight,
                'passed': True,
                'reason': 'No expected behaviors specified'
            }

        # Check which expected behaviors were completed
        completed = 0
        for behavior in expected_behavior:
            if any(behavior in actual for actual in actual_behavior):
                completed += 1

        score = (completed / len(expected_behavior) * weight) if expected_behavior else weight

        return {
            'dimension': 'completeness',
            'weight': weight,
            'score': score,
            'max_score': weight,
            'passed': score >= weight * 0.8,
            'completed': completed,
            'total': len(expected_behavior)
        }

    def check_critical_violations(self, must_not: List[str], actual_behavior: List[str]) -> List[str]:
        """
        Check for critical violations.

        Args:
            must_not: List of forbidden behaviors
            actual_behavior: List of actual behaviors

        Returns:
            List of critical violations detected
        """
        violations = []

        for forbidden in must_not:
            for actual in actual_behavior:
                if forbidden.lower() in actual.lower():
                    violations.append(forbidden)

        return violations

    def calculate_total_score(self, dimension_scores: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate total score from dimension scores.

        Args:
            dimension_scores: List of dimension grading results

        Returns:
            Total score calculation
        """
        total_score = sum(d['score'] for d in dimension_scores)
        max_score = sum(d['max_score'] for d in dimension_scores)

        # Check for critical violations
        if self.critical_violations:
            return {
                'total_score': 0,
                'max_score': max_score,
                'percentage': 0.0,
                'passed': False,
                'critical_violations': self.critical_violations,
                'reason': 'Critical violations detected'
            }

        return {
            'total_score': total_score,
            'max_score': max_score,
            'percentage': (total_score / max_score * 100) if max_score > 0 else 0,
            'passed': total_score >= max_score * 0.8,
            'dimension_scores': dimension_scores
        }
