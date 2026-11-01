"""
Regression Detector (Improved)
Compares each run to the previous release baseline and names newly failing specs.
Flags a deliberately broken tool.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).parent))


class RegressionDetector:
    """Detects test regressions by comparing with release baselines"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.history_dir = test_root / 'test-reports' / 'history'
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_dir = test_root / 'test-reports' / 'baselines'
        self.baseline_dir.mkdir(parents=True, exist_ok=True)

    def save_result(self, run_result: Dict):
        """Save a test result to history"""
        timestamp = datetime.now().isoformat()
        history_file = self.history_dir / f"{run_result.get('run_id', timestamp)}.json"

        with open(history_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'run_id': run_result.get('run_id'),
                'version': run_result.get('version', 'dev'),
                'summary': run_result.get('summary'),
                'success_rate': run_result.get('success_rate'),
                'failed_tests': run_result.get('failed_tests', []),
                'error_tests': run_result.get('error_tests', []),
                'duration': run_result.get('duration'),
                'tool_results': run_result.get('tool_results', {})
            }, f, indent=2)

        return history_file

    def set_baseline(self, version: str, run_result: Dict):
        """Set a release baseline for a specific version"""
        baseline_file = self.baseline_dir / f"baseline-{version}.json"

        with open(baseline_file, 'w') as f:
            json.dump({
                'version': version,
                'timestamp': datetime.now().isoformat(),
                'run_id': run_result.get('run_id'),
                'summary': run_result.get('summary'),
                'success_rate': run_result.get('success_rate'),
                'passed_tests': run_result.get('passed_tests', []),
                'failed_tests': run_result.get('failed_tests', []),
                'error_tests': run_result.get('error_tests', []),
                'tool_results': run_result.get('tool_results', {})
            }, f, indent=2)

        return baseline_file

    def get_baseline(self, version: str) -> Optional[Dict]:
        """Get the baseline for a specific version"""
        baseline_file = self.baseline_dir / f"baseline-{version}.json"
        if not baseline_file.exists():
            return None

        with open(baseline_file, 'r') as f:
            return json.load(f)

    def get_previous_results(self, limit: int = 5) -> List[Dict]:
        """Get the most recent previous results"""
        history_files = sorted(self.history_dir.glob('*.json'), reverse=True)[:limit]

        results = []
        for history_file in history_files:
            with open(history_file, 'r') as f:
                results.append(json.load(f))

        return results

    def detect_regressions(self, current_result: Dict, baseline_version: Optional[str] = None) -> Dict:
        """
        Detect regressions by comparing with release baseline.
        If baseline_version is provided, compare against that specific baseline.
        Otherwise, compare against the most recent baseline.
        """
        # Determine which baseline to use
        if baseline_version:
            baseline = self.get_baseline(baseline_version)
            if not baseline:
                # Fallback to most recent baseline
                baseline = self._get_most_recent_baseline()
        else:
            baseline = self._get_most_recent_baseline()

        if not baseline:
            return {
                'has_regressions': False,
                'message': 'No baseline to compare against. Run set_baseline first.'
            }

        regressions = {
            'has_regressions': False,
            'baseline_version': baseline.get('version'),
            'baseline_run_id': baseline.get('run_id'),
            'current_run_id': current_result.get('run_id'),
            'baseline_success_rate': baseline.get('success_rate'),
            'current_success_rate': current_result.get('success_rate'),
            'new_failures': [],
            'new_errors': [],
            'broken_tools': [],
            'performance_regressions': [],
            'fixed_tests': []
        }

        # Check for new failures (tests that passed in baseline but fail now)
        baseline_passed = set(baseline.get('passed_tests', []))
        current_failed = set(current_result.get('failed_tests', []))
        new_failures = baseline_passed & current_failed

        if new_failures:
            regressions['has_regressions'] = True
            regressions['new_failures'] = list(new_failures)

        # Check for new errors
        baseline_passed_or_failed = baseline_passed | set(baseline.get('failed_tests', []))
        current_error = set(current_result.get('error_tests', []))
        new_errors = baseline_passed_or_failed & current_error

        if new_errors:
            regressions['has_regressions'] = True
            regressions['new_errors'] = list(new_errors)

        # Check for fixed tests
        baseline_failed = set(baseline.get('failed_tests', []))
        current_passed = set(current_result.get('passed_tests', []))
        fixed_tests = baseline_failed & current_passed

        if fixed_tests:
            regressions['fixed_tests'] = list(fixed_tests)

        # Identify broken tools (tools with many failing tests)
        regressions['broken_tools'] = self._identify_broken_tools(
            current_result.get('tool_results', {}),
            baseline.get('tool_results', {})
        )

        if regressions['broken_tools']:
            regressions['has_regressions'] = True

        # Check success rate regression
        baseline_rate = baseline.get('success_rate', 0)
        current_rate = current_result.get('success_rate', 0)

        if current_rate < baseline_rate - 0.05:  # 5% drop threshold
            regressions['has_regressions'] = True
            regressions['success_rate_drop'] = baseline_rate - current_rate

        # Check duration regression
        baseline_duration = baseline.get('duration', 0)
        current_duration = current_result.get('duration', 0)

        if current_duration > baseline_duration * 1.5:  # 50% slower threshold
            regressions['has_regressions'] = True
            regressions['duration_increase'] = current_duration - baseline_duration

        return regressions

    def _get_most_recent_baseline(self) -> Optional[Dict]:
        """Get the most recent baseline file"""
        baseline_files = sorted(self.baseline_dir.glob('baseline-*.json'), reverse=True)
        if not baseline_files:
            return None

        with open(baseline_files[0], 'r') as f:
            return json.load(f)

    def _identify_broken_tools(self, current_tool_results: Dict, baseline_tool_results: Dict) -> List[Dict]:
        """Identify tools that have broken since the baseline"""
        broken_tools = []

        for tool_name, current_stats in current_tool_results.items():
            baseline_stats = baseline_tool_results.get(tool_name, {})

            # Compare pass rates
            current_pass_rate = current_stats.get('pass_rate', 0)
            baseline_pass_rate = baseline_stats.get('pass_rate', 1.0)

            # A tool is broken if pass rate dropped by 20% or more
            if current_pass_rate <= baseline_pass_rate - 0.20:
                broken_tools.append({
                    'tool': tool_name,
                    'baseline_pass_rate': baseline_pass_rate,
                    'current_pass_rate': current_pass_rate,
                    'drop': baseline_pass_rate - current_pass_rate
                })

        return broken_tools

    def generate_regression_report(self, regressions: Dict) -> str:
        """Generate a human-readable regression report"""
        lines = [
            "Regression Detection Report",
            "=" * 50,
            f"Baseline Version: {regressions.get('baseline_version', 'N/A')}",
            f"Baseline Run: {regressions.get('baseline_run_id', 'N/A')}",
            f"Current Run: {regressions.get('current_run_id', 'N/A')}",
            "",
            f"Baseline Success Rate: {regressions.get('baseline_success_rate', 0):.2%}",
            f"Current Success Rate: {regressions.get('current_success_rate', 0):.2%}",
        ]

        if regressions.get('success_rate_drop'):
            lines.append(f"⚠️  Success Rate Drop: {regressions['success_rate_drop']:.2%}")

        if regressions.get('duration_increase'):
            lines.append(f"⚠️  Duration Increase: {regressions['duration_increase']:.2f}s")

        lines.append("")

        if regressions['broken_tools']:
            lines.append(f"🔨 Broken Tools ({len(regressions['broken_tools'])}):")
            for tool in regressions['broken_tools']:
                lines.append(f"  - {tool['tool']}: {tool['baseline_pass_rate']:.2%} → {tool['current_pass_rate']:.2%} (drop: {tool['drop']:.2%})")
            lines.append("")

        if regressions['new_failures']:
            lines.append(f"❌ New Failures ({len(regressions['new_failures'])}):")
            for test in regressions['new_failures'][:20]:  # Limit to 20
                lines.append(f"  - {test}")
            if len(regressions['new_failures']) > 20:
                lines.append(f"  ... and {len(regressions['new_failures']) - 20} more")
            lines.append("")

        if regressions['new_errors']:
            lines.append(f"⚠️  New Errors ({len(regressions['new_errors'])}):")
            for test in regressions['new_errors'][:20]:
                lines.append(f"  - {test}")
            if len(regressions['new_errors']) > 20:
                lines.append(f"  ... and {len(regressions['new_errors']) - 20} more")
            lines.append("")

        if regressions['fixed_tests']:
            lines.append(f"✅ Fixed Tests ({len(regressions['fixed_tests'])}):")
            for test in regressions['fixed_tests'][:20]:
                lines.append(f"  - {test}")
            if len(regressions['fixed_tests']) > 20:
                lines.append(f"  ... and {len(regressions['fixed_tests']) - 20} more")
            lines.append("")

        if not regressions['has_regressions']:
            lines.append("✅ No regressions detected")
        else:
            lines.append("⚠️  Regressions detected")

        return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Detect test regressions')
    parser.add_argument('--json', type=str, help='Current run JSON result')
    parser.add_argument('--set-baseline', type=str, help='Set current result as baseline for version')
    parser.add_argument('--baseline-version', type=str, help='Compare against specific baseline version')

    args = parser.parse_args()

    test_root = Path(__file__).parent.parent
    detector = RegressionDetector(test_root)

    if args.json:
        with open(args.json, 'r') as f:
            current_result = json.load(f)

        # Save current result
        detector.save_result(current_result)

        # Set baseline if requested
        if args.set_baseline:
            detector.set_baseline(args.set_baseline, current_result)
            print(f"✅ Baseline set for version {args.set_baseline}")
            return 0

        # Detect regressions
        regressions = detector.detect_regressions(current_result, args.baseline_version)

        # Print report
        print(detector.generate_regression_report(regressions))

        # Return exit code
        return 1 if regressions['has_regressions'] else 0
    else:
        print("Usage: regression_detector.py --json <result.json> [--set-baseline <version>] [--baseline-version <version>]")
        return 1


if __name__ == '__main__':
    sys.exit(main())


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Detect test regressions')
    parser.add_argument('--json', type=str, help='Current run JSON result')

    args = parser.parse_args()

    test_root = Path(__file__).parent.parent
    detector = RegressionDetector(test_root)

    if args.json:
        with open(args.json, 'r') as f:
            current_result = json.load(f)

        # Save current result
        detector.save_result(current_result)

        # Detect regressions
        regressions = detector.detect_regressions(current_result)

        # Print report
        print(detector.generate_regression_report(regressions))

        # Return exit code
        return 1 if regressions['has_regressions'] else 0


if __name__ == '__main__':
    sys.exit(main())
