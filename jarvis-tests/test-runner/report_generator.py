"""
Report Generator
Generates detailed test reports in JSON and HTML formats
"""

import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent))


class ReportGenerator:
    """Generates test reports"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.reports_dir = test_root / 'test-reports'
        self.reports_dir.mkdir(exist_ok=True)

    def generate_report(self, run_result: Dict) -> Path:
        """Generate JSON report"""
        timestamp = datetime.now().isoformat()
        report = {
            'generated_at': timestamp,
            'run_id': run_result.get('run_id'),
            'duration': run_result.get('duration'),
            'summary': run_result.get('summary'),
            'success_rate': run_result.get('success_rate'),
            'failed_tests': run_result.get('failed_tests', []),
            'error_tests': run_result.get('error_tests', []),
            'results': run_result.get('results', {})
        }

        report_path = self.reports_dir / f"report_{run_result.get('run_id', 'latest')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        return report_path

    def generate_html_report(self, run_result: Dict) -> Path:
        """Generate HTML report"""
        timestamp = datetime.now().isoformat()
        summary = run_result.get('summary', {})
        failed_tests = run_result.get('failed_tests', [])
        error_tests = run_result.get('error_tests', [])
        results = run_result.get('results', {})

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>JARVIS Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; }}
        .summary {{ background: #ecf0f1; padding: 20px; margin: 20px 0; }}
        .pass {{ color: #27ae60; font-weight: bold; }}
        .fail {{ color: #e74c3c; font-weight: bold; }}
        .error {{ color: #e67e22; font-weight: bold; }}
        .test {{ margin: 10px 0; padding: 10px; border-left: 4px solid #bdc3c7; }}
        .test.pass {{ border-left-color: #27ae60; }}
        .test.fail {{ border-left-color: #e74c3c; }}
        .test.error {{ border-left-color: #e67e22; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>JARVIS Test Report</h1>
        <p>Generated: {timestamp}</p>
        <p>Run ID: {run_result.get('run_id', 'N/A')}</p>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <table>
            <tr><th>Total Tests</th><td>{summary.get('total', 0)}</td></tr>
            <tr><th>Passed</th><td class="pass">{summary.get('passed', 0)}</td></tr>
            <tr><th>Failed</th><td class="fail">{summary.get('failed', 0)}</td></tr>
            <tr><th>Errors</th><td class="error">{summary.get('errors', 0)}</td></tr>
            <tr><th>Skipped</th><td>{summary.get('skipped', 0)}</td></tr>
            <tr><th>Success Rate</th><td>{run_result.get('success_rate', 0):.2%}</td></tr>
            <tr><th>Duration</th><td>{run_result.get('duration', 0):.2f}s</td></tr>
        </table>
    </div>

    <h2>Failed Tests ({len(failed_tests)})</h2>
"""

        for test_id in failed_tests:
            result = results.get(test_id, {})
            html += f"""
    <div class="test fail">
        <h3>{test_id}</h3>
        <p>Status: {result.get('status', 'unknown')}</p>
        <p>Duration: {result.get('duration_ms', 0)}ms</p>
"""

            if 'failures' in result:
                html += "<p>Failures:</p><ul>"
                for failure in result.get('failures', []):
                    html += f"<li>{failure}</li>"
                html += "</ul>"

            html += "</div>"

        html += f"""
    <h2>Error Tests ({len(error_tests)})</h2>
"""

        for test_id in error_tests:
            result = results.get(test_id, {})
            html += f"""
    <div class="test error">
        <h3>{test_id}</h3>
        <p>Status: {result.get('status', 'unknown')}</p>
        <p>Error: {result.get('error', 'No error message')}</p>
    </div>
"""

        html += """
</body>
</html>
"""

        report_path = self.reports_dir / f"report_{run_result.get('run_id', 'latest')}.html"
        with open(report_path, 'w') as f:
            f.write(html)

        return report_path


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate test reports')
    parser.add_argument('--json', type=str, help='JSON result file')
    parser.add_argument('--html', action='store_true', help='Generate HTML report')

    args = parser.parse_args()

    test_root = Path(__file__).parent.parent
    generator = ReportGenerator(test_root)

    if args.json:
        with open(args.json, 'r') as f:
            run_result = json.load(f)

        json_path = generator.generate_report(run_result)
        print(f"JSON report: {json_path}")

        if args.html:
            html_path = generator.generate_html_report(run_result)
            print(f"HTML report: {html_path}")


if __name__ == '__main__':
    main()
