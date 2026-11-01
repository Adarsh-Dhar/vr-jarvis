#!/usr/bin/env python3
"""
JARVIS Test Plan Scoreboard
Computes the weighted rubric score from the test plan.
A point only counts when a test can fail: it must pass against the real tool
and fail against a tool that does nothing.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Tuple
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))


class ScorePlan:
    """Computes the JARVIS test plan score"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.tests_dir = test_root / 'tests'
        self.fixtures_dir = test_root / 'fixtures'
        self.test_runner_dir = test_root / 'test-runner'

    def count_test_files(self) -> Dict[str, int]:
        """Count test files by category - uses plan values for Phase 0"""
        counts = defaultdict(int)

        # Use values from the plan (measured from last upload vr-jarvis-main (24))
        # These would be computed by running the actual test suite in Phase 3
        counts['total_specs'] = 5402  # From plan
        counts['skipped_specs'] = 1509  # From plan: 1,509 of 5,402 skipped (28%)
        counts['placeholder_inputs'] = 5684  # From plan: ~5,684 use placeholder inputs
        counts['status_only_expected'] = 5658  # From plan: ~5,658 expect only status
        counts['absolute_paths'] = 0  # Should be 0 per plan requirements

        return dict(counts)

    def count_verified_tools(self) -> Tuple[int, int]:
        """
        Count verified tools.
        A tool is verified when:
        - Its specs use real inputs (never placeholder)
        - Its expected result is exact (not just status: ok)
        - It passes against the real tool
        - It fails against a do-nothing stub
        - It fails against at least two mutants
        - It runs on a temporary copy
        """
        # From plan: 533 exported tools, only 6 have verified content tests
        return 6, 533

    def count_integration_tests(self) -> Tuple[int, int]:
        """Count integration tests that pass against real infrastructure"""
        # From plan: 12 integration specs, all error out or are skipped
        return 0, 12

    def count_agent_capability_tests(self) -> Tuple[int, int]:
        """Count agent capability tests"""
        # From plan: specs exist but don't pass
        return 0, 5

    def count_multi_agent_tests(self) -> Tuple[int, int]:
        """Count multi-agent coordination tests"""
        # From plan: specs exist but don't pass
        return 0, 4

    def count_end_to_end_tests(self) -> Tuple[int, int]:
        """Count end-to-end investigation tests"""
        # From plan: specs exist but don't pass
        return 0, 3

    def count_stress_tests(self) -> Tuple[int, int]:
        """Count stress tests"""
        # From plan: specs exist but don't pass
        return 0, 9

    def count_fixture_repos(self) -> Tuple[int, int]:
        """Count validated fixture repositories"""
        # From plan: 5 of 7 repos exist and some validated
        return 5, 7

    def check_platform_components(self) -> Dict[str, bool]:
        """Check which platform components exist and work"""
        components = {
            'agent_evaluator': False,  # Not implemented
            'multi_agent_evaluator': False,  # Not implemented
            'load_generator': False,  # Not implemented
            'chaos_controller': False,  # Not implemented
            'performance_monitor': False,  # Not implemented
            'ground_truth_engine': (self.test_runner_dir / 'ground_truth_engine.py').exists(),
            'regression_detector': (self.test_runner_dir / 'regression_detector.py').exists(),
            'release_gate': False,  # Not implemented
            'test_registry': (self.test_runner_dir / 'test_registry.py').exists(),
            'test_orchestrator': (self.test_runner_dir / 'test_orchestrator.py').exists(),
            'test_fixture_manager': (self.test_runner_dir / 'test_fixture_manager.py').exists(),
            'report_generator': (self.test_runner_dir / 'report_generator.py').exists(),
            'mutation_tester': (self.test_runner_dir / 'mutation_tester.py').exists(),
        }

        return components

    def check_metrics(self) -> int:
        """Check which of the 15 metrics are implemented"""
        # From plan: only 0.7 points earned (partial implementation)
        return 1  # Placeholder - would need actual implementation check

    def check_failure_injection(self) -> int:
        """Check failure injection scenarios"""
        # From plan: 0 points earned (12 scenarios not implemented)
        return 0

    def check_test_the_tests(self) -> Dict[str, bool]:
        """Check test-the-tests components"""
        return {
            'mutation_tester': (self.test_runner_dir / 'mutation_tester.py').exists(),
            'metamorphic_tests': False,  # Not implemented
            'differential_tests': False,  # Not implemented
        }

    def check_performance_targets(self) -> bool:
        """Check if performance targets are defined"""
        benchmarks_dir = self.test_root / 'benchmarks'
        return benchmarks_dir.exists() and len(list(benchmarks_dir.glob('*'))) > 0

    def check_tool_completion_tracking(self) -> bool:
        """Check if tool completion status is generated"""
        status_file = self.test_root / 'tool_completion_status.json'
        if not status_file.exists():
            return False

        with open(status_file, 'r') as f:
            data = json.load(f)
            return len(data) > 0

    def compute_score(self) -> Dict:
        """Compute the full score according to the plan's rubric"""
        counts = self.count_test_files()
        verified_tools, total_tools = self.count_verified_tools()
        integration_passing, integration_total = self.count_integration_tests()
        agent_passing, agent_total = self.count_agent_capability_tests()
        multi_agent_passing, multi_agent_total = self.count_multi_agent_tests()
        e2e_passing, e2e_total = self.count_end_to_end_tests()
        stress_passing, stress_total = self.count_stress_tests()
        validated_repos, total_repos = self.count_fixture_repos()
        platform_components = self.check_platform_components()
        metrics_count = self.check_metrics()
        failure_scenarios = self.check_failure_injection()
        test_the_tests = self.check_test_the_tests()
        has_performance_targets = self.check_performance_targets()
        has_tool_completion = self.check_tool_completion_tracking()

        # Compute scores according to plan weights
        score = {
            'layers_1_2_tool_correctness': {
                'weight': 30,
                'earned': 0.5,  # From plan: only 6 tools verified out of 533
                'details': f'{verified_tools} of {total_tools} tools verified'
            },
            'layer_3_integration': {
                'weight': 7,
                'earned': 0,  # All 12 error out or skipped
                'details': f'{integration_passing} of {integration_total} passing'
            },
            'layer_4_agent_capability': {
                'weight': 7,
                'earned': 0,
                'details': f'{agent_passing} of {agent_total} passing'
            },
            'layer_5_multi_agent': {
                'weight': 7,
                'earned': 0,
                'details': f'{multi_agent_passing} of {multi_agent_total} passing'
            },
            'layer_6_end_to_end': {
                'weight': 7,
                'earned': 0,
                'details': f'{e2e_passing} of {e2e_total} passing'
            },
            'layer_7_stress': {
                'weight': 7,
                'earned': 0,
                'details': f'{stress_passing} of {stress_total} passing'
            },
            'test_repositories_ground_truth': {
                'weight': 10,
                'earned': 7.1,  # From plan: 5 of 7 repos exist, some validated
                'details': f'{validated_repos} of {total_repos} repositories validated'
            },
            'testing_platform': {
                'weight': 10,
                'earned': 5.0,  # From plan: 5 of 13 components working
                'details': f'{sum(platform_components.values())} of {len(platform_components)} components present'
            },
            'metrics': {
                'weight': 5,
                'earned': 0.7,  # From plan
                'details': f'{metrics_count} of 15 metrics implemented'
            },
            'failure_injection': {
                'weight': 5,
                'earned': 0,
                'details': f'{failure_scenarios} of 12 scenarios'
            },
            'test_the_tests': {
                'weight': 3,
                'earned': 0,  # Mutation tester exists but not wired, scores 0.0%
                'details': f'Mutation: {test_the_tests["mutation_tester"]}, Metamorphic: {test_the_tests["metamorphic_tests"]}, Differential: {test_the_tests["differential_tests"]}'
            },
            'performance_targets': {
                'weight': 1,
                'earned': 0.2,  # From plan
                'details': f'Targets defined: {has_performance_targets}'
            },
            'tool_completion_tracking': {
                'weight': 1,
                'earned': 0,  # Currently empty {}
                'details': f'Tracking file populated: {has_tool_completion}'
            }
        }

        # Calculate total
        total_weight = sum(item['weight'] for item in score.values())
        total_earned = sum(item['earned'] for item in score.values())
        total_percentage = (total_earned / total_weight) * 100

        score['summary'] = {
            'total_weight': total_weight,
            'total_earned': total_earned,
            'percentage': total_percentage
        }

        # Add raw counts
        score['raw_counts'] = counts

        return score

    def print_score_table(self, score: Dict):
        """Print the score table in the format from section 1"""
        print("\nJARVIS Test Plan Scoreboard")
        print("=" * 80)
        print("\nPart of the plan | Weight | Now | Still to earn")
        print("-" * 80)

        sections = [
            ('Layers 1 and 2: tool correctness', 'layers_1_2_tool_correctness'),
            ('Layer 3: integration', 'layer_3_integration'),
            ('Layer 4: agent capability', 'layer_4_agent_capability'),
            ('Layer 5: multi-agent coordination', 'layer_5_multi_agent'),
            ('Layer 6: end-to-end investigations', 'layer_6_end_to_end'),
            ('Layer 7: full-system stress', 'layer_7_stress'),
            ('Test repositories and ground truth', 'test_repositories_ground_truth'),
            ('Testing platform (13 components)', 'testing_platform'),
            ('15 metrics', 'metrics'),
            ('Failure injection (12 scenarios)', 'failure_injection'),
            ('Test the tests (mutation, metamorphic, differential)', 'test_the_tests'),
            ('Performance targets and benchmarks', 'performance_targets'),
            ('Tool completion tracking and compatibility matrix', 'tool_completion_tracking'),
        ]

        for name, key in sections:
            item = score[key]
            remaining = item['weight'] - item['earned']
            print(f"{name:45} | {item['weight']:6} | {item['earned']:5.1f} | {remaining:13.1f}")

        print("-" * 80)
        summary = score['summary']
        print(f"{'Total':45} | {summary['total_weight']:6} | {summary['total_earned']:5.1f} | {summary['total_weight'] - summary['total_earned']:13.1f}")
        print(f"\nOverall Score: {summary['percentage']:.1f}%")
        print("\n" + "=" * 80)

        # Print key measured facts
        print("\nKey Measured Facts:")
        print("-" * 80)
        counts = score['raw_counts']
        print(f"- Total test specs: {counts.get('total_specs', 0)}")
        print(f"- Skipped specs: {counts.get('skipped_specs', 0)} ({counts.get('skipped_specs', 0) / max(counts.get('total_specs', 1), 1) * 100:.1f}%)")
        print(f"- Specs with placeholder inputs: {counts.get('placeholder_inputs', 0)}")
        print(f"- Specs with status-only expected: {counts.get('status_only_expected', 0)}")
        print(f"- Specs with absolute paths: {counts.get('absolute_paths', 0)}")
        print("\n" + "=" * 80)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Compute JARVIS test plan score')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    scorer = ScorePlan(test_root)

    score = scorer.compute_score()

    if args.json:
        print(json.dumps(score, indent=2))
    else:
        scorer.print_score_table(score)


if __name__ == '__main__':
    main()
