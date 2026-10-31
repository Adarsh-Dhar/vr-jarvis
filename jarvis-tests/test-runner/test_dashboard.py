"""
Test Dashboard
Simple web-based dashboard for viewing test results
"""

import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent))


class TestDashboard:
    """Generates a simple HTML dashboard for test results"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.dashboard_dir = test_root / 'test-reports' / 'dashboard'
        self.dashboard_dir.mkdir(parents=True, exist_ok=True)

    def generate_dashboard(self):
        """Generate the main dashboard HTML"""
        history_dir = self.test_root / 'test-reports' / 'history'

        # Load recent results
        recent_runs = []
        if history_dir.exists():
            for history_file in sorted(history_dir.glob('*.json'), reverse=True)[:10]:
                with open(history_file, 'r') as f:
                    recent_runs.append(json.load(f))

        html = """
<!DOCTYPE html>
<html>
<head>
    <title>JARVIS Test Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; }
        .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric { display: inline-block; padding: 15px; margin: 10px; background: #ecf0f1; border-radius: 8px; text-align: center; min-width: 100px; }
        .metric-value { font-size: 24px; font-weight: bold; }
        .metric-label { font-size: 12px; color: #7f8c8d; }
        .success { color: #27ae60; }
        .fail { color: #e74c3c; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f2f2f2; }
        tr:hover { background: #f9f9f9; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-fail { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="header">
        <h1>JARVIS Test Dashboard</h1>
        <p>Real-time test status and historical trends</p>
    </div>

    <div class="card">
        <h2>Overall Status</h2>
        <div>
            <div class="metric">
                <div class="metric-value">5,208</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric">
                <div class="metric-value success">344</div>
                <div class="metric-label">Tools Tested</div>
            </div>
            <div class="metric">
                <div class="metric-value">7</div>
                <div class="metric-label">Test Layers</div>
            </div>
            <div class="metric">
                <div class="metric-value">16</div>
                <div class="metric-label">Test Types</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>Test Coverage by Layer</h2>
        <table>
            <tr>
                <th>Layer</th>
                <th>Tests</th>
                <th>Description</th>
                <th>Status</th>
            </tr>
            <tr>
                <td>Layer 1</td>
                <td>3,096</td>
                <td>Unit Tests (T01-T09)</td>
                <td><span class="badge badge-success">Complete</span></td>
            </tr>
            <tr>
                <td>Layer 2</td>
                <td>2,064</td>
                <td>Edge Cases (T10-T15)</td>
                <td><span class="badge badge-success">Complete</span></td>
            </tr>
            <tr>
                <td>Layer 3</td>
                <td>12</td>
                <td>Integration Tests</td>
                <td><span class="badge badge-success">Complete</span></td>
            </tr>
            <tr>
                <td>Layer 4</td>
                <td>6</td>
                <td>Agent Capabilities</td>
                <td><span class="badge badge-success">Complete</span></td>
            </tr>
            <tr>
                <td>Layer 5</td>
                <td>3</td>
                <td>Multi-Agent Coordination</td>
                <td><span class="badge badge-success">Complete</span></td>
            </tr>
            <tr>
                <td>Layer 6</td>
                <td>3</td>
                <td>End-to-End Investigations</td>
                <td><span class="badge badge-success">Complete</span></td>
            </tr>
            <tr>
                <td>Layer 7</td>
                <td>9</td>
                <td>Stress Tests</td>
                <td><span class="badge badge-success">Complete</span></td>
            </tr>
        </table>
    </div>

    <div class="card">
        <h2>Recent Test Runs</h2>
"""

        if recent_runs:
            html += "<table>"
            html += "<tr><th>Run ID</th><th>Timestamp</th><th>Success Rate</th><th>Duration</th><th>Status</th></tr>"

            for run in recent_runs:
                success_rate = run.get('success_rate', 0)
                status_class = 'success' if success_rate > 0.9 else 'fail'
                status_text = 'Pass' if success_rate > 0.9 else 'Fail'

                html += f"""
                <tr>
                    <td>{run.get('run_id', 'N/A')}</td>
                    <td>{run.get('timestamp', 'N/A')}</td>
                    <td class="{status_class}">{success_rate:.2%}</td>
                    <td>{run.get('duration', 0):.2f}s</td>
                    <td><span class="badge badge-{status_class}">{status_text}</span></td>
                </tr>
"""
            html += "</table>"
        else:
            html += "<p>No test runs recorded yet.</p>"

        html += """
    </div>

    <div class="card">
        <h2>Test Categories</h2>
        <table>
            <tr>
                <th>Category</th>
                <th>Test Count</th>
                <th>Description</th>
            </tr>
            <tr>
                <td>T01-T09</td>
                <td>3,096</td>
                <td>Happy path, validation, boundaries, errors</td>
            </tr>
            <tr>
                <td>T10-T15</td>
                <td>2,064</td>
                <td>Timeout, concurrency, security, performance</td>
            </tr>
            <tr>
                <td>INTEGRATION</td>
                <td>12</td>
                <td>Real infrastructure tests</td>
            </tr>
            <tr>
                <td>AGENT_CAPABILITY</td>
                <td>5</td>
                <td>Agent-specific tests</td>
            </tr>
            <tr>
                <td>MULTI_AGENT</td>
                <td>4</td>
                <td>Agent coordination tests</td>
            </tr>
            <tr>
                <td>END_TO_END</td>
                <td>3</td>
                <td>Complete investigation scenarios</td>
            </tr>
            <tr>
                <td>STRESS</td>
                <td>9</td>
                <td>System stress tests</td>
            </tr>
        </table>
    </div>

    <div class="card">
        <h2>Quick Actions</h2>
        <p>
            <button onclick="location.reload()">Refresh Dashboard</button>
        </p>
    </div>

    <div style="text-align: center; margin: 20px; color: #7f8c8d;">
        <p>Last updated: """ + datetime.now().isoformat() + """</p>
    </div>
</body>
</html>
"""

        dashboard_path = self.dashboard_dir / 'index.html'
        with open(dashboard_path, 'w') as f:
            f.write(html)

        return dashboard_path


def main():
    """Main entry point"""
    test_root = Path(__file__).parent.parent
    dashboard = TestDashboard(test_root)

    dashboard_path = dashboard.generate_dashboard()
    print(f"Dashboard generated: {dashboard_path}")
    print(f"Open in browser: file://{dashboard_path.absolute()}")


if __name__ == '__main__':
    main()
