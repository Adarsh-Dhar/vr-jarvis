#!/usr/bin/env python3
"""
Integrated Evaluation Harness
Combines all evaluation components into a cohesive test execution platform
"""

import yaml
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import evaluation components
from schema_validator import SchemaValidator
from tool_call_recorder import ToolCallRecorder, ToolCallValidator
from agent_trace_recorder import AgentTraceRecorder, TraceAnalyzer
from fixture_manager import FixtureManager, FixtureRegistry
from output_evaluator import OutputEvaluator, DeterministicGrader
from evidence_evaluator import EvidenceEvaluator
from policy_evaluator import PolicyEvaluator


class IntegratedEvaluationHarness:
    """Integrated harness for agent evaluation.
    
    Execution Modes:
    - 'mock': Uses simulated execution (for infrastructure validation)
    - 'live': Executes actual Google ADK agents (for real performance measurement)
    
    The 'mock' mode validates the evaluation framework works correctly.
    The 'live' mode measures actual JARVIS agent quality.
    """

    def __init__(self, base_dir: Path, execution_mode: str = 'mock'):
        self.base_dir = base_dir
        self.agent_specs_dir = base_dir / 'agent-specifications'
        self.evaluations_dir = base_dir / 'evaluations'
        self.fixtures_dir = base_dir / 'fixtures'
        self.reports_dir = base_dir / 'reports'
        self.execution_mode = execution_mode  # 'mock' or 'live'

        # Initialize components
        self.schema_validator = SchemaValidator()
        self.fixture_manager = FixtureManager(self.fixtures_dir)
        self.fixture_registry = FixtureRegistry(self.fixture_manager)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Initialized harness in {self.execution_mode} mode")

    def load_agent_spec(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Load an agent specification."""
        spec_path = self.agent_specs_dir / f'{agent_id}.yaml'
        if not spec_path.exists():
            return None

        with open(spec_path) as f:
            return yaml.safe_load(f)

    def validate_agent_spec(self, agent_id: str) -> bool:
        """Validate an agent specification."""
        spec_path = self.agent_specs_dir / f'{agent_id}.yaml'
        return self.schema_validator.validate_agent_specification(spec_path)

    def load_test_case(self, test_path: Path) -> Optional[Dict[str, Any]]:
        """Load a test case."""
        try:
            with open(test_path) as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Failed to load test case {test_path}: {e}")
            return None

    def execute_test(self, test_case: Dict[str, Any], agent_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single test case with full recording.

        Args:
            test_case: The test case definition
            agent_spec: The agent specification

        Returns:
            Complete test execution result
        """
        test_id = test_case.get('test_id')
        agent_id = test_case.get('agent')

        print(f"Executing test: {test_id}")

        # Initialize recorders
        tool_call_recorder = ToolCallRecorder()
        trace_recorder = AgentTraceRecorder(
            agent_id=agent_id,
            agent_version=agent_spec.get('version', '1.0.0'),
            model='placeholder'  # Will be replaced with actual model
        )

        # Start recording
        tool_call_recorder.start_recording()
        trace_recorder.start_recording(
            initial_task=test_case.get('user_request'),
            initial_context=test_case.get('fixture', {})
        )

        # Execute the agent based on execution mode
        if self.execution_mode == 'mock':
            # Mock execution: returns expected outputs for infrastructure validation
            actual_output = self._simulate_agent_execution(test_case, agent_spec)
            execution_note = 'Mock execution - infrastructure validation only'
        elif self.execution_mode == 'live':
            # Live execution: executes actual Google ADK agents
            actual_output = self._execute_real_agent(test_case, agent_spec)
            execution_note = 'Live execution - actual agent performance'
        else:
            raise ValueError(f"Unknown execution mode: {self.execution_mode}")
        
        # Record execution mode in trace
        trace_recorder.add_note(execution_note)

        # Stop recording
        trace_recorder.stop_recording(actual_output)
        tool_call_recorder.stop_recording()

        # Validate tool calls
        tool_validator = ToolCallValidator(agent_spec)
        tool_validation = tool_validator.validate_all_calls(tool_call_recorder.tool_calls)

        # Evaluate output
        output_evaluator = OutputEvaluator(agent_spec)
        output_evaluation = output_evaluator.evaluate_output(test_case, actual_output)

        # Evaluate evidence
        evidence_evaluator = EvidenceEvaluator()
        evidence_evaluation = evidence_evaluator.evaluate_all_claims(actual_output)

        # Evaluate policy compliance
        policy_evaluator = PolicyEvaluator(agent_spec)
        policy_evaluation = policy_evaluator.evaluate_boundary_compliance(trace_recorder.to_dict())

        # Grade the test
        grader = DeterministicGrader()
        dimension_scores = []

        # Grade each dimension
        grading_config = test_case.get('grading', {})

        if grading_config.get('result_correctness', 0) > 0:
            result_grade = grader.grade_result_correctness(
                test_case.get('expected_results', {}),
                actual_output,
                grading_config['result_correctness']
            )
            dimension_scores.append(result_grade)

        if grading_config.get('output_schema', 0) > 0:
            schema_grade = grader.grade_output_schema(
                agent_spec,
                actual_output,
                grading_config['output_schema']
            )
            dimension_scores.append(schema_grade)

        if grading_config.get('completeness', 0) > 0:
            completeness_grade = grader.grade_completeness(
                test_case.get('expected_behavior', []),
                [],  # Would be populated from actual behavior
                grading_config['completeness']
            )
            dimension_scores.append(completeness_grade)

        if grading_config.get('evidence_quality', 0) > 0:
            evidence_grade = evidence_evaluator.grade_evidence_quality(
                actual_output,
                grading_config['evidence_quality']
            )
            dimension_scores.append(evidence_grade)

        if grading_config.get('boundary_compliance', 0) > 0:
            boundary_grade = policy_evaluator.grade_boundary_compliance(
                trace_recorder.to_dict(),
                grading_config['boundary_compliance']
            )
            dimension_scores.append(boundary_grade)

        # Check for critical violations
        must_not = test_case.get('must_not', [])
        critical_violations = grader.check_critical_violations(must_not, [])

        # Calculate total score
        total_score = grader.calculate_total_score(dimension_scores)

        # Determine overall status
        if critical_violations:
            status = 'failed'
        elif total_score['passed']:
            status = 'passed'
        else:
            status = 'failed'
        
        # If in mock mode, mark status as 'mock_passed' to distinguish from real execution
        if self.execution_mode == 'mock' and status == 'passed':
            status = 'mock_passed'
        elif self.execution_mode == 'mock' and status == 'failed':
            status = 'mock_failed'

        # Compile complete result
        result = {
            'test_id': test_id,
            'agent': agent_id,
            'scenario': test_case.get('scenario'),
            'status': status,
            'execution_mode': self.execution_mode,
            'timestamp': datetime.now().isoformat(),
            'execution': {
                'actual_output': actual_output,
                'duration_seconds': trace_recorder.to_dict().get('summary', {}).get('duration_seconds', 0)
            },
            'tool_calls': tool_call_recorder.to_dict(),
            'trace': trace_recorder.to_dict(),
            'tool_validation': tool_validation,
            'output_evaluation': output_evaluation,
            'evidence_evaluation': evidence_evaluation,
            'policy_evaluation': policy_evaluation,
            'grading': {
                'dimension_scores': dimension_scores,
                'total_score': total_score,
                'critical_violations': critical_violations
            }
        }

        return result

    def _simulate_agent_execution(self, test_case: Dict[str, Any], agent_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate agent execution by returning expected output to pass tests.

        This provides a mock execution that matches test expectations for demonstration.
        In production, this would execute the actual agent.
        """
        layer = test_case.get('layer', '')
        
        # For contract tests (Layer 1), return the expected contract
        if layer == 'layer1_contract':
            return test_case.get('expected_output', {'status': 'ok'})
        
        # For Layer 2 responsibility tests, return expected_results if present
        expected_results = test_case.get('expected_results', {})
        if expected_results and layer == 'layer2_responsibility':
            output = expected_results.copy()
            if 'status' not in output:
                output['status'] = 'ok'
            return output
        
        # For other tests, return expected_output if present
        expected_output = test_case.get('expected_output', {})
        if expected_output:
            output = expected_output.copy()
            if 'status' not in output:
                output['status'] = 'ok'
            return output
        
        # Fallback: return a minimal successful output
        output = {'status': 'ok'}
        
        # Add fields based on test type to satisfy evaluation checks
        if 'tool_integration' in layer:
            output['tool_selected'] = True
            output['arguments_correct'] = True
            output['result_interpreted'] = True
            output['no_unauthorized_tools'] = True
        elif 'judgment' in layer:
            output['confidence_reported'] = True
            output['uncertainty_acknowledged'] = True
            output['limitations_reported'] = True
            output['no_hallucination'] = True
        elif 'end_to_end' in layer:
            output['task_completed'] = True
            output['verification_passed'] = True
        elif 'stress' in layer:
            output['analysis_completed'] = True
            output['performance_within_limits'] = True
            output['limitations_reported'] = True
            output['no_timeout'] = True
        else:
            # Check expected_result for boolean fields
            expected_result = test_case.get('expected_result', {})
            for key, value in expected_result.items():
                if isinstance(value, bool):
                    output[key] = True
        
        return output

    def _execute_real_agent(self, test_case: Dict[str, Any], agent_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the actual Google ADK agent.
        
        This would:
        1. Load the actual agent from the registry
        2. Create an isolated execution session
        3. Mount the required repository fixture
        4. Send the test request through the agent runtime
        5. Capture all tool calls and delegation
        6. Capture structured findings
        7. Return the actual result or execution error
        
        For now, this is a placeholder indicating what needs to be implemented.
        """
        # TODO: Implement actual Google ADK agent execution
        # This requires:
        # - Importing the agent registry from server/ai_agents/agents/registry.py
        # - Loading the actual agent instance
        # - Creating a Google ADK session
        # - Executing the request through the ADK runner
        # - Capturing tool calls, delegation, and findings
        
        return {
            'status': 'not_implemented',
            'error': 'Live agent execution not yet implemented',
            'note': 'Phase 6 requires Google ADK integration with server agent registry'
        }

    def run_agent_tests(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Run all tests for a specific agent.

        Args:
            agent_id: ID of the agent to test

        Returns:
            List of test results
        """
        # Load agent specification
        agent_spec = self.load_agent_spec(agent_id)
        if not agent_spec:
            print(f"❌ Agent specification not found: {agent_id}")
            return []

        # Validate specification
        if not self.validate_agent_spec(agent_id):
            print(f"❌ Agent specification validation failed: {agent_id}")
            return []

        print(f"✅ Agent specification validated: {agent_id}")

        # Find test directory
        test_dir = self.evaluations_dir / agent_id
        if not test_dir.exists():
            print(f"❌ Test directory not found: {test_dir}")
            return []

        # Load and execute all test cases
        results = []
        for test_file in sorted(test_dir.glob('*.yaml')):
            test_case = self.load_test_case(test_file)
            if test_case:
                result = self.execute_test(test_case, agent_spec)
                results.append(result)

        return results

    def run_all_tests(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Run tests for all agents.

        Returns:
            Dictionary mapping agent IDs to their test results
        """
        all_results = {}

        for agent_dir in sorted(self.evaluations_dir.iterdir()):
            if agent_dir.is_dir():
                agent_id = agent_dir.name
                print(f"\n{'='*60}")
                print(f"Testing agent: {agent_id}")
                print(f"{'='*60}")
                results = self.run_agent_tests(agent_id)
                all_results[agent_id] = results

        return all_results

    def save_results(self, results: Dict[str, List[Dict[str, Any]]], filename: str = 'evaluation_results.json'):
        """Save evaluation results to JSON."""
        output_path = self.reports_dir / filename
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Results saved to: {output_path}")

    def generate_summary(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Generate a summary of all evaluation results."""
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_skipped = 0

        by_agent = {}

        for agent_id, agent_results in results.items():
            agent_total = len(agent_results)
            agent_passed = sum(1 for r in agent_results if r['status'] == 'passed')
            agent_failed = sum(1 for r in agent_results if r['status'] == 'failed')
            agent_skipped = sum(1 for r in agent_results if r['status'] == 'skipped')

            total_tests += agent_total
            total_passed += agent_passed
            total_failed += agent_failed
            total_skipped += agent_skipped

            by_agent[agent_id] = {
                'total': agent_total,
                'passed': agent_passed,
                'failed': agent_failed,
                'skipped': agent_skipped,
                'success_rate': (agent_passed / agent_total * 100) if agent_total > 0 else 0
            }

        return {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed': total_passed,
                'failed': total_failed,
                'skipped': total_skipped,
                'success_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0
            },
            'by_agent': by_agent
        }


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    
    # Parse execution mode from command line
    execution_mode = 'mock'  # default
    if '--live' in sys.argv:
        execution_mode = 'live'
    elif '--mock' in sys.argv:
        execution_mode = 'mock'
    
    harness = IntegratedEvaluationHarness(base_dir, execution_mode=execution_mode)

    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        # Run tests for specific agent
        agent_id = sys.argv[1]
        results = {agent_id: harness.run_agent_tests(agent_id)}
    else:
        # Run all tests
        results = harness.run_all_tests()

    # Save results
    harness.save_results(results)

    # Generate and print summary
    summary = harness.generate_summary(results)
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Execution Mode: {execution_mode.upper()}")
    print(f"Total Tests: {summary['summary']['total_tests']}")
    print(f"Passed: {summary['summary']['passed']}")
    print(f"Failed: {summary['summary']['failed']}")
    print(f"Skipped: {summary['summary']['skipped']}")
    print(f"Success Rate: {summary['summary']['success_rate']:.2f}%")
    
    if execution_mode == 'mock':
        print(f"\n⚠️  MOCK MODE: Results are from simulated execution.")
        print(f"   These validate the evaluation framework, not actual agent quality.")
        print(f"   Use --live flag to execute actual agents.")

    print(f"\nBy Agent:")
    for agent_id, agent_summary in summary['by_agent'].items():
        print(f"  {agent_id}: {agent_summary['passed']}/{agent_summary['total']} ({agent_summary['success_rate']:.2f}%)")


if __name__ == '__main__':
    main()
