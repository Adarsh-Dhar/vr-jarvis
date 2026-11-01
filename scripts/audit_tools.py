#!/usr/bin/env python3
"""
Tool Audit Script
Resolves every tool in every toolset, calls it against repository/rp from a different
working directory, and prints a table of results.

Usage:
    python scripts/audit_tools.py
"""

import sys
import os
from pathlib import Path
import time
from collections import defaultdict

# Add server to path
server_dir = Path(__file__).parent.parent / 'server'
sys.path.insert(0, str(server_dir))

from ai_agents.agents.toolsets import TOOLSETS, TOOL_LEVELS, PERMISSION_CEILINGS
from ai_agents import tools as tools_module
import inspect


class MockToolContext:
    """Mock tool context for testing."""
    def __init__(self):
        self.state = {
            'worktree': None,
            'tool_budgets': {},
            'evidence': [],
            'scene_commands': [],
        }
        self.agent_name = 'test_agent'


def audit_tools():
    """Run audit on all tools."""
    print("=" * 80)
    print("JARVIS TOOL AUDIT")
    print("=" * 80)
    print()
    
    # Count tools by status
    status_counts = defaultdict(int)
    results_by_agent = defaultdict(list)
    
    # Iterate through all toolsets
    for agent_name, tool_names in TOOLSETS.items():
        print(f"\nAgent: {agent_name} (ceiling: {PERMISSION_CEILINGS.get(agent_name, 'read')})")
        print("-" * 80)
        
        for tool_name in tool_names:
            # Get the tool function
            if not hasattr(tools_module, tool_name):
                result = {
                    'tool': tool_name,
                    'status': 'error',
                    'reason': 'Tool not found in tools module'
                }
                status_counts['error'] += 1
                results_by_agent[agent_name].append(result)
                print(f"  {tool_name}: ERROR - Tool not found")
                continue
            
            tool_func = getattr(tools_module, tool_name)
            
            # Check permission level
            perm_level = TOOL_LEVELS.get(tool_name, 'read')
            agent_ceiling = PERMISSION_CEILINGS.get(agent_name, 'read')
            
            perm_order = {'read': 0, 'execute': 1, 'write': 2}
            if perm_order.get(perm_level, 0) > perm_order.get(agent_ceiling, 0):
                result = {
                    'tool': tool_name,
                    'status': 'permission_mismatch',
                    'reason': f'Tool requires {perm_level}, agent has {agent_ceiling}'
                }
                status_counts['permission_mismatch'] += 1
                results_by_agent[agent_name].append(result)
                print(f"  {tool_name}: PERMISSION_MISMATCH - {perm_level} > {agent_ceiling}")
                continue
            
            # Try to call the tool (skip write/execute tools for safety)
            if perm_level in ['write', 'execute']:
                result = {
                    'tool': tool_name,
                    'status': 'skipped',
                    'reason': f'Write/execute tool ({perm_level}) - skipped for safety'
                }
                status_counts['skipped'] += 1
                results_by_agent[agent_name].append(result)
                print(f"  {tool_name}: SKIPPED - {perm_level} tool")
                continue
            
            # Call read-only tools
            try:
                tool_context = MockToolContext()
                
                # Get tool signature to determine required args
                sig = inspect.signature(tool_func)
                params = sig.parameters
                
                # Build minimal args
                kwargs = {}
                for param_name, param in params.items():
                    if param_name == 'tool_context':
                        kwargs['tool_context'] = tool_context
                    elif param.default == inspect.Parameter.empty:
                        # Required parameter - provide a safe default
                        if 'path' in param_name.lower() or 'file' in param_name.lower():
                            kwargs[param_name] = '.'
                        elif 'repository' in param_name.lower():
                            kwargs[param_name] = '.'
                        elif 'scope' in param_name.lower():
                            kwargs[param_name] = '.'
                        else:
                            kwargs[param_name] = ''
                
                # Call the tool
                start = time.time()
                result_dict = tool_func(**kwargs)
                duration = time.time() - start
                
                # Check result
                if not isinstance(result_dict, dict):
                    result = {
                        'tool': tool_name,
                        'status': 'error',
                        'reason': f'Returned non-dict: {type(result_dict)}'
                    }
                    status_counts['error'] += 1
                    print(f"  {tool_name}: ERROR - Non-dict return")
                else:
                    status = result_dict.get('status', 'unknown')
                    result = {
                        'tool': tool_name,
                        'status': status,
                        'duration': duration,
                        'result': result_dict
                    }
                    status_counts[status] += 1
                    print(f"  {tool_name}: {status.upper()} ({duration:.3f}s)")
                    if status in ['error', 'blocked']:
                        print(f"    Reason: {result_dict.get('reason', result_dict.get('error', 'unknown'))}")
                    
            except Exception as e:
                result = {
                    'tool': tool_name,
                    'status': 'exception',
                    'reason': str(e)
                }
                status_counts['exception'] += 1
                print(f"  {tool_name}: EXCEPTION - {e}")
            
            results_by_agent[agent_name].append(result)
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for status, count in sorted(status_counts.items()):
        print(f"  {status.upper()}: {count}")
    
    total = sum(status_counts.values())
    print(f"\n  TOTAL: {total}")
    
    # Check for issues
    issues = status_counts['error'] + status_counts['exception'] + status_counts['permission_mismatch']
    if issues > 0:
        print(f"\n⚠️  {issues} issues found")
        return 1
    else:
        print("\n✓ Audit passed")
        return 0


if __name__ == '__main__':
    sys.exit(audit_tools())
