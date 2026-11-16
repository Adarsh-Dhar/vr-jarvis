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
import json
import typing
from pathlib import Path
import time
from collections import defaultdict

# Add server to path
server_dir = Path(__file__).parent.parent / 'server'
sys.path.insert(0, str(server_dir))

# Load the repo .env so API keys are available when the script is run directly
# (start.sh exports them for the server; a bare `python scripts/audit_tools.py`
# otherwise sees no keys and every LLM-backed tool silently falls back).
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except Exception:
    pass

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


def _load_fixtures():
    """Best-effort real values from the active repository index, so read tools
    are exercised against real data instead of only rejecting empty input."""
    fx = {'repo_root': '', 'repo_name': '', 'file': '', 'dir': '',
          'node_id': '', 'node_name': ''}
    try:
        from ai_agents import config
        root = Path(config.REPO_ROOT)
        fx['repo_root'] = str(root)
        fx['repo_name'] = root.name
        idx = Path(config.INDEX_DIR) / (root.name + '.json')
        if idx.is_file():
            data = json.loads(idx.read_text())
            for n in data.get('nodes') or []:
                if n.get('kind') == 'function' and n.get('id'):
                    fx['node_id'] = n['id']
                    fx['node_name'] = n.get('name') or ''
                    if n.get('file'):
                        fx['file'] = n['file']
                        fx['dir'] = str(Path(n['file']).parent)
                    break
        if not fx['file'] and root.is_dir():
            for p in root.rglob('*'):
                if p.is_file():
                    fx['file'] = str(p.relative_to(root))
                    fx['dir'] = str(Path(fx['file']).parent)
                    break
    except Exception:
        pass
    return fx


def _is_dictish(ann):
    while typing.get_origin(ann) is typing.Annotated:
        ann = typing.get_args(ann)[0]
    if ann is dict or typing.get_origin(ann) is dict:
        return True
    return isinstance(ann, type) and issubclass(ann, dict)


_NODE_ID_PARAMS = {
    'node_id', 'from_id', 'to_id', 'src_id', 'dst_id', 'src', 'dst',
    'start_node', 'end_node', 'focus_node', 'element_id', 'element1_id',
    'element2_id', 'object_id', 'function_id', 'class_id', 'interface_id',
    'module_id', 'component_id',
}
_EMPTY_ID_PARAMS = {
    'graph_id', 'edge_id', 'session_id', 'conversation_id', 'investigation_id',
    'visualization_id', 'repository_id', 'task_id', 'request_id', 'trace_id',
    'callsite_id', 'condition_id',
}
_TEXT_VALUES = {
    'claim': 'audit smoke-test claim',
    'action_summary': 'audit smoke-test action',
    'task': 'audit smoke-test task',
    'idea_text': 'a small queue service',
    'user_message': 'hello',
    'text': 'hello',
    'summary': 'audit summary',
    'diff': 'audit diff',
    'verification_status': 'verified',
    'verification_notes': 'audit note',
    'parameter': 'x',
    'agent': 'investigator_agent',
    'style': 'solid',
    'state': 'show',
    'mode': 'CODE',
    'graph_type': 'call_graph',
}


def _value_for_name(name, tool_name, fx):
    if name in ('repository_path', 'repo_path'):
        return fx['repo_root'] or '.'
    if name in ('repo', 'name'):
        return fx['repo_name'] or '.'
    if name == 'path':
        # browse_vr_folder wants a directory; every other 'path' param wants a file.
        return (fx['dir'] if tool_name == 'browse_vr_folder' else fx['file']) or '.'
    if name == 'file_path':
        return fx['file'] or '.'
    if name in ('directory', 'dir', 'folder', 'module_path'):
        return fx['dir'] or '.'
    if name == 'graph_id':
        return 'audit_graph'
    if name in _EMPTY_ID_PARAMS:
        return ''
    if name == 'module_id':
        # trace_cross_module_relationships accepts a folder path or '.'.
        return fx['dir'] or '.'
    if name in _NODE_ID_PARAMS:
        return fx['node_id'] or ''
    if name in ('symbol_name', 'function_name', 'query'):
        return fx['node_name'] or ''
    if name == 'variable_id':
        return '%s:x' % fx['node_name'] if fx['node_name'] else ''
    if name == 'direction':
        return 'right' if tool_name == 'move_graph' else 'both'
    if name == 'panel':
        return 'status'
    if name == 'question':
        return 'what does %s do?' % (fx['node_name'] or 'this code')
    if name == 'request':
        return 'explain %s' % (fx['node_name'] or 'the code')
    if name in _TEXT_VALUES:
        return _TEXT_VALUES[name]
    return ''


