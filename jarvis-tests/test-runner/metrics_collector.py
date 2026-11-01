#!/usr/bin/env python3
"""
Metrics Collector
Collects all 15 metrics from various sources for Phase 5.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))


class MetricsCollector:
    """Collects the 15 metrics from the plan"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.reports_dir = test_root / 'test-reports' / 'metrics'
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def collect_all_metrics(self) -> Dict:
        """Collect all 15 metrics"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'metrics': {}
        }

        # Metric 1: Tool Correctness
        metrics['metrics']['tool_correctness'] = self.collect_tool_correctness()

        # Metric 2: Tool Completeness
        metrics['metrics']['tool_completeness'] = self.collect_tool_completeness()

        # Metric 3: Precision
        metrics['metrics']['precision'] = self.collect_precision()

        # Metric 4: Recall
        metrics['metrics']['recall'] = self.collect_recall()

        # Metric 5: Schema Validity
        metrics['metrics']['schema_validity'] = self.collect_schema_validity()

        # Metric 6: Agent Task Success
        metrics['metrics']['agent_task_success'] = self.collect_agent_task_success()

        # Metric 7: Tool Selection
        metrics['metrics']['tool_selection'] = self.collect_tool_selection()

        # Metric 8: Evidence Accuracy
        metrics['metrics']['evidence_accuracy'] = self.collect_evidence_accuracy()

        # Metric 9: Hallucination Rate
        metrics['metrics']['hallucination_rate'] = self.collect_hallucination_rate()

        # Metric 10: Investigation Completeness
        metrics['metrics']['investigation_completeness'] = self.collect_investigation_completeness()

        # Metric 11: Latency P50
        metrics['metrics']['latency_p50'] = self.collect_latency_p50()

        # Metric 12: Latency P95
        metrics['metrics']['latency_p95'] = self.collect_latency_p95()

        # Metric 13: Throughput
        metrics['metrics']['throughput'] = self.collect_throughput()

        # Metric 14: Resource Consumption
        metrics['metrics']['resource_consumption'] = self.collect_resource_consumption()

        # Metric 15: Failure Recovery
        metrics['metrics']['failure_recovery'] = self.collect_failure_recovery()

        return metrics

    def collect_tool_correctness(self) -> Dict:
        """Metric 1: Verified-spec pass rate"""
        try:
            from score_plan import ScorePlan
            scorer = ScorePlan(self.test_root)
            score = scorer.compute_score()
            
            # Extract tool correctness from layers 1-2
            tool_correctness = score['details'].get('layers_1_2_tool_correctness', {})
            
            return {
                'value': tool_correctness.get('current', 0.5),
                'target': 0.80,
                'status': 'pass' if tool_correctness.get('current', 0) >= 0.80 else 'fail',
                'source': 'score_plan.py'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 0.80,
                'status': 'error',
                'error': str(e),
                'source': 'score_plan.py'
            }

    def collect_tool_completeness(self) -> Dict:
        """Metric 2: Percentage of tools with verified specs"""
        try:
            status_file = self.test_root / 'tool_completion_status.json'
            if not status_file.exists():
                return {'value': 0.0, 'target': 0.90, 'status': 'error', 'source': 'tool_completion_status.json'}
            
            with open(status_file, 'r') as f:
                status = json.load(f)
            
            total_tools = len(status)
            verified_tools = sum(1 for s in status.values() if s.get('status') == 'Validated')
            completeness = verified_tools / total_tools if total_tools > 0 else 0.0
            
            return {
                'value': completeness,
                'target': 0.90,
                'status': 'pass' if completeness >= 0.90 else 'fail',
                'source': 'tool_completion_status.json'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 0.90,
                'status': 'error',
                'error': str(e),
                'source': 'tool_completion_status.json'
            }

    def collect_precision(self) -> Dict:
        """Metric 3: Precision from ground truth engine"""
        return {
            'value': 0.0,  # Will be calculated from ground truth engine
            'target': 0.95,
            'status': 'pending',
            'source': 'ground_truth_engine.py'
        }

    def collect_recall(self) -> Dict:
        """Metric 4: Recall from ground truth engine"""
        return {
            'value': 0.0,  # Will be calculated from ground truth engine
            'target': 0.90,
            'status': 'pending',
            'source': 'ground_truth_engine.py'
        }

    def collect_schema_validity(self) -> Dict:
        """Metric 5: Schema validity percentage"""
        try:
            from validate_spec_schema import validate_all_specs
            results = validate_all_specs(self.test_root)
            
            valid_count = sum(1 for r in results if r.get('valid', False))
            total_count = len(results)
            validity = valid_count / total_count if total_count > 0 else 0.0
            
            return {
                'value': validity,
                'target': 1.0,
                'status': 'pass' if validity >= 1.0 else 'fail',
                'source': 'validate_spec_schema.py'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 1.0,
                'status': 'error',
                'error': str(e),
                'source': 'validate_spec_schema.py'
            }

    def collect_agent_task_success(self) -> Dict:
        """Metric 6: Agent task success rate"""
        try:
            from agent_evaluator import AgentEvaluator
            evaluator = AgentEvaluator(self.test_root)
            
            # Load latest evaluation
            eval_file = self.test_root / 'test-reports' / 'agent-evaluations' / 'latest.json'
            if eval_file.exists():
                with open(eval_file, 'r') as f:
                    eval_data = json.load(f)
                success_rate = eval_data.get('overall_score', 0.0)
            else:
                success_rate = 0.0
            
            return {
                'value': success_rate,
                'target': 0.85,
                'status': 'pass' if success_rate >= 0.85 else 'fail',
                'source': 'agent_evaluator.py'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 0.85,
                'status': 'error',
                'error': str(e),
                'source': 'agent_evaluator.py'
            }

    def collect_tool_selection(self) -> Dict:
        """Metric 7: Agent tool selection accuracy"""
        try:
            from agent_evaluator import AgentEvaluator
            evaluator = AgentEvaluator(self.test_root)
            
            eval_file = self.test_root / 'test-reports' / 'agent-evaluations' / 'latest.json'
            if eval_file.exists():
                with open(eval_file, 'r') as f:
                    eval_data = json.load(f)
                selection_score = eval_data.get('tool_selection_score', 0.0)
            else:
                selection_score = 0.0
            
            return {
                'value': selection_score,
                'target': 0.80,
                'status': 'pass' if selection_score >= 0.80 else 'fail',
                'source': 'agent_evaluator.py'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 0.80,
                'status': 'error',
                'error': str(e),
                'source': 'agent_evaluator.py'
            }

    def collect_evidence_accuracy(self) -> Dict:
        """Metric 8: Evidence accuracy percentage"""
        try:
            from agent_evaluator import AgentEvaluator
            evaluator = AgentEvaluator(self.test_root)
            
            eval_file = self.test_root / 'test-reports' / 'agent-evaluations' / 'latest.json'
            if eval_file.exists():
                with open(eval_file, 'r') as f:
                    eval_data = json.load(f)
                evidence_score = eval_data.get('evidence_score', 0.0)
            else:
                evidence_score = 0.0
            
            return {
                'value': evidence_score,
                'target': 0.90,
                'status': 'pass' if evidence_score >= 0.90 else 'fail',
                'source': 'agent_evaluator.py'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 0.90,
                'status': 'error',
                'error': str(e),
                'source': 'agent_evaluator.py'
            }

    def collect_hallucination_rate(self) -> Dict:
        """Metric 9: Hallucination rate (inverse of evidence)"""
        try:
            from agent_evaluator import AgentEvaluator
            evaluator = AgentEvaluator(self.test_root)
            
            eval_file = self.test_root / 'test-reports' / 'agent-evaluations' / 'latest.json'
            if eval_file.exists():
                with open(eval_file, 'r') as f:
                    eval_data = json.load(f)
                hallucination_score = eval_data.get('hallucination_score', 0.0)
            else:
                hallucination_score = 0.0
            
            return {
                'value': hallucination_score,
                'target': 0.10,
                'status': 'pass' if hallucination_score <= 0.10 else 'fail',
                'source': 'agent_evaluator.py'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 0.10,
                'status': 'error',
                'error': str(e),
                'source': 'agent_evaluator.py'
            }

    def collect_investigation_completeness(self) -> Dict:
        """Metric 10: Investigation completeness"""
        return {
            'value': 0.0,  # Will be calculated from scenario manifests
            'target': 0.90,
            'status': 'pending',
            'source': 'scenario_manifests'
        }

    def collect_latency_p50(self) -> Dict:
        """Metric 11: P50 latency"""
        try:
            from performance_monitor import PerformanceMonitor
            monitor = PerformanceMonitor(self.test_root)
            
            perf_file = self.test_root / 'test-reports' / 'performance' / 'latest.json'
            if perf_file.exists():
                with open(perf_file, 'r') as f:
                    perf_data = json.load(f)
                # Calculate average P50 across all tools
                p50_values = [t.get('percentiles', {}).get('p50', 0) for t in perf_data.get('tools', {}).values()]
                avg_p50 = sum(p50_values) / len(p50_values) if p50_values else 0
            else:
                avg_p50 = 0.0
            
            return {
                'value': avg_p50,
                'target': 100,  # ms
                'status': 'pass' if avg_p50 <= 100 else 'fail',
                'source': 'performance_monitor.py'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 100,
                'status': 'error',
                'error': str(e),
                'source': 'performance_monitor.py'
            }

    def collect_latency_p95(self) -> Dict:
        """Metric 12: P95 latency"""
        try:
            from performance_monitor import PerformanceMonitor
            monitor = PerformanceMonitor(self.test_root)
            
            perf_file = self.test_root / 'test-reports' / 'performance' / 'latest.json'
            if perf_file.exists():
                with open(perf_file, 'r') as f:
                    perf_data = json.load(f)
                p95_values = [t.get('percentiles', {}).get('p95', 0) for t in perf_data.get('tools', {}).values()]
                avg_p95 = sum(p95_values) / len(p95_values) if p95_values else 0
            else:
                avg_p95 = 0.0
            
            return {
                'value': avg_p95,
                'target': 300,  # ms
                'status': 'pass' if avg_p95 <= 300 else 'fail',
                'source': 'performance_monitor.py'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 300,
                'status': 'error',
                'error': str(e),
                'source': 'performance_monitor.py'
            }

    def collect_throughput(self) -> Dict:
        """Metric 13: Throughput (req/s)"""
        try:
            from load_generator import LoadGenerator
            gen = LoadGenerator(self.test_root)
            
            load_file = self.test_root / 'test-reports' / 'load-tests' / 'latest.json'
            if load_file.exists():
                with open(load_file, 'r') as f:
                    load_data = json.load(f)
                throughput = load_data.get('throughput', 0)
            else:
                throughput = 0.0
            
            return {
                'value': throughput,
                'target': 100,  # req/s
                'status': 'pass' if throughput >= 100 else 'fail',
                'source': 'load_generator.py'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 100,
                'status': 'error',
                'error': str(e),
                'source': 'load_generator.py'
            }

    def collect_resource_consumption(self) -> Dict:
        """Metric 14: Resource consumption"""
        try:
            from performance_monitor import PerformanceMonitor
            monitor = PerformanceMonitor(self.test_root)
            
            perf_file = self.test_root / 'test-reports' / 'performance' / 'latest.json'
            if perf_file.exists():
                with open(perf_file, 'r') as f:
                    perf_data = json.load(f)
                metrics = perf_data.get('metrics', {})
                cpu = metrics.get('cpu_delta', 0)
                memory = metrics.get('memory_delta_mb', 0)
            else:
                cpu = 0
                memory = 0
            
            return {
                'value': {'cpu_percent': cpu, 'memory_mb': memory},
                'target': {'cpu_percent': 80, 'memory_mb': 4096},
                'status': 'pass' if cpu <= 80 and memory <= 4096 else 'fail',
                'source': 'performance_monitor.py'
            }
        except Exception as e:
            return {
                'value': {'cpu_percent': 0, 'memory_mb': 0},
                'target': {'cpu_percent': 80, 'memory_mb': 4096},
                'status': 'error',
                'error': str(e),
                'source': 'performance_monitor.py'
            }

    def collect_failure_recovery(self) -> Dict:
        """Metric 15: Failure recovery time"""
        try:
            from chaos_controller import ChaosController
            chaos = ChaosController(self.test_root)
            
            chaos_file = self.test_root / 'test-reports' / 'chaos' / 'latest.json'
            if chaos_file.exists():
                with open(chaos_file, 'r') as f:
                    chaos_data = json.load(f)
                recovery_time = chaos_data.get('avg_recovery_time_seconds', 0)
            else:
                recovery_time = 0.0
            
            return {
                'value': recovery_time,
                'target': 30,  # seconds
                'status': 'pass' if recovery_time <= 30 else 'fail',
                'source': 'chaos_controller.py'
            }
        except Exception as e:
            return {
                'value': 0.0,
                'target': 30,
                'status': 'error',
                'error': str(e),
                'source': 'chaos_controller.py'
            }

    def save_metrics(self, metrics: Dict):
        """Save metrics to file"""
        timestamp = datetime.now().isoformat()
        metrics_file = self.reports_dir / f"metrics-{timestamp}.json"
        
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        # Also save as latest
        latest_file = self.reports_dir / 'latest.json'
        with open(latest_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        return metrics_file


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Collect metrics')
    parser.add_argument('--test-root', type=str, default='..',
                        help='Path to test root directory')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    collector = MetricsCollector(test_root)

    metrics = collector.collect_all_metrics()
    file_path = collector.save_metrics(metrics)

    print(f"✅ Metrics collected and saved to {file_path}")
    
    # Print summary
    print("\nMetrics Summary:")
    print("=" * 60)
    for metric_name, metric_data in metrics['metrics'].items():
        value = metric_data.get('value')
        target = metric_data.get('target')
        status = metric_data.get('status')
        if isinstance(value, dict):
            value_str = str(value)
        else:
            value_str = str(value)
        print(f"{metric_name:30} {value_str:20} target: {target} [{status}]")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
