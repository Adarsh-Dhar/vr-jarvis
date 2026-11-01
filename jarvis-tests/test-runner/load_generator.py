#!/usr/bin/env python3
"""
Load Generator
Runs staged workloads and records success rate, queue time, memory and CPU.
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Try to import psutil, provide fallback if not available
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not installed. Memory/CPU metrics will be skipped.", file=sys.stderr)

sys.path.insert(0, str(Path(__file__).parent))


class LoadGenerator:
    """Generates load for testing system capacity"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.reports_dir = test_root / 'test-reports' / 'load-tests'
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def run_workload(self, concurrent_tasks: int, task_duration: float = 1.0) -> Dict:
        """
        Run a staged workload.
        
        Args:
            concurrent_tasks: Number of concurrent tasks to run
            task_duration: Duration of each task in seconds
        
        Returns:
            Load test results
        """
        start_time = time.time()

        # Record initial metrics
        if HAS_PSUTIL:
            process = psutil.Process()
            initial_cpu = process.cpu_percent()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        else:
            initial_cpu = 0
            initial_memory = 0

        # Run tasks concurrently
        results = []
        with ThreadPoolExecutor(max_workers=concurrent_tasks) as executor:
            futures = [
                executor.submit(self._mock_task, i, task_duration)
                for i in range(concurrent_tasks)
            ]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({'task_id': 'unknown', 'status': 'error', 'error': str(e)})

        # Record final metrics
        if HAS_PSUTIL:
            final_cpu = process.cpu_percent()
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
        else:
            final_cpu = 0
            final_memory = 0
        duration = time.time() - start_time

        # Calculate metrics
        success_count = sum(1 for r in results if r.get('status') == 'success')
        success_rate = success_count / len(results) if results else 0

        report = {
            'timestamp': datetime.now().isoformat(),
            'workload': {
                'concurrent_tasks': concurrent_tasks,
                'task_duration': task_duration,
                'total_tasks': len(results)
            },
            'results': {
                'success_count': success_count,
                'error_count': len(results) - success_count,
                'success_rate': success_rate,
                'duration': duration
            },
            'metrics': {
                'cpu_initial': initial_cpu,
                'cpu_final': final_cpu,
                'cpu_delta': final_cpu - initial_cpu,
                'memory_initial_mb': initial_memory,
                'memory_final_mb': final_memory,
                'memory_delta_mb': final_memory - initial_memory
            },
            'queue_metrics': {
                'avg_queue_time': duration / concurrent_tasks if concurrent_tasks > 0 else 0
            }
        }

        return report

    def _mock_task(self, task_id: int, duration: float) -> Dict:
        """Mock task for testing"""
        time.sleep(duration)
        return {'task_id': task_id, 'status': 'success'}

    def generate_capacity_report(self, reports: List[Dict]) -> str:
        """Generate a capacity report"""
        lines = [
            "Load Test Capacity Report",
            "=" * 80,
            f"Generated: {datetime.now().isoformat()}",
            f"Total Workloads: {len(reports)}",
            ""
        ]

        for report in reports:
            workload = report['workload']
            results = report['results']
            metrics = report['metrics']

            lines.append(f"Workload: {workload['concurrent_tasks']} concurrent tasks")
            lines.append(f"  Success Rate: {results['success_rate']:.2%}")
            lines.append(f"  Duration: {results['duration']:.2f}s")
            lines.append(f"  CPU Delta: {metrics['cpu_delta']:.1f}%")
            lines.append(f"  Memory Delta: {metrics['memory_delta_mb']:.2f} MB")
            lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def save_report(self, report: Dict):
        """Save report to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"load_test_{report['workload']['concurrent_tasks']}_{timestamp}.json"
        filepath = self.reports_dir / filename

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)

        return filepath


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Run load tests')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')
    parser.add_argument('--concurrent', type=int, nargs='+', default=[10, 50, 100],
                        help='Concurrent task counts to test')
    parser.add_argument('--duration', type=float, default=1.0,
                        help='Task duration in seconds')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    generator = LoadGenerator(test_root)

    reports = []
    for concurrent in args.concurrent:
        print(f"Running workload with {concurrent} concurrent tasks...")
        report = generator.run_workload(concurrent, args.duration)
        generator.save_report(report)
        reports.append(report)

    print(generator.generate_capacity_report(reports))

    sys.exit(0)


if __name__ == '__main__':
    main()
