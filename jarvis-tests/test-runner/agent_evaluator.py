#!/usr/bin/env python3
"""
Agent Evaluator
Captures each agent's tool calls from the ADK event stream.
Scores tool selection, call order, whether every claim cites a real tool result,
and detects agents that invent symbols or relationships.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))


class AgentEvaluator:
    """Evaluates agent behavior and tool usage"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.reports_dir = test_root / 'test-reports' / 'agent-evaluations'
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def evaluate_agent(self, agent_name: str, tool_calls: List[Dict], 
                        expected_tools: Set[str], ground_truth: Dict) -> Dict:
        """
        Evaluate a single agent's performance.
        
        Args:
            agent_name: Name of the agent
            tool_calls: List of tool calls made by the agent
            expected_tools: Set of tools that should be called
            ground_truth: Ground truth data to validate against
        
        Returns:
            Evaluation results with scores
        """
        evaluation = {
            'agent_name': agent_name,
            'timestamp': datetime.now().isoformat(),
            'tool_selection_score': 0.0,
            'call_order_score': 0.0,
            'evidence_score': 0.0,
            'hallucination_score': 0.0,
            'overall_score': 0.0,
            'details': {}
        }

        # 1. Tool Selection Score
        actual_tools = set(call.get('tool') for call in tool_calls if call.get('tool'))
        correct_tools = actual_tools & expected_tools
        extra_tools = actual_tools - expected_tools
        missing_tools = expected_tools - actual_tools

        if expected_tools:
            selection_score = len(correct_tools) / len(expected_tools)
        else:
            selection_score = 1.0 if not actual_tools else 0.0

        evaluation['tool_selection_score'] = selection_score
        evaluation['details']['tool_selection'] = {
            'correct': list(correct_tools),
            'extra': list(extra_tools),
            'missing': list(missing_tools)
        }

        # 2. Call Order Score
        # Check if tools were called in a logical order
        expected_order = list(expected_tools)
        actual_order = [call.get('tool') for call in tool_calls if call.get('tool') in expected_tools]
        
        # Simple check: are expected tools in order?
        order_score = 0.0
        if len(actual_order) > 1:
            correct_position = 0
            for i, tool in enumerate(actual_order):
                if i < len(expected_order) and tool == expected_order[i]:
                    correct_position += 1
            order_score = correct_position / len(actual_order)
        else:
            order_score = 1.0

        evaluation['call_order_score'] = order_score
        evaluation['details']['call_order'] = {
            'expected': expected_order,
            'actual': actual_order
        }

        # 3. Evidence Score
        # Check if every claim cites a real tool result
        claims_with_evidence = 0
        total_claims = 0

        for call in tool_calls:
            output = call.get('output', {})
            if isinstance(output, dict):
                # Check if output references tool results
                if output.get('source') == 'tool_result':
                    claims_with_evidence += 1
                total_claims += 1

        evidence_score = claims_with_evidence / total_claims if total_claims > 0 else 1.0
        evaluation['evidence_score'] = evidence_score
        evaluation['details']['evidence'] = {
            'claims_with_evidence': claims_with_evidence,
            'total_claims': total_claims
        }

        # 4. Hallucination Score
        # Detect invented symbols or relationships
        hallucinations = []
        
        for call in tool_calls:
            output = call.get('output', {})
            if isinstance(output, dict):
                # Check for symbols that don't exist in ground truth
                symbols = output.get('symbols', [])
                gt_symbols = ground_truth.get('functions', {}).keys()
                
                for symbol in symbols:
                    if symbol not in gt_symbols:
                        hallucinations.append(symbol)

        hallucination_score = 1.0 - (len(hallucinations) / len(tool_calls)) if len(tool_calls) > 0 else 1.0
        evaluation['hallucination_score'] = max(0.0, hallucination_score)
        evaluation['details']['hallucinations'] = hallucinations

        # Overall Score (weighted average)
        evaluation['overall_score'] = (
            evaluation['tool_selection_score'] * 0.3 +
            evaluation['call_order_score'] * 0.2 +
            evaluation['evidence_score'] * 0.3 +
            evaluation['hallucination_score'] * 0.2
        )

        return evaluation

    def detect_scripted_agent(self, evaluation: Dict) -> bool:
        """
        Detect if an agent is scripted (invents function results).
        Returns True if the agent appears to be scripted.
        """
        # Heuristics for detecting scripted agents:
        # 1. Low evidence score (claims without tool results)
        # 2. High hallucination score (invented symbols)
        # 3. Perfect tool selection but no actual tool calls

        if evaluation['evidence_score'] < 0.5:
            return True
        
        if evaluation['hallucination_score'] < 0.8:
            return True

        return False

    def save_evaluation(self, evaluation: Dict):
        """Save evaluation to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{evaluation['agent_name']}_{timestamp}.json"
        filepath = self.reports_dir / filename

        with open(filepath, 'w') as f:
            json.dump(evaluation, f, indent=2)

        return filepath

    def generate_report(self, evaluations: List[Dict]) -> str:
        """Generate a human-readable report"""
        lines = [
            "Agent Evaluation Report",
            "=" * 80,
            f"Generated: {datetime.now().isoformat()}",
            f"Total Agents Evaluated: {len(evaluations)}",
            ""
        ]

        for eval in evaluations:
            lines.append(f"Agent: {eval['agent_name']}")
            lines.append(f"  Overall Score: {eval['overall_score']:.2%}")
            lines.append(f"  Tool Selection: {eval['tool_selection_score']:.2%}")
            lines.append(f"  Call Order: {eval['call_order_score']:.2%}")
            lines.append(f"  Evidence: {eval['evidence_score']:.2%}")
            lines.append(f"  Hallucination: {eval['hallucination_score']:.2%}")

            if self.detect_scripted_agent(eval):
                lines.append(f"  ⚠️  WARNING: Agent appears to be scripted (invents results)")

            lines.append("")

        # Summary
        avg_score = sum(e['overall_score'] for e in evaluations) / len(evaluations) if evaluations else 0
        lines.append("=" * 80)
        lines.append(f"Average Score: {avg_score:.2%}")
        lines.append("=" * 80)

        return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Evaluate agent performance')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')
    parser.add_argument('--agent', type=str,
                        help='Agent name to evaluate')
    parser.add_argument('--mock', action='store_true',
                        help='Run with mock data for testing')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    evaluator = AgentEvaluator(test_root)

    if args.mock:
        # Mock evaluation for testing
        tool_calls = [
            {'tool': 'read_file', 'output': {'source': 'tool_result', 'symbols': ['alpha', 'beta']}},
            {'tool': 'find_callers', 'output': {'source': 'tool_result', 'symbols': ['target']}}
        ]
        expected_tools = {'read_file', 'find_callers'}
        ground_truth = {'functions': {'alpha': {}, 'beta': {}, 'target': {}}}

        evaluation = evaluator.evaluate_agent('test_agent', tool_calls, expected_tools, ground_truth)
        evaluator.save_evaluation(evaluation)
        print(evaluator.generate_report([evaluation]))
    else:
        print("Agent evaluator ready. Use with actual agent execution data.")
        print("Mock mode: python3 agent_evaluator.py --mock")

    sys.exit(0)


if __name__ == '__main__':
    main()
