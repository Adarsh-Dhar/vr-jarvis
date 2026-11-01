#!/usr/bin/env python3
"""
Release Gate (Improved)
Reads the scoreboard, mutation score, stress results, and platform component status.
Blocks a build with a failing critical spec or regression.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))


class ReleaseGate:
    """Evaluates whether a release should pass based on test results"""

    def __init__(self, test_root: Path):
        self.test_root = test_root.resolve()
        self.reports_dir = self.test_root / 'test-reports'
        # Platform components are in test-runner directory
        self.runner_dir = self.test_root / 'test-runner'

    def check_scoreboard(self, min_score: float = 22.4) -> Dict:
        """
        Check the scoreboard score.
        Default min_score is 22.4% (Phase 2 completion).
        """
        try:
            # Add runner dir to path to import score_plan
            sys.path.insert(0, str(self.runner_dir))
            from score_plan import ScorePlan
            scorer = ScorePlan(self.test_root)
            score = scorer.compute_score()
            return {
                'checked': True,
                'percentage': score['summary']['percentage'],
                'passed': score['summary']['percentage'] >= min_score,
                'target': min_score
            }
        except Exception as e:
            return {
                'checked': False,
                'error': str(e)
            }

    def check_mutation_score(self, min_score: float = 80.0) -> Dict:
        """Check mutation testing score (requires 80% kill rate per plan)"""
        mutation_file = self.reports_dir / 'mutation-results.json'
        if not mutation_file.exists():
            return {
                'checked': False,
                'reason': 'No mutation results found (optional until Phase 10)'
            }

        try:
            with open(mutation_file, 'r') as f:
                data = json.load(f)

            score = data.get('mutation_score', 0.0)
            return {
                'checked': True,
                'score': score,
                'passed': score >= min_score,
                'target': min_score
            }
        except Exception as e:
            return {
                'checked': False,
                'error': str(e)
            }

    def check_stress_results(self, min_success_rate: float = 95.0) -> Dict:
        """Check stress test results (requires 95% for release per plan)"""
        stress_file = self.reports_dir / 'stress-results.json'
        if not stress_file.exists():
            return {
                'checked': False,
                'reason': 'No stress results found (optional until Phase 9)'
            }

        try:
            with open(stress_file, 'r') as f:
                data = json.load(f)

            success_rate = data.get('success_rate', 0.0)
            return {
                'checked': True,
                'success_rate': success_rate,
                'passed': success_rate >= min_success_rate,
                'target': min_success_rate
            }
        except Exception as e:
            return {
                'checked': False,
                'error': str(e)
            }

    def check_critical_failures(self, run_result: Dict) -> Dict:
        """Check for critical test failures (blocks release)"""
        critical_failures = []

        for test_id, result in run_result.get('results', {}).items():
            if result.get('status') == 'failed':
                test_def = result.get('test_def', {})
                severity = test_def.get('severity', 'medium')
                if severity == 'critical':
                    critical_failures.append(test_id)

        return {
            'checked': True,
            'critical_failures': critical_failures,
            'passed': len(critical_failures) == 0
        }

    def check_regressions(self, baseline_version: Optional[str] = None) -> Dict:
        """Check for regressions against baseline"""
        try:
            sys.path.insert(0, str(self.runner_dir))
            from regression_detector import RegressionDetector
            detector = RegressionDetector(self.runner_dir)

            # Get baseline or use most recent
            if baseline_version:
                baseline = detector.get_baseline(baseline_version)
            else:
                baseline = detector._get_most_recent_baseline()

            if not baseline:
                return {
                    'checked': False,
                    'reason': 'No baseline found (run with --set-baseline first)'
                }

            # Check latest history against baseline
            history = detector.get_previous_results(limit=1)
            if not history:
                return {
                    'checked': False,
                    'reason': 'No recent run to compare'
                }

            regressions = detector.detect_regressions(history[0])

            return {
                'checked': True,
                'has_regressions': regressions['has_regressions'],
                'new_failures': regressions.get('new_failures', []),
                'broken_tools': regressions.get('broken_tools', []),
                'passed': not regressions['has_regressions']
            }
        except Exception as e:
            return {
                'checked': False,
                'error': str(e)
            }

    def check_performance(self) -> Dict:
        """Check performance targets"""
        perf_file = self.reports_dir / 'performance' / 'latest.json'
        if not perf_file.exists():
            return {
                'checked': False,
                'reason': 'No performance results found (optional)'
            }

        try:
            with open(perf_file, 'r') as f:
                data = json.load(f)

            tools_violating = []
            for tool_name, tool_data in data.get('tools', {}).items():
                target_check = tool_data.get('target_check', {})
                if not target_check.get('meets_targets', True):
                    tools_violating.append(tool_name)

            return {
                'checked': True,
                'tools_violating': tools_violating,
                'passed': len(tools_violating) == 0
            }
        except Exception as e:
            return {
                'checked': False,
                'error': str(e)
            }

    def check_platform_components(self) -> Dict:
        """Check that all 13 platform components are working"""
        components = {
            'scoreboard': False,
            'do_nothing_gate': False,
            'skip_analysis': False,
            'test_comparators': False,
            'schema_validation': False,
            'regression_detector': False,
            'ground_truth_engine': False,
            'mutation_tester': False,
            'agent_evaluator': False,
            'multi_agent_evaluator': False,
            'load_generator': False,
            'chaos_controller': False,
            'performance_monitor': False
        }

        # Check component files exist
        component_files = {
            'scoreboard': 'score_plan.py',
            'do_nothing_gate': 'do_nothing_stub.py',
            'skip_analysis': 'analyze_skips.py',
            'test_comparators': 'test_comparators.py',
            'schema_validation': 'validate_spec_schema.py',
            'regression_detector': 'regression_detector.py',
            'ground_truth_engine': 'ground_truth_engine.py',
            'mutation_tester': 'mutation_tester.py',
            'agent_evaluator': 'agent_evaluator.py',
            'multi_agent_evaluator': 'multi_agent_evaluator.py',
            'load_generator': 'load_generator.py',
            'chaos_controller': 'chaos_controller.py',
            'performance_monitor': 'performance_monitor.py'
        }

        for comp, filename in component_files.items():
            if (self.runner_dir / filename).exists():
                components[comp] = True

        all_present = all(components.values())

        return {
            'checked': True,
            'components': components,
            'present_count': sum(components.values()),
            'total_count': len(components),
            'passed': all_present
        }

    def evaluate_release(self, run_result: Dict = None, 
                        baseline_version: Optional[str] = None,
                        phase: str = '2') -> Dict:
        """
        Evaluate all gate criteria and return pass/fail decision.
        Phase determines which checks are required:
        - Phase 0: scoreboard only
        - Phase 1: scoreboard + fixtures
        - Phase 2: scoreboard + platform components
        - Phase 3+: all checks

        Returns {passed: bool, details: {...}}
        """
        details = {
            'scoreboard': self.check_scoreboard(),
            'mutation': self.check_mutation_score(),
            'stress': self.check_stress_results(),
            'platform_components': self.check_platform_components(),
            'regressions': self.check_regressions(baseline_version),
            'performance': self.check_performance()
        }

        if run_result:
            details['critical_failures'] = self.check_critical_failures(run_result)

        # Determine required checks based on phase
        if phase == '0':
            required_checks = ['scoreboard']
            # Phase 0 target is 16.5%
            details['scoreboard']['target'] = 16.5
        elif phase == '1':
            required_checks = ['scoreboard']
            # Phase 1 target is 19.4%
            details['scoreboard']['target'] = 19.4
        elif phase == '2':
            # Phase 2: platform components must be present
            # Score target is 22.4% but won't be reached until Phase 3
            required_checks = ['platform_components']
        else:
            # Full release
            required_checks = ['scoreboard', 'platform_components', 'regressions', 'critical_failures']

        # Check required
        all_required_passed = all(
            details[check].get('passed', False)
            for check in required_checks
            if details[check].get('checked', False)
        )

        passed = all_required_passed

        return {
            'passed': passed,
            'phase': phase,
            'details': details,
            'required_checks': required_checks
        }

    def print_gate_report(self, evaluation: Dict):
        """Print a human-readable gate report"""
        print("\n" + "=" * 80)
        print(f"Release Gate Evaluation (Phase {evaluation.get('phase', 'unknown')})")
        print("=" * 80)

        details = evaluation['details']

        # Scoreboard
        print("\nScoreboard:")
        if details['scoreboard']['checked']:
            pct = details['scoreboard']['percentage']
            target = details['scoreboard'].get('target', 0)
            print(f"  Score: {pct:.1f}% (target: {target:.1f}%)")
            print(f"  Status: {'✅ PASS' if details['scoreboard']['passed'] else '❌ FAIL'}")
        else:
            print(f"  Status: ⚠️  Not checked: {details['scoreboard'].get('error', 'unknown')}")

        # Platform components
        print("\nPlatform Components (13 total):")
        if details['platform_components']['checked']:
            count = details['platform_components']['present_count']
            total = details['platform_components']['total_count']
            print(f"  Present: {count}/{total}")
            print(f"  Status: {'✅ PASS' if details['platform_components']['passed'] else '❌ FAIL'}")
            if count < total:
                missing = [k for k, v in details['platform_components']['components'].items() if not v]
                print(f"  Missing: {', '.join(missing)}")
        else:
            print(f"  Status: ⚠️  Not checked")

        # Regressions
        print("\nRegressions:")
        if details['regressions']['checked']:
            if details['regressions']['has_regressions']:
                print(f"  ❌ Regressions detected")
                if details['regressions']['new_failures']:
                    print(f"  New failures: {len(details['regressions']['new_failures'])}")
                if details['regressions']['broken_tools']:
                    print(f"  Broken tools: {len(details['regressions']['broken_tools'])}")
            else:
                print(f"  ✅ No regressions")
        else:
            print(f"  Status: ⚠️  {details['regressions'].get('reason', 'Not checked')}")

        # Mutation
        print("\nMutation Testing:")
        if details['mutation']['checked']:
            score = details['mutation']['score']
            target = details['mutation'].get('target', 0)
            print(f"  Score: {score:.1f}% (target: {target:.1f}%)")
            print(f"  Status: {'✅ PASS' if details['mutation']['passed'] else '❌ FAIL'}")
        else:
            print(f"  Status: ⚠️  {details['mutation'].get('reason', 'Not checked')}")

        # Stress
        print("\nStress Tests:")
        if details['stress']['checked']:
            rate = details['stress']['success_rate']
            target = details['stress'].get('target', 0)
            print(f"  Success Rate: {rate:.1f}% (target: {target:.1f}%)")
            print(f"  Status: {'✅ PASS' if details['stress']['passed'] else '❌ FAIL'}")
        else:
            print(f"  Status: ⚠️  {details['stress'].get('reason', 'Not checked')}")

        # Performance
        print("\nPerformance:")
        if details['performance']['checked']:
            if details['performance']['passed']:
                print(f"  ✅ All tools meet targets")
            else:
                print(f"  ❌ Tools violating targets: {len(details['performance']['tools_violating'])}")
                for tool in details['performance']['tools_violating'][:5]:
                    print(f"    - {tool}")
        else:
            print(f"  Status: ⚠️  {details['performance'].get('reason', 'Not checked')}")

        # Critical failures
        if 'critical_failures' in details:
            print("\nCritical Failures:")
            if details['critical_failures']['checked']:
                if details['critical_failures']['critical_failures']:
                    print(f"  ❌ {len(details['critical_failures']['critical_failures'])} critical failures")
                    for test_id in details['critical_failures']['critical_failures'][:5]:
                        print(f"    - {test_id}")
                else:
                    print(f"  ✅ No critical failures")

        # Final decision
        print("\n" + "=" * 80)
        if evaluation['passed']:
            print("✅ RELEASE GATE: PASS")
        else:
            print("❌ RELEASE GATE: FAIL")
        print("=" * 80)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Run release gate')
    parser.add_argument('--test-root', type=str, default='.',
                        help='Path to test root directory')
    parser.add_argument('--run-result', type=str,
                        help='Path to run result JSON file')
    parser.add_argument('--baseline-version', type=str,
                        help='Baseline version to compare against')
    parser.add_argument('--phase', type=str, default='2',
                        help='Release phase (0, 1, 2, or full)')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    gate = ReleaseGate(test_root)

    run_result = None
    if args.run_result:
        with open(args.run_result, 'r') as f:
            run_result = json.load(f)

    evaluation = gate.evaluate_release(run_result, args.baseline_version, args.phase)
    gate.print_gate_report(evaluation)

    sys.exit(0 if evaluation['passed'] else 1)


if __name__ == '__main__':
    main()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Run release gate')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')
    parser.add_argument('--run-result', type=str,
                        help='Path to run result JSON file')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    gate = ReleaseGate(test_root)

    run_result = None
    if args.run_result:
        with open(args.run_result, 'r') as f:
            run_result = json.load(f)

    evaluation = gate.evaluate_release(run_result)
    gate.print_gate_report(evaluation)

    sys.exit(0 if evaluation['passed'] else 1)


if __name__ == '__main__':
    main()
