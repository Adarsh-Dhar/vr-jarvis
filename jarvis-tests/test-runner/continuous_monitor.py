#!/usr/bin/env python3
"""
Continuous Monitor
Monitors test results and sends alerts for regressions, failures, and quality issues
"""

import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent))


class ContinuousMonitor:
    """Continuously monitors test results and generates alerts"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.history_dir = test_root / 'test-reports' / 'history'
        self.alerts_dir = test_root / 'test-reports' / 'alerts'
        self.alerts_dir.mkdir(parents=True, exist_ok=True)

    def get_latest_results(self) -> Dict:
        """Get the most recent test results"""
        history_files = sorted(self.history_dir.glob('*.json'), reverse=True)

        if not history_files:
            return None

        with open(history_files[0], 'r') as f:
            return json.load(f)

    def check_for_alerts(self, latest_results: Dict) -> List[Dict]:
        """Check for conditions that should trigger alerts"""
        alerts = []

        # Check 1: Success rate below threshold
        success_rate = latest_results.get('success_rate', 0)
        if success_rate < 0.90:
            alerts.append({
                'type': 'critical',
                'severity': 'high',
                'message': f'Success rate {success_rate:.2%} below 90% threshold',
                'metric': 'success_rate',
                'value': success_rate,
                'threshold': 0.90
            })

        # Check 2: Too many failed tests
        failed_count = latest_results.get('summary', {}).get('failed', 0)
        total_count = latest_results.get('summary', {}).get('total', 0)
        if total_count > 0 and (failed_count / total_count) > 0.10:
            alerts.append({
                'type': 'warning',
                'severity': 'medium',
                'message': f'Failed test rate {failed_count/total_count:.2%} above 10% threshold',
                'metric': 'failed_rate',
                'value': failed_count / total_count,
                'threshold': 0.10
            })

        # Check 3: Regression detection
        previous_results = self._get_previous_results()
        if previous_results:
            prev_rate = previous_results.get('success_rate', 0)
            if success_rate < prev_rate - 0.05:
                alerts.append({
                    'type': 'regression',
                    'severity': 'high',
                    'message': f'Success rate dropped from {prev_rate:.2%} to {success_rate:.2%}',
                    'metric': 'success_rate_regression',
                    'value': success_rate,
                    'previous': prev_rate,
                    'threshold': 0.05
                })

        # Check 4: Performance regression
        current_duration = latest_results.get('duration', 0)
        if previous_results:
            prev_duration = previous_results.get('duration', 0)
            if current_duration > prev_duration * 1.5:
                alerts.append({
                    'type': 'performance',
                    'severity': 'medium',
                    'message': f'Test duration increased from {prev_duration:.2f}s to {current_duration:.2f}s',
                    'metric': 'duration_regression',
                    'value': current_duration,
                    'previous': prev_duration,
                    'threshold': 1.5
                })

        # Check 5: New failures
        current_failed = set(latest_results.get('failed_tests', []))
        if previous_results:
            prev_failed = set(previous_results.get('failed_tests', []))
            new_failures = current_failed - prev_failed
            if new_failures:
                alerts.append({
                    'type': 'new_failures',
                    'severity': 'high',
                    'message': f'{len(new_failures)} new test failures detected',
                    'metric': 'new_failures',
                    'value': len(new_failures),
                    'details': list(new_failures)
                })

        return alerts

    def _get_previous_results(self) -> Dict:
        """Get the previous run results"""
        history_files = sorted(self.history_dir.glob('*.json'), reverse=True)

        if len(history_files) < 2:
            return None

        with open(history_files[1], 'r') as f:
            return json.load(f)

    def save_alerts(self, alerts: List[Dict]):
        """Save alerts to file"""
        timestamp = datetime.now().isoformat()
        alert_file = self.alerts_dir / f"alerts_{timestamp.replace(':', '-')}.json"

        with open(alert_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'alerts': alerts
            }, f, indent=2)

        return alert_file

    def generate_alert_report(self, alerts: List[Dict]) -> str:
        """Generate a human-readable alert report"""
        if not alerts:
            return "✅ No alerts detected. All systems nominal."

        lines = [
            "⚠️  ALERTS DETECTED",
            "=" * 50,
            f"Generated: {datetime.now().isoformat()}",
            f"Total Alerts: {len(alerts)}",
            ""
        ]

        for alert in alerts:
            severity_emoji = {
                'high': '🔴',
                'medium': '🟡',
                'low': '🟢'
            }

            lines.append(f"{severity_emoji.get(alert['severity'], '⚪')} [{alert['type'].upper()}] {alert['message']}")

            if 'details' in alert:
                lines.append(f"  Details: {alert['details']}")

            lines.append("")

        return "\n".join(lines)

    def monitor_and_alert(self):
        """Run monitoring and generate alerts"""
        latest_results = self.get_latest_results()

        if not latest_results:
            print("No test results found. Cannot monitor.")
            return

        alerts = self.check_for_alerts(latest_results)

        if alerts:
            self.save_alerts(alerts)
            report = self.generate_alert_report(alerts)
            print(report)
        else:
            print("✅ No alerts detected")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Continuous monitoring and alerting')
    parser.add_argument('--monitor', action='store_true', help='Run monitoring and generate alerts')

    args = parser.parse_args()

    test_root = Path(__file__).parent.parent
    monitor = ContinuousMonitor(test_root)

    if args.monitor:
        monitor.monitor_and_alert()


if __name__ == '__main__':
    main()
