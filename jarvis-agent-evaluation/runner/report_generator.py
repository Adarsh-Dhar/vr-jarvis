#!/usr/bin/env python3
"""
Report Generator for Agent Evaluation
Generates detailed evaluation reports from test results
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class ReportGenerator:
    """Generates evaluation reports from test results."""

    def __init__(self, results_path: Path, output_dir: Path):
        self.results_path = results_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = self.load_results()

    def load_results(self) -> List[Dict[str, Any]]:
        """Load test results from JSON."""
        try:
            with open(self.results_path) as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Failed to load results: {e}")
            return []

    def generate_markdown_report(self) -> str:
        """Generate a Markdown report."""
        if not self.results:
            return "# No Results\n\nNo test results to report."

        # Calculate summary statistics
        total = len(self.results)
        passed = sum(1 for r in self.results if r['execution']['status'] == 'passed')
        failed = sum(1 for r in self.results if r['execution']['status'] == 'failed')
        skipped = sum(1 for r in self.results if r['execution']['status'] == 'skipped')
        errors = sum(1 for r in self.results if r['execution']['status'] == 'error')

        # Group by agent
        by_agent = {}
        for result in self.results:
            agent = result['test'].get('agent', 'unknown')
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(result)

        # Generate report
        report = []
        report.append("# Agent Evaluation Report")
        report.append(f"\nGenerated: {datetime.now().isoformat()}")
        report.append(f"\n## Executive Summary")
        report.append(f"\n**Total Tests:** {total}")
        report.append(f"**Passed:** {passed} ({passed/total*100:.2f}%)" if total > 0 else "**Passed:** 0")
        report.append(f"**Failed:** {failed} ({failed/total*100:.2f}%)" if total > 0 else "**Failed:** 0")
        report.append(f"**Skipped:** {skipped} ({skipped/total*100:.2f}%)" if total > 0 else "**Skipped:** 0")
        report.append(f"**Errors:** {errors} ({errors/total*100:.2f}%)" if total > 0 else "**Errors:** 0")

        # Agent-specific results
        report.append(f"\n## Results by Agent")
        for agent, agent_results in sorted(by_agent.items()):
            agent_total = len(agent_results)
            agent_passed = sum(1 for r in agent_results if r['execution']['status'] == 'passed')
            agent_failed = sum(1 for r in agent_results if r['execution']['status'] == 'failed')
            
            report.append(f"\n### {agent}")
            report.append(f"- Total: {agent_total}")
            report.append(f"- Passed: {agent_passed} ({agent_passed/agent_total*100:.2f}%)" if agent_total > 0 else "- Passed: 0")
            report.append(f"- Failed: {agent_failed} ({agent_failed/agent_total*100:.2f}%)" if agent_total > 0 else "- Failed: 0")

        # Detailed failures
        if failed > 0:
            report.append(f"\n## Failed Tests")
            for result in self.results:
                if result['execution']['status'] == 'failed':
                    test_id = result['test'].get('test_id', 'unknown')
                    scenario = result['test'].get('scenario', 'unknown')
                    error = result['execution'].get('errors', ['No error details'])
                    report.append(f"\n### {test_id}: {scenario}")
                    report.append(f"**Error:** {error}")

        # Detailed errors
        if errors > 0:
            report.append(f"\n## Errors")
            for result in self.results:
                if result['execution']['status'] == 'error':
                    test_id = result['test'].get('test_id', 'unknown')
                    error = result['execution'].get('error', 'Unknown error')
                    report.append(f"\n### {test_id}")
                    report.append(f"**Error:** {error}")

        return '\n'.join(report)

    def generate_json_report(self) -> Dict[str, Any]:
        """Generate a JSON report."""
        if not self.results:
            return {'error': 'No results to report'}

        # Calculate summary statistics
        total = len(self.results)
        passed = sum(1 for r in self.results if r['execution']['status'] == 'passed')
        failed = sum(1 for r in self.results if r['execution']['status'] == 'failed')
        skipped = sum(1 for r in self.results if r['execution']['status'] == 'skipped')
        errors = sum(1 for r in self.results if r['execution']['status'] == 'error')

        # Group by agent
        by_agent = {}
        for result in self.results:
            agent = result['test'].get('agent', 'unknown')
            if agent not in by_agent:
                by_agent[agent] = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0}
            by_agent[agent]['total'] += 1
            status = result['execution']['status']
            by_agent[agent][status] += 1

        return {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'errors': errors,
                'success_rate': (passed / total * 100) if total > 0 else 0
            },
            'by_agent': by_agent,
            'results': self.results
        }

    def save_markdown_report(self, filename: str = 'evaluation_report.md'):
        """Save Markdown report."""
        report = self.generate_markdown_report()
        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"✅ Markdown report saved to: {output_path}")

    def save_json_report(self, filename: str = 'evaluation_report.json'):
        """Save JSON report."""
        report = self.generate_json_report()
        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"✅ JSON report saved to: {output_path}")


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    results_path = base_dir / 'reports' / 'test_results.json'
    output_dir = base_dir / 'reports'

    if not results_path.exists():
        print(f"❌ Results file not found: {results_path}")
        print("Run the test runner first to generate results.")
        sys.exit(1)

    generator = ReportGenerator(results_path, output_dir)
    generator.save_markdown_report()
    generator.save_json_report()


if __name__ == '__main__':
    main()