def _placeholder(param, tool_name, fx):
    """Pick a type-appropriate placeholder for a required parameter."""
    ann = param.annotation
    if ann is inspect.Parameter.empty:
        ann = str
    while True:
        origin = typing.get_origin(ann)
        args = typing.get_args(ann)
        if origin is typing.Annotated:
            ann = args[0]
            continue
        if origin is typing.Literal and args:
            return args[0]
        if origin is typing.Union:
            if str in args:
                ann = str
                continue
            inner = next((a for a in args if a is not type(None)), str)
            ann = inner
            continue
        break
    if ann is bool:
        return False
    if ann is int:
        return 1
    if ann is float:
        return 1.0
    if ann is bytes:
        return b''
    if ann in (list, tuple, set) or typing.get_origin(ann) in (list, tuple, set):
        args = typing.get_args(ann)
        name = param.name.lower()
        if args and _is_dictish(args[0]):
            return [{}]
        if 'failed' in name or 'not_run' in name:
            return []
        if 'id' in name:
            return [fx['node_id']] if fx['node_id'] else []
        return []
    if _is_dictish(ann):
        return {}
    pname = param.name.lower()
    if pname == 'edge_id':
        return 'audit_edge'
    if pname == 'conversation_id':
        return 'audit_conv'
    if pname == 'investigation_id':
        return 'audit_inv'
    return _value_for_name(pname, tool_name, fx)


def audit_tools():
    """Run audit on all tools."""
    print("=" * 80)
    print("JARVIS TOOL AUDIT")
    print("=" * 80)
    print()

    fixtures = _load_fixtures()
    print(f"Fixtures: repo={fixtures['repo_name'] or '?'} file={fixtures['file'] or '?'} "
          f"node={fixtures['node_id'] or '?'}")
    print()

    # Seed conversational memory so id-based lookups have something to find.
    try:
        from ai_agents.tools import conversational_tools as _conv
        _conv._conversation_state['audit_conv'] = {
            'turn': 1, 'state': 'initial',
            'history': [{'turn': 1, 'user': 'audit', 'timestamp': 0}],
            'created_at': 0}
        _conv._investigation_memory['audit_inv'] = {
            'summary': 'audit investigation',
            'key_points': ['audit point']}
    except Exception:
        pass

    # Count tools by status
    status_counts = defaultdict(int)
    results_by_agent = defaultdict(list)

    # Iterate through all toolsets
    for agent_name, tool_names in TOOLSETS.items():
        print(f"\nAgent: {agent_name} (ceiling: {PERMISSION_CEILINGS.get(agent_name, 'read')})")
        print("-" * 80)

        # One shared context per agent so state written by one tool (findings,
        # graphs, scene commands) is visible to the agent's later tools.
        tool_context = MockToolContext()

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
                # Get tool signature to determine required args
                sig = inspect.signature(tool_func)
                params = sig.parameters

                # Build minimal args, type- and name-aware
                kwargs = {}
                for param_name, param in params.items():
                    if param_name == 'tool_context':
                        kwargs['tool_context'] = tool_context
                    elif param.default == inspect.Parameter.empty:
                        kwargs[param_name] = _placeholder(param, tool_name, fixtures)
                
                # Call the tool
                start = time.time()
                result_dict = tool_func(**kwargs)
                duration = time.time() - start

                # Seed one edge into the audit graph so edge/path tools have
                # something to traverse (create_graph only makes an empty graph).
                if agent_name == 'visualization_spatial' and tool_name == 'create_graph':
                    try:
                        node_id = fixtures['node_id'] or 'audit_node'
                        node2 = fixtures['node_id'] + '::caller' if fixtures['node_id'] else 'audit_node2'
                        ss = tool_context.state.setdefault('session_states', {}).setdefault('default', {})
                        g = ss.setdefault('graph_state', {}).setdefault(
                            'audit_graph', {'type': 'call_graph', 'nodes': {}, 'edges': {}})
                        for nid in (node_id, node2):
                            g['nodes'][nid] = {'id': nid, 'name': nid.split('::')[-1],
                                               'label': nid.split('::')[-1]}
                        g['edges']['audit_edge'] = {
                            'edge_id': 'audit_edge', 'src': node_id, 'dst': node2,
                            'source': node_id, 'target': node2, 'type': 'calls'}
                    except Exception:
                        pass
                
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
