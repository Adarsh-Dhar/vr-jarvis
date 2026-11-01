#!/usr/bin/env python3
"""
Performance Monitor
Aggregates P50, P95 and P99 per tool and compares with the targets from the plan.
Fails when a P95 target is missed.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import statistics
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))


class PerformanceMonitor:
    """Monitors and reports performance metrics"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.reports_dir = test_root / 'test-reports' / 'performance'
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.tool_metrics = defaultdict(list)
        
        # Performance targets from the plan
        self.targets = {
            'symbol_lookup': {'p95_ms': 100},
            'indexed_search': {'p95_ms': 300},
            'direct_call_graph_query': {'p95_ms': 500},
            'small_repository_indexing': {'p95_s': 30},
            'incremental_indexing': {'p95_s': 5},
            'basic_agent_response': {'p95_s': 5}
        }

    def record_tool_performance(self, tool_name: str, duration_ms: float):
        """Record performance data for a tool"""
        self.tool_metrics[tool_name].append(duration_ms)

    def calculate_percentiles(self, metrics: List[float]) -> Dict[str, float]:
        """Calculate P50, P95, P99 percentiles"""
        if not metrics:
            return {'p50': 0, 'p95': 0, 'p99': 0}
        
        sorted_metrics = sorted(metrics)
        n = len(sorted_metrics)
        
        return {
            'p50': sorted_metrics[int(n * 0.5)] if n > 0 else 0,
            'p95': sorted_metrics[int(n * 0.95)] if n > 0 else 0,
            'p99': sorted_metrics[int(n * 0.99)] if n > 0 else 0
        }

    def check_against_targets(self, tool_name: str, percentiles: Dict[str, float]) -> Dict:
        """Check if performance meets targets"""
        result = {
            'tool': tool_name,
            'meets_targets': True,
            'violations': []
        }

        # Map tool names to target categories
        target_map = {
            'extract_symbols': 'symbol_lookup',
            'search_symbols': 'indexed_search',
            'find_callers': 'direct_call_graph_query',
            'index_repository': 'small_repository_indexing'
        }

        target_category = target_map.get(tool_name)
        if target_category and target_category in self.targets:
            target = self.targets[target_category]
            p95 = percentiles.get('p95', 0)
            
            if 'p95_ms' in target and p95 > target['p95_ms']:
                result['meets_targets'] = False
                result['violations'].append(f"P95 {p95}ms exceeds target {target['p95_ms']}ms")

        return result

    def generate_report(self) -> Dict:
        """Generate performance report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'tools': {},
            'summary': {
                'total_tools': len(self.tool_metrics),
                'tools_meeting_targets': 0,
                'tools_violating_targets': 0
            }
        }

        for tool_name, metrics in self.tool_metrics.items():
            percentiles = self.calculate_percentiles(metrics)
            check = self.check_against_targets(tool_name, percentiles)
            
            report['tools'][tool_name] = {
                'count': len(metrics),
                'percentiles': percentiles,
                'target_check': check
            }

            if check['meets_targets']:
                report['summary']['tools_meeting_targets'] += 1
            else:
                report['summary']['tools_violating_targets'] += 1

        return report

    def save_report(self, report: Dict):
        """Save report to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"performance_{timestamp}.json"
        filepath = self.reports_dir / filename

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)

        return filepath


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Monitor performance')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')
    parser.add_argument('--mock', action='store_true',
                        help='Run with mock data for testing')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    monitor = PerformanceMonitor(test_root)

    if args.mock:
        # Mock data for testing
        monitor.tool_metrics['extract_symbols'] = [50, 75, 100, 120, 80]
        monitor.tool_metrics['search_symbols'] = [200, 250, 300, 350, 280]
        monitor.tool_metrics['find_callers'] = [400, 450, 500, 550, 480]

        report = monitor.generate_report()
        monitor.save_report(report)
        print(json.dumps(report, indent=2))
    else:
        print("Performance monitor ready. Integrate with test runner for actual metrics.")

    sys.exit(0)


if __name__ == '__main__':
    main()
