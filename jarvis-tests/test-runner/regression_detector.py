"""
Regression Detector
Compares current test results with previous runs to detect regressions
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent))


class RegressionDetector:
    """Detects test regressions by comparing with historical results"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.history_dir = test_root / 'test-reports' / 'history'
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_result(self, run_result: Dict):
        """Save a test result to history"""
        timestamp = datetime.now().isoformat()
        history_file = self.history_dir / f"{run_result.get('run_id', timestamp)}.json"

        with open(history_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'run_id': run_result.get('run_id'),
                'summary': run_result.get('summary'),
                'success_rate': run_result.get('success_rate'),
                'failed_tests': run_result.get('failed_tests', []),
                'error_tests': run_result.get('error_tests', []),
                'duration': run_result.get('duration')
            }, f, indent=2)

        return history_file

    def get_previous_results(self, limit: int = 5) -> List[Dict]:
        """Get the most recent previous results"""
        history_files = sorted(self.history_dir.glob('*.json'), reverse=True)[:limit]

        results = []
        for history_file in history_files:
            with open(history_file, 'r') as f:
                results.append(json.load(f))

        return results

    def detect_regressions(self, current_result: Dict) -> Dict:
        """Detect regressions by comparing with previous runs"""
        previous_results = self.get_previous_results(limit=1)

        if not previous_results:
            return {
                'has_regressions': False,
                'message': 'No previous results to compare'
            }

        previous = previous_results[0]

        regressions = {
            'has_regressions': False,
            'previous_run_id': previous.get('run_id'),
            'current_run_id': current_result.get('run_id'),
            'previous_success_rate': previous.get('success_rate'),
            'current_success_rate': current_result.get('success_rate'),
            'new_failures': [],
            'performance_regressions': [],
            'fixed_tests': []
        }

        # Check for new failures
        current_failed = set(current_result.get('failed_tests', []))
        previous_failed = set(previous.get('failed_tests', []))

        new_failures = current_failed - previous_failed
        if new_failures:
            regressions['has_regressions'] = True
            regressions['new_failures'] = list(new_failures)

        # Check for fixed tests
        fixed_tests = previous_failed - current_failed
        if fixed_tests:
            regressions['fixed_tests'] = list(fixed_tests)

        # Check success rate regression
        prev_rate = previous.get('success_rate', 0)
        curr_rate = current_result.get('success_rate', 0)

        if curr_rate < prev_rate - 0.05:  # 5% drop threshold
            regressions['has_regressions'] = True
            regressions['success_rate_drop'] = prev_rate - curr_rate

        # Check duration regression
        prev_duration = previous.get('duration', 0)
        curr_duration = current_result.get('duration', 0)

        if curr_duration > prev_duration * 1.5:  # 50% slower threshold
            regressions['has_regressions'] = True
            regressions['duration_increase'] = curr_duration - prev_duration

        return regressions

    def generate_regression_report(self, regressions: Dict) -> str:
        """Generate a human-readable regression report"""
        lines = [
            "Regression Detection Report",
            "=" * 50,
            f"Previous Run: {regressions.get('previous_run_id', 'N/A')}",
            f"Current Run: {regressions.get('current_run_id', 'N/A')}",
            "",
            f"Previous Success Rate: {regressions.get('previous_success_rate', 0):.2%}",
            f"Current Success Rate: {regressions.get('current_success_rate', 0):.2%}",
        ]

        if regressions.get('success_rate_drop'):
            lines.append(f"⚠️  Success Rate Drop: {regressions['success_rate_drop']:.2%}")

        if regressions.get('duration_increase'):
            lines.append(f"⚠️  Duration Increase: {regressions['duration_increase']:.2f}s")

        lines.append("")

        if regressions['new_failures']:
            lines.append(f"❌ New Failures ({len(regressions['new_failures'])}):")
            for test in regressions['new_failures']:
                lines.append(f"  - {test}")
            lines.append("")

        if regressions['fixed_tests']:
            lines.append(f"✅ Fixed Tests ({len(regressions['fixed_tests'])}):")
            for test in regressions['fixed_tests']:
                lines.append(f"  - {test}")
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
