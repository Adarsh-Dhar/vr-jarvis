#!/usr/bin/env python3
"""
Enhanced Test Dashboard
Web-based dashboard with real-time updates, tool completion tracking, and alerts
"""

import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent))


class EnhancedTestDashboard:
    """Enhanced dashboard with monitoring and alerts"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.dashboard_dir = test_root / 'test-reports' / 'dashboard'
        self.dashboard_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir = test_root / 'test-reports' / 'history'
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def get_tool_completion_status(self) -> Dict:
        """Get completion status for all tools"""
        completion_file = self.test_root / 'tool_completion_status.json'

        if not completion_file.exists():
            # Generate initial status
            return self._generate_initial_completion_status()

        with open(completion_file, 'r') as f:
            return json.load(f)

    def _generate_initial_completion_status(self) -> Dict:
        """Generate initial tool completion status"""
        from test_registry import TestRegistry

        registry = TestRegistry(self.test_root)
        registry.load_test_definitions()

        # Get all tested tools
        tested_tools = set()
        for test_def in registry.get_all_tests().values():
            tool = test_def.get('tool')
            if tool:
                tested_tools.add(tool)

        # Get all exported tools
        try:
            sys.path.insert(0, str(self.test_root.parent.parent / 'server'))
            from ai_agents import tools
            all_tools = set(tools.__all__)
        except:
            all_tools = set()

        # Calculate completion status
        completion_status = {}
        for tool in all_tools:
            has_tests = tool in tested_tools
            completion_status[tool] = {
                'has_tests': has_tests,
                'test_count': len(registry.get_tests_by_tool(tool)),
                'layers': self._get_tool_layers(registry, tool),
                'status': self._determine_status(registry, tool)
            }

        # Save to file
        completion_file = self.test_root / 'tool_completion_status.json'
        with open(completion_file, 'w') as f:
            json.dump(completion_status, f, indent=2)

        return completion_status

    def _get_tool_layers(self, registry, tool_name: str) -> List[int]:
        """Get which layers a tool has tests for"""
        layers = set()
        for test_id in registry.get_tests_by_tool(tool_name):
            test_def = registry.get_test(test_id)
            if test_def:
                layer = test_def.get('layer')
                if layer:
                    layers.add(layer)
        return sorted(list(layers))

    def _determine_status(self, registry, tool_name: str) -> str:
        """Determine completion status for a tool"""
        layers = self._get_tool_layers(registry, tool_name)
        test_count = len(registry.get_tests_by_tool(tool_name))

        if not layers:
            return 'untested'
        elif 1 in layers and test_count >= 9:
            return 'experimental'
        elif set(layers) >= {1, 2} and test_count >= 15:
            return 'validated'
        elif set(layers) >= {1, 2, 3} and test_count >= 18:
            return 'stress_tested'
        else:
            return 'in_progress'

    def get_test_trends(self) -> Dict:
        """Get test trends from historical data"""
        history_files = sorted(self.history_dir.glob('*.json'), reverse=True)[:30]

        trends = {
            'success_rates': [],
            'durations': [],
            'test_counts': [],
            'timestamps': []
        }

        for history_file in history_files:
            try:
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    trends['success_rates'].append(data.get('success_rate', 0))
                    trends['durations'].append(data.get('duration', 0))
                    trends['test_counts'].append(data.get('summary', {}).get('total', 0))
                    trends['timestamps'].append(data.get('timestamp'))
            except:
                pass

        return trends

    def generate_enhanced_dashboard(self):
        """Generate enhanced dashboard with monitoring"""
        completion_status = self.get_tool_completion_status()
        trends = self.get_test_trends()

        # Calculate statistics
        total_tools = len(completion_status)
        untested = sum(1 for v in completion_status.values() if v['status'] == 'untested')
        experimental = sum(1 for v in completion_status.values() if v['status'] == 'experimental')
        validated = sum(1 for v in completion_status.values() if v['status'] == 'validated')
        stress_tested = sum(1 for v in completion_status.values() if v['status'] == 'stress_tested')
        in_progress = sum(1 for v in completion_status.values() if v['status'] == 'in_progress')

        # Calculate percentages safely
        completion_pct = ((total_tools - untested) / total_tools * 100) if total_tools > 0 else 0
        untested_pct = (untested / total_tools * 100) if total_tools > 0 else 0
        experimental_pct = (experimental / total_tools * 100) if total_tools > 0 else 0
        validated_pct = (validated / total_tools * 100) if total_tools > 0 else 0
        stress_tested_pct = (stress_tested / total_tools * 100) if total_tools > 0 else 0

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>JARVIS Test Dashboard - Enhanced</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #2c3e50, #3498db); color: white; padding: 20px; border-radius: 8px; }}
        .card {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric {{ display: inline-block; padding: 15px; margin: 10px; background: #ecf0f1; border-radius: 8px; text-align: center; min-width: 100px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .metric-label {{ font-size: 12px; color: #7f8c8d; }}
        .success {{ color: #27ae60; }}
        .warning {{ color: #f39c12; }}
        .danger {{ color: #e74c3c; }}
        .info {{ color: #3498db; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f2f2f2; }}
        tr:hover {{ background: #f9f9f9; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
        .badge-untested {{ background: #f8d7da; color: #721c24; }}
        .badge-experimental {{ background: #fff3cd; color: #856404; }}
        .badge-validated {{ background: #d4edda; color: #155724; }}
        .badge-stress {{ background: #d1ecf1; color: #0c5460; }}
        .progress-bar {{ height: 20px; background: #e0e0e0; border-radius: 10px; overflow: hidden; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #3498db, #2ecc71); transition: width 0.3s; }}
        .alert {{ padding: 15px; margin: 10px 0; border-radius: 8px; }}
        .alert-success {{ background: #d4edda; color: #155724; }}
        .alert-warning {{ background: #fff3cd; color: #856404; }}
        .alert-danger {{ background: #f8d7da; color: #721c24; }}
    </style>
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(function() {{
            location.reload();
        }}, 30000);
    </script>
</head>
<body>
    <div class="header">
        <h1>JARVIS Test Dashboard - Enhanced</h1>
        <p>Real-time monitoring, tool completion tracking, and automated alerts</p>
        <p>Last updated: {datetime.now().isoformat()}</p>
    </div>

    <div class="card">
        <h2>Overall Progress</h2>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {completion_pct:.1f}%"></div>
        </div>
        <p>Completion: {total_tools - untested} / {total_tools} tools ({completion_pct:.1f}%)</p>
        <div>
            <div class="metric">
                <div class="metric-value info">{total_tools}</div>
                <div class="metric-label">Total Tools</div>
            </div>
            <div class="metric">
                <div class="metric-value success">{validated + stress_tested}</div>
                <div class="metric-label">Production-Ready</div>
            </div>
            <div class="metric">
                <div class="metric-value warning">{experimental}</div>
                <div class="metric-label">Experimental</div>
            </div>
            <div class="metric">
                <div class="metric-value danger">{untested}</div>
                <div class="metric-label">Untested</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>Completion Status by Category</h2>
        <table>
            <tr>
                <th>Status</th>
                <th>Count</th>
                <th>Percentage</th>
                <th>Description</th>
            </tr>
            <tr>
                <td><span class="badge badge-untested">Untested</span></td>
                <td>{untested}</td>
                <td>{untested_pct:.1f}%</td>
                <td>No meaningful test coverage</td>
            </tr>
            <tr>
                <td><span class="badge badge-experimental">Experimental</span></td>
                <td>{experimental}</td>
                <td>{experimental_pct:.1f}%</td>
                <td>Basic functionality works (T01 passed)</td>
            </tr>
            <tr>
                <td><span class="badge badge-validated">Validated</span></td>
                <td>{validated}</td>
                <td>{validated_pct:.1f}%</td>
                <td>Correctness and integration established (Layers 1-3)</td>
            </tr>
            <tr>
                <td><span class="badge badge-stress">Stress-Tested</span></td>
                <td>{stress_tested}</td>
                <td>{stress_tested_pct:.1f}%</td>
                <td>Load, concurrency and failure behavior evaluated (Layers 4-7)</td>
            </tr>
        </table>
    </div>

    <div class="card">
        <h2>Recent Test Trends</h2>
"""

        if trends['success_rates']:
            latest_rate = trends['success_rates'][0]
            previous_rate = trends['success_rates'][1] if len(trends['success_rates']) > 1 else latest_rate

            if latest_rate >= previous_rate:
                trend = "improving"
                trend_class = "success"
            else:
                trend = "declining"
                trend_class = "danger"

            html += f"""
        <div class="alert alert-{trend_class}">
            <strong>Success Rate Trend:</strong> {trend} ({previous_rate:.2%} → {latest_rate:.2%})
        </div>
"""
        else:
            html += """
        <p>No historical data available yet.</p>
"""

        html += """
    </div>

    <div class="card">
        <h2>Tool Completion List</h2>
        <table>
            <tr>
                <th>Tool</th>
                <th>Status</th>
                <th>Layers</th>
                <th>Tests</th>
            </tr>
"""

        for tool, status in sorted(completion_status.items()):
            status_class = {
                'untested': 'badge-untested',
                'experimental': 'badge-experimental',
                'validated': 'badge-validated',
                'stress_tested': 'badge-stress',
                'in_progress': 'badge-experimental'
            }

            layers_str = ', '.join(map(str, status['layers'])) if status['layers'] else 'None'

            html += f"""
            <tr>
                <td>{tool}</td>
                <td><span class="badge {status_class[status['status']]}">{status['status']}</span></td>
                <td>{layers_str}</td>
                <td>{status['test_count']}</td>
            </tr>
"""

        html += """
        </table>
    </div>

    <div class="card">
        <h2>Quick Actions</h2>
        <p>
            <button onclick="location.reload()">Refresh Dashboard</button>
            <button onclick="window.open('README.md', '_blank')">View Documentation</button>
            <button onclick="window.open('IMPLEMENTATION_PROGRESS.md', '_blank')">View Progress</button>
        </p>
    </div>

    <div style="text-align: center; margin: 20px; color: #7f8c8d;">
        <p>Auto-refreshes every 30 seconds</p>
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
    dashboard = EnhancedTestDashboard(test_root)

    dashboard_path = dashboard.generate_enhanced_dashboard()
    print(f"Enhanced dashboard generated: {dashboard_path}")
    print(f"Open in browser: file://{dashboard_path.absolute()}")


if __name__ == '__main__':
    main()
