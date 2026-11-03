#!/usr/bin/env python3
"""
Schema Validator for Agent Specifications and Test Cases
Validates YAML files against their defined schemas
"""

import yaml
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional


class SchemaValidator:
    """Validates agent specifications and test cases against their schemas."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_agent_specification(self, spec_path: Path) -> bool:
        """Validate an agent specification YAML file."""
        self.errors = []
        self.warnings = []

        try:
            with open(spec_path) as f:
                spec = yaml.safe_load(f)
        except Exception as e:
            self.errors.append(f"Failed to load YAML: {e}")
            return False

        # Required fields
        required_fields = [
            'agent_id', 'name', 'version', 'responsibility',
            'supported_tasks', 'allowed_tools', 'required_inputs',
            'required_output', 'decision_rules', 'boundaries',
            'dependencies', 'failure_behavior', 'quality_requirements',
            'performance_targets'
        ]

        for field in required_fields:
            if field not in spec:
                self.errors.append(f"Missing required field: {field}")

        # Field type validation
        if 'agent_id' in spec and not isinstance(spec['agent_id'], str):
            self.errors.append("agent_id must be a string")

        if 'supported_tasks' in spec and not isinstance(spec['supported_tasks'], list):
            self.errors.append("supported_tasks must be a list")

        if 'allowed_tools' in spec and not isinstance(spec['allowed_tools'], list):
            self.errors.append("allowed_tools must be a list")

        # Quality requirements validation
        if 'quality_requirements' in spec:
            qr = spec['quality_requirements']
            if 'minimum_precision' in qr:
                if not 0 <= qr['minimum_precision'] <= 1:
                    self.errors.append("minimum_precision must be between 0 and 1")
            if 'minimum_recall' in qr:
                if not 0 <= qr['minimum_recall'] <= 1:
                    self.errors.append("minimum_recall must be between 0 and 1")

        # Performance targets validation
        if 'performance_targets' in spec:
            pt = spec['performance_targets']
            if 'max_latency_seconds' in pt and pt['max_latency_seconds'] <= 0:
                self.errors.append("max_latency_seconds must be positive")
            if 'max_tool_calls' in pt and pt['max_tool_calls'] <= 0:
                self.errors.append("max_tool_calls must be positive")

        return len(self.errors) == 0

    def validate_test_case(self, test_path: Path) -> bool:
        """Validate a test case YAML file."""
        self.errors = []
        self.warnings = []

        try:
            with open(test_path) as f:
                test = yaml.safe_load(f)
        except Exception as e:
            self.errors.append(f"Failed to load YAML: {e}")
            return False

        # Required fields
        required_fields = [
            'test_id', 'agent', 'scenario', 'description',
            'layer', 'severity', 'fixture', 'user_request',
            'expected_behavior', 'expected_results', 'must_not',
            'grading', 'limits'
        ]

        for field in required_fields:
            if field not in test:
                self.errors.append(f"Missing required field: {field}")

        # Test ID format validation
        if 'test_id' in test:
            test_id = test['test_id']
            if not isinstance(test_id, str) or not test_id.startswith('AG-'):
                self.errors.append("test_id must start with 'AG-'")

        # Layer validation
        valid_layers = [
            'layer1_contract', 'layer2_responsibility', 'layer3_integration',
            'layer4_judgment', 'layer5_delegation', 'layer6_end_to_end',
            'layer7_stress'
        ]
        if 'layer' in test and test['layer'] not in valid_layers:
            self.errors.append(f"Invalid layer: {test['layer']}")

        # Severity validation
        valid_severities = ['critical', 'high', 'medium', 'low']
        if 'severity' in test and test['severity'] not in valid_severities:
            self.errors.append(f"Invalid severity: {test['severity']}")

        # Grading validation
        if 'grading' in test:
            grading = test['grading']
            total_weight = sum(grading.values()) if grading else 0
            if total_weight != 100:
                self.warnings.append(f"Grading weights sum to {total_weight}, expected 100")

        # Limits validation
        if 'limits' in test:
            limits = test['limits']
            if 'max_tool_calls' in limits and limits['max_tool_calls'] <= 0:
                self.errors.append("max_tool_calls must be positive")
            if 'max_duration_seconds' in limits and limits['max_duration_seconds'] <= 0:
                self.errors.append("max_duration_seconds must be positive")

        return len(self.errors) == 0

    def print_report(self):
        """Print validation report."""
        if self.errors:
            print("❌ Validation FAILED")
            for error in self.errors:
                print(f"  ERROR: {error}")
        else:
            print("✅ Validation PASSED")

        if self.warnings:
            print("\n⚠️  Warnings:")
            for warning in self.warnings:
                print(f"  WARNING: {warning}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python schema_validator.py <file.yaml> [--agent-spec|--test-case]")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    validator = SchemaValidator()

    if '--agent-spec' in sys.argv or file_path.name.startswith('agent_'):
        valid = validator.validate_agent_specification(file_path)
    elif '--test-case' in sys.argv or file_path.name.startswith('test_'):
        valid = validator.validate_test_case(file_path)
    else:
        print("❌ Unknown file type. Use --agent-spec or --test-case")
        sys.exit(1)

    validator.print_report()
    sys.exit(0 if valid else 1)


if __name__ == '__main__':
    main()
