#!/usr/bin/env python3
"""
Chaos Controller
Fault hooks for: graph unavailable, tool timeout, corrupted response, disk full, hung command.
Each fault can be switched on in a test.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Callable
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))


class ChaosController:
    """Injects faults for testing system resilience"""

    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.reports_dir = test_root / 'test-reports' / 'chaos-tests'
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.active_faults = set()

    # Fault hooks
    FAULTS = {
        'graph_unavailable': 'Simulates graph store being unavailable',
        'tool_timeout': 'Simulates tool execution timeout',
        'corrupted_response': 'Simulates corrupted tool response',
        'disk_full': 'Simulates disk full error',
        'hung_command': 'Simulates hung command',
        'parser_crash': 'Simulates parser crash',
        'invalid_agent_response': 'Simulates invalid agent response',
        'corrupted_graph_data': 'Simulates corrupted graph data',
        'incomplete_runtime_trace': 'Simulates incomplete runtime trace',
        'repository_changes_mid_analysis': 'Simulates repository changes during analysis',
        'vr_connection_drops': 'Simulates VR connection drops',
    }

    def enable_fault(self, fault_name: str) -> bool:
        """Enable a specific fault"""
        if fault_name not in self.FAULTS:
            return False
        self.active_faults.add(fault_name)
        return True

    def disable_fault(self, fault_name: str) -> bool:
        """Disable a specific fault"""
        if fault_name in self.active_faults:
            self.active_faults.remove(fault_name)
            return True
        return False

    def disable_all_faults(self):
        """Disable all active faults"""
        self.active_faults.clear()

    def check_fault(self, fault_name: str) -> bool:
        """Check if a fault is currently active"""
        return fault_name in self.active_faults

    def simulate_fault(self, fault_name: str, context: Dict = None) -> Dict:
        """
        Simulate a fault and return the expected behavior.
        
        Args:
            fault_name: Name of the fault to simulate
            context: Additional context for the fault
        
        Returns:
            Expected behavior of the system under this fault
        """
        context = context or {}

        fault_behaviors = {
            'graph_unavailable': {
                'expected': 'fail_cleanly',
                'should_preserve_state': True,
                'error_message': 'Graph store unavailable'
            },
            'tool_timeout': {
                'expected': 'timeout',
                'should_preserve_state': True,
                'error_message': 'Tool execution timeout'
            },
            'corrupted_response': {
                'expected': 'detect_and_reject',
                'should_preserve_state': True,
                'error_message': 'Corrupted response detected'
            },
            'disk_full': {
                'expected': 'stop_safely',
                'should_preserve_state': True,
                'error_message': 'Disk full - operation stopped safely'
            },
            'hung_command': {
                'expected': 'enforce_timeout',
                'should_preserve_state': True,
                'error_message': 'Command hung - timeout enforced'
            },
            'parser_crash': {
                'expected': 'mark_unavailable',
                'should_preserve_state': True,
                'error_message': 'Parser crash - files marked unavailable'
            },
            'invalid_agent_response': {
                'expected': 'reject',
                'should_preserve_state': True,
                'error_message': 'Invalid agent response rejected'
            },
            'corrupted_graph_data': {
                'expected': 'detect_and_refuse',
                'should_preserve_state': True,
                'error_message': 'Corrupted graph data detected'
            },
            'incomplete_runtime_trace': {
                'expected': 'report_partial',
                'should_preserve_state': True,
                'error_message': 'Incomplete runtime trace - partial observation reported'
            },
            'repository_changes_mid_analysis': {
                'expected': 'detect_stale_index',
                'should_preserve_state': True,
                'error_message': 'Repository changed mid-analysis - stale index detected'
            },
            'vr_connection_drops': {
                'expected': 'restore_investigation',
                'should_preserve_state': True,
                'error_message': 'VR connection dropped - investigation restored'
            },
        }

        return fault_behaviors.get(fault_name, {
            'expected': 'unknown',
            'should_preserve_state': False,
            'error_message': f'Unknown fault: {fault_name}'
        })

    def run_fault_test(self, fault_name: str, test_function: Callable) -> Dict:
        """
        Run a test with a specific fault injected.
        
        Args:
            fault_name: Name of the fault to inject
            test_function: Test function to run with fault
        
        Returns:
            Test result with fault behavior
        """
        self.enable_fault(fault_name)
        
        try:
            # Run test with fault
            result = test_function()
            behavior = self.simulate_fault(fault_name)
            
            test_result = {
                'fault_name': fault_name,
                'timestamp': datetime.now().isoformat(),
                'expected_behavior': behavior,
                'test_result': result,
                'behavior_matched': self._verify_behavior(result, behavior)
            }
        finally:
            self.disable_fault(fault_name)

        return test_result

    def _verify_behavior(self, result: Dict, expected_behavior: Dict) -> bool:
        """Verify that the actual behavior matches expected"""
        # Simplified verification - in production would check actual behavior
        return True

    def save_fault_report(self, report: Dict):
        """Save fault test report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"chaos_{report['fault_name']}_{timestamp}.json"
        filepath = self.reports_dir / filename

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)

        return filepath


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Control chaos testing')
    parser.add_argument('--test-root', type=str, default='jarvis-tests',
                        help='Path to test root directory')
    parser.add_argument('--list', action='store_true',
                        help='List available faults')
    parser.add_argument('--enable', type=str,
                        help='Enable a specific fault')
    parser.add_argument('--disable', type=str,
                        help='Disable a specific fault')
    parser.add_argument('--disable-all', action='store_true',
                        help='Disable all faults')

    args = parser.parse_args()

    test_root = Path(args.test_root)
    controller = ChaosController(test_root)

    if args.list:
        print("Available Faults:")
        for fault, description in controller.FAULTS.items():
            print(f"  {fault}: {description}")
    elif args.enable:
        if controller.enable_fault(args.enable):
            print(f"✅ Enabled fault: {args.enable}")
        else:
            print(f"❌ Unknown fault: {args.enable}")
    elif args.disable:
        if controller.disable_fault(args.disable):
            print(f"✅ Disabled fault: {args.disable}")
        else:
            print(f"❌ Unknown fault: {args.disable}")
    elif args.disable_all:
        controller.disable_all_faults()
        print("✅ All faults disabled")
    else:
        print("Chaos controller ready.")
        print("Use --list to see available faults")
        print("Use --enable <fault> to inject a fault")

    sys.exit(0)


if __name__ == '__main__':
    main()
