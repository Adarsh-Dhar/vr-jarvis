"""
Report Generator
Produces detailed test reports
"""

from pathlib import Path
from typing import Dict, Optional
import json
import time
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent))


class ReportGenerator:
    """Generates detailed test reports"""
    
    def __init__(self, test_root: Path):
        self.test_root = Path(test_root).absolute()
        self.reports_dir = self.test_root / 'test-reports'
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(self, run_data: Dict) -> Path:
        """Generate a detailed report from test run data"""
        report = {
            'run_id': run_data.get('run_id'),
            'timestamp': datetime.utcnow().isoformat(),
            'summary': run_data.get('summary'),
            'duration': run_data.get('duration'),
            'success_rate': run_data.get('success_rate'),
            'failed_tests': run_data.get('failed_tests', []),
            'error_tests': run_data.get('error_tests', []),
            'detailed_results': run_data.get('results', {})
        }
        
        # Save report
        report_path = self.reports_dir / f"report_{run_data.get('run_id')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report_path
    
    def generate_html_report(self, run_data: Dict) -> Path:
        """Generate an HTML report"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>JARVIS Test Report - {run_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .error {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>JARVIS Test Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p>Run ID: {run_id}</p>
        <p>Timestamp: {timestamp}</p>
        <p>Duration: {duration:.2f}s</p>
        <p>Total Tests: {total}</p>
        <p class="passed">Passed: {passed}</p>
        <p class="failed">Failed: {failed}</p>
        <p class="error">Errors: {errors}</p>
        <p>Success Rate: {success_rate:.2%}</p>
    </div>
    <h2>Test Results</h2>
    <table>
        <tr>
            <th>Test ID</th>
            <th>Status</th>
            <th>Duration (ms)</th>
        </tr>
        {results_rows}
    </table>
</body>
</html>
"""
        
        # Generate results rows
        results_rows = ""
        for test_id, result in run_data.get('results', {}).items():
            status = result.get('status', 'unknown')
            duration = result.get('duration_ms', 0)
            row_class = status
            results_rows += f'<tr><td>{test_id}</td><td class="{row_class}">{status}</td><td>{duration}</td></tr>'
        
        html_content = html_template.format(
            run_id=run_data.get('run_id'),
            timestamp=datetime.utcnow().isoformat(),
            duration=run_data.get('duration', 0),
            total=run_data.get('summary', {}).get('total', 0),
            passed=run_data.get('summary', {}).get('passed', 0),
            failed=run_data.get('summary', {}).get('failed', 0),
            errors=run_data.get('summary', {}).get('errors', 0),
            success_rate=run_data.get('success_rate', 0),
            results_rows=results_rows
        )
        
        # Save HTML report
        html_path = self.reports_dir / f"report_{run_data.get('run_id')}.html"
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        return html_path
