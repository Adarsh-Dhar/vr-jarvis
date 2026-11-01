#!/usr/bin/env python3
"""
Multi-Agent Evaluator
Records which agent did what and when.
Checks delegation, parallel vs sequential execution, duplicate work and overwritten findings.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))


class MultiAgentEvaluator:
    """Evaluates multi-agent coordination"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.reports_dir = test_root / 'test-reports' / 'multi-agent-evaluations'
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def evaluate_coordination(self, agent_actions: List[Dict]) -> Dict:
        """
        Evaluate multi-agent coordination.
        
        Args:
            agent_actions: List of agent actions with timestamps
                [{'agent': 'agent1', 'action': 'tool_call', 'tool': 'read_file', 'timestamp': ...}, ...]
        
        Returns:
            Evaluation results
        """
        evaluation = {
            'timestamp': datetime.now().isoformat(),
            'delegation_score': 0.0,
            'parallelization_score': 0.0,
            'duplicate_work_score': 0.0,
            'conflict_score': 0.0,
            'overall_score': 0.0,
            'details': {}
        }

        # Group actions by agent
        actions_by_agent = defaultdict(list)
        for action in agent_actions:
            actions_by_agent[action['agent']].append(action)

        # 1. Delegation Score
        # Check if work was appropriately delegated among agents
        delegated_tasks = set()
        for agent, actions in actions_by_agent.items():
            for action in actions:
                task_id = action.get('task_id')
                if task_id:
                    delegated_tasks.add(task_id)

        # Good delegation: different agents work on different tasks
        delegation_score = 1.0 if len(delegated_tasks) > 0 else 0.0
        evaluation['delegation_score'] = delegation_score
        evaluation['details']['delegated_tasks'] = len(delegated_tasks)

        # 2. Parallelization Score
        # Check if agents worked in parallel where possible
        timestamps = [a['timestamp'] for a in agent_actions if 'timestamp' in a]
        if len(timestamps) > 1:
            # Check for overlapping time windows
            sorted_times = sorted(timestamps)
            overlapping_pairs = 0
            for i in range(len(sorted_times) - 1):
                if sorted_times[i + 1] - sorted_times[i] < 1.0:  # Within 1 second
                    overlapping_pairs += 1
            
            parallelization_score = overlapping_pairs / (len(timestamps) - 1) if len(timestamps) > 1 else 0.0
        else:
            parallelization_score = 0.0

        evaluation['parallelization_score'] = parallelization_score
        evaluation['details']['parallel_opportunities'] = len(timestamps) - 1 if timestamps else 0

        # 3. Duplicate Work Score
        # Check if multiple agents worked on the same task
        task_assignments = defaultdict(set)
        for action in agent_actions:
            task_id = action.get('task_id')
            agent = action.get('agent')
            if task_id and agent:
                task_assignments[task_id].add(agent)

        duplicate_tasks = sum(1 for agents in task_assignments.values() if len(agents) > 1)
        total_tasks = len(task_assignments)
        duplicate_score = 1.0 - (duplicate_tasks / total_tasks) if total_tasks > 0 else 1.0

        evaluation['duplicate_work_score'] = duplicate_score
        evaluation['details']['duplicate_tasks'] = duplicate_tasks

        # 4. Conflict Score
        # Check if one agent overwrote another's finding
        findings = {}
        for action in agent_actions:
            if action.get('action') == 'record_finding':
                key = action.get('finding_key')
                agent = action.get('agent')
                if key in findings and findings[key] != agent:
                    # Conflict: different agent overwrote finding
                    evaluation['details']['conflicts'] = evaluation['details'].get('conflicts', [])
                    evaluation['details']['conflicts'].append({
                        'key': key,
                        'original_agent': findings[key],
                        'overwriting_agent': agent
                    })

                findings[key] = agent

        conflict_score = 1.0 if not evaluation['details'].get('conflicts') else 0.0
        evaluation['conflict_score'] = conflict_score

        # Overall Score
        evaluation['overall_score'] = (
            evaluation['delegation_score'] * 0.3 +
            evaluation['parallelization_score'] * 0.2 +
            evaluation['duplicate_work_score'] * 0.3 +
            evaluation['conflict_score'] * 0.2
        )

        return evaluation

    def detect_overwriting_agent(self, evaluation: Dict) -> bool:
        """
        Detect if an agent overwrites another's verified finding.
        Returns True if conflicts detected.
        """
        return evaluation['conflict_score'] < 1.0

    def save_evaluation(self, evaluation: Dict):
        """Save evaluation to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"multi_agent_{timestamp}.json"
        filepath = self.reports_dir / filename

        with open(filepath, 'w') as f:
            json.dump(evaluation, f, indent=2)

        return filepath

    def generate_report(self, evaluation: Dict) -> str:
        """Generate a human-readable report"""
        lines = [
            "Multi-Agent Coordination Evaluation Report",
            "=" * 80,
            f"Generated: {datetime.now().isoformat()}",
            "",
            f"Overall Score: {evaluation['overall_score']:.2%}",
            f"Delegation: {evaluation['delegation_score']:.2%}",
            f"Parallelization: {evaluation['parallelization_score']:.2%}",
            f"No Duplicate Work: {evaluation['duplicate_work_score']:.2%}",
            f"No Conflicts: {evaluation['conflict_score']:.2%}",
            ""
        ]

        if evaluation['details'].get('conflicts'):
            lines.append("⚠️  CONFLICTS DETECTED:")
            for conflict in evaluation['details']['conflicts']:
                lines.append(f"  - Finding '{conflict['key']}' overwritten by {conflict['overwriting_agent']} (original: {conflict['original_agent']})")
            lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Evaluate multi-agent coordination')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')
    parser.add_argument('--mock', action='store_true',
                        help='Run with mock data for testing')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    evaluator = MultiAgentEvaluator(test_root)

    if args.mock:
        # Mock evaluation for testing
        agent_actions = [
            {'agent': 'agent1', 'action': 'tool_call', 'tool': 'read_file', 'task_id': 'task1', 'timestamp': 0.0},
            {'agent': 'agent2', 'action': 'tool_call', 'tool': 'find_callers', 'task_id': 'task2', 'timestamp': 0.5},
            {'agent': 'agent1', 'action': 'record_finding', 'finding_key': 'symbol_alpha', 'timestamp': 1.0},
            {'agent': 'agent2', 'action': 'record_finding', 'finding_key': 'symbol_beta', 'timestamp': 1.5}
        ]

        evaluation = evaluator.evaluate_coordination(agent_actions)
        evaluator.save_evaluation(evaluation)
        print(evaluator.generate_report(evaluation))
    else:
        print("Multi-agent evaluator ready. Use with actual agent execution data.")
        print("Mock mode: python3 multi_agent_evaluator.py --mock")

    sys.exit(0)


if __name__ == '__main__':
    main()
