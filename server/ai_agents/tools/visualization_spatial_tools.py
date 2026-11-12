"""
Agent 12 - Visualization & Spatial Intelligence Tools
Makes the whole system feel like JARVIS inside VR.
"""

from typing import Optional, List, Dict, Any
import uuid
import time
from google.adk.tools import ToolContext
from ._safe import safe

# Helper to emit scene commands
def _emit_command(tool_context: ToolContext, command: str, **kwargs):
    """Queue a scene command to state['scene_commands']."""
    if tool_context is None:
        return  # No-op if no context (e.g., in tests)
    commands = tool_context.state.get('scene_commands', [])
    cmd_entry = {'type': command, **kwargs}
    commands.append(cmd_entry)
    tool_context.state['scene_commands'] = commands


# Helper functions for session-scoped state
def _get_session_state(tool_context: ToolContext, state_key: str, default=None):
    """Get session-scoped state for a given key using session_id."""
    if tool_context is None:
        return default
    # Try to get session_id from state or use a session-specific key
    session_id = tool_context.state.get('session_id', 'default')
    session_states = tool_context.state.get('session_states', {})
    session_data = session_states.get(session_id, {})
    return session_data.get(state_key, default)


def _set_session_state(tool_context: ToolContext, state_key: str, value):
    """Set session-scoped state for a given key using session_id."""
    if tool_context is None:
        return  # No-op if no context
    session_id = tool_context.state.get('session_id', 'default')
    session_states = tool_context.state.get('session_states', {})
    if session_id not in session_states:
        session_states[session_id] = {}
    session_states[session_id][state_key] = value
    tool_context.state['session_states'] = session_states


# Graph Tools

@safe
def create_graph(
    graph_id: str,
    graph_type: str,
    tool_context: ToolContext
) -> dict:
    """Create a new graph."""
    try:
        if not graph_id:
            graph_id = str(uuid.uuid4())
        
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        graph_state[graph_id] = {
            'type': graph_type,
            'nodes': {},
            'edges': {},
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'graph_state', graph_state)
        
        return {
            'status': 'ok',
            'graph_id': graph_id,
            'graph_type': graph_type,
            'created': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def expand_graph_node(
    graph_id: str,
    node_id: str,
    tool_context: ToolContext,
    depth: int = 1
) -> dict:
    """Expand a node to show its connections. Emits expand_node command."""
    try:
        _emit_command(tool_context, 'expand_node', node_id=node_id, depth=depth)

        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # Expand node by adding related nodes based on depth
        from .relationship_intelligence_tools import find_downstream_dependencies, find_shared_dependencies

        graph = graph_state[graph_id]

        # Add downstream dependencies
        dep_result = find_downstream_dependencies(node_id, tool_context)
        if dep_result.get('status') == 'ok':
            for dep in dep_result.get('dependencies', []):
                if dep not in [n['id'] for n in graph['nodes']]:
                    graph['nodes'].append({'id': dep, 'type': 'dependency'})
                    graph['edges'].append({'from': node_id, 'to': dep})

        # Add shared dependencies
        shared_result = find_shared_dependencies(node_id, tool_context)
        if shared_result.get('status') == 'ok':
            for shared in shared_result.get('shared_dependencies', []):
                if shared not in [n['id'] for n in graph['nodes']]:
                    graph['nodes'].append({'id': shared, 'type': 'shared'})
                    graph['edges'].append({'from': node_id, 'to': shared})

        node_count = len(graph['nodes'])
        edge_count = len(graph['edges'])
        _set_session_state(tool_context, 'graph_state', graph_state)

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'node_id': node_id,
            'depth': depth,
            'expanded': True,
            'total_nodes': node_count,
            'total_edges': edge_count,
            'command_queued': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def collapse_graph_node(
    graph_id: str,
    node_id: str,
    tool_context: ToolContext
) -> dict:
    """Collapse a node to hide its connections. Emits collapse_node command."""
    try:
        _emit_command(tool_context, 'collapse_node', node_id=node_id)

        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # In a real implementation, this would hide connected nodes in the visualization
        return {
            'status': 'ok',
            'graph_id': graph_id,
            'node_id': node_id,
            'collapsed': True,
            'note': 'Collapse requires VR rendering engine integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def search_graph(
    graph_id: str,
    query: str,
    tool_context: ToolContext
) -> dict:
    """Search for nodes in the graph."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        matches = []
        query_lower = query.lower()

        for node_id, node_data in graph_state[graph_id]['nodes'].items():
            # Search in node data
            for key, value in node_data.items():
                if query_lower in str(value).lower():
                    matches.append({
                        'node_id': node_id,
                        'relevance': 0.9,
                        'field': key
                    })
                    break

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'query': query,
            'matches': matches
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def highlight_path(
    graph_id: str,
    path: List[str],
    tool_context: ToolContext
) -> dict:
    """Highlight a path in the graph."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # Store highlight state
        graph_state[graph_id]['highlighted_path'] = path
        _set_session_state(tool_context, 'graph_state', graph_state)

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'path': path,
            'highlighted': True,
            'note': 'Highlighting requires VR rendering engine integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def highlight_dependencies(
    graph_id: str,
    node_id: str,
    tool_context: ToolContext,
    depth: int = 2
) -> dict:
    """Highlight dependencies of a node."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # Find connected nodes
        connected_nodes = set()
        for edge_key in graph_state[graph_id]['edges'].keys():
            if node_id in edge_key:
                parts = edge_key.split('->')
                connected_nodes.update(parts)

        graph_state[graph_id]['highlighted_nodes'] = list(connected_nodes)
        _set_session_state(tool_context, 'graph_state', graph_state)

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'node_id': node_id,
            'depth': depth,
            'highlighted_nodes': list(connected_nodes),
            'note': 'Highlighting requires VR rendering engine integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def isolate_subgraph(
    graph_id: str,
    node_ids: List[str],
    tool_context: ToolContext
) -> dict:
    """Show only a selected subgraph."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        graph_state[graph_id]['visible_nodes'] = node_ids
        _set_session_state(tool_context, 'graph_state', graph_state)

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'node_ids': node_ids,
            'isolated': True,
            'note': 'Isolation requires VR rendering engine integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def calculate_graph_layout(
    graph_id: str,
    tool_context: ToolContext,
    layout_algorithm: str = 'force_directed'
) -> dict:
    """Calculate graph layout."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # Simple circular layout for demo
        nodes = list(graph_state[graph_id]['nodes'].keys())
        positions = {}

        import math
        for i, node in enumerate(nodes):
            angle = 2 * math.pi * i / len(nodes)
            radius = 200
            positions[node] = {
                'x': radius * math.cos(angle),
                'y': radius * math.sin(angle)
            }

        graph_state[graph_id]['positions'] = positions
        _set_session_state(tool_context, 'graph_state', graph_state)

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'layout_algorithm': layout_algorithm,
            'positions': positions
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def summarize_graph(
    graph_id: str,
    tool_context: ToolContext
) -> dict:
    """Summarize graph statistics."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        graph = graph_state[graph_id]
        node_count = len(graph['nodes'])
        edge_count = len(graph['edges'])

        avg_degree = (2 * edge_count / node_count) if node_count > 0 else 0

        summary = {
            'total_nodes': node_count,
            'total_edges': edge_count,
            'avg_degree': avg_degree,
            'graph_type': graph.get('type', 'unknown')
        }

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'summary': summary
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Visualization Tools

@safe
def visualize_call_graph(
    function_id: str,
    tool_context: ToolContext,
    scope: str = 'local',
    depth: int = 2,
    include_possible: bool = False
) -> dict:
    """
    Visualize the call-graph neighborhood of a function and emit ``show_graph``.

    Uses the canonical CodeGraph so edges carry resolution metadata
    (callsite_id, resolution, confidence, reason). ``scope`` controls the
    neighborhood: 'local' = direct callers/callees, 'neighborhood' = multi-hop,
    'repo' = whole repository call graph. Uncertain edges (may_call) are only
    included when ``include_possible`` is true.
    """
    try:
        from ..intelligence.graph_engine.codegraph import load_current_graph

        viz_id = str(uuid.uuid4())
        graph = load_current_graph()

        # Whole-repository view
        if function_id in ('.', 'repo'):
            sub = graph.subgraph(
                [n['id'] for n in graph._nodes.values()
                 if n.get('level') in ('function', 'class') or n.get('kind') in ('function', 'method', 'object')],
                include_edges=True)
            nodes, edges = sub['nodes'], [
                e for e in sub['edges'] if e.get('type') in ('calls', 'may_call', 'inherits')]
            if not include_possible:
                edges = [e for e in edges if e.get('type') != 'may_call']
            _emit_command(tool_context, 'show_graph',
                          nodes=nodes, edges=edges,
                          title='Call Graph: repository')
            return {
                'status': 'ok', 'function_id': function_id, 'scope': scope,
                'visualization_id': viz_id,
                'nodes_count': len(nodes), 'edges_count': len(edges),
                'resolution_counts': _edge_resolution_counts(edges),
            }

        # Resolve the selected symbol strictly
        resolved = graph.resolve(function_id)
        if resolved['status'] == 'not_found':
            return {'status': 'error',
                    'error': f'Function not found in graph index: {function_id}'}
        if resolved['status'] == 'ambiguous':
            return {'status': 'ambiguous',
                    'message': f'"{function_id}" matches multiple symbols; '
                               'pass a full id such as file.py::Class.method',
                    'candidates': [c['id'] for c in resolved['candidates'][:20]]}
        target = resolved['node']

        # Neighborhood depth from scope
        eff_depth = {'local': 1, 'neighborhood': max(depth, 2), 'repo': 6}.get(scope, depth)
        sub = graph.neighborhood(target['id'], depth=eff_depth, direction='both',
                                 include_unresolved=include_possible,
                                 max_nodes=800)
        nodes = sub['nodes']
        edges = [e for e in sub['edges'] if e.get('type') in ('calls', 'may_call', 'inherits')]
        if not include_possible:
            edges = [e for e in edges if e.get('type') != 'may_call']

        _emit_command(tool_context, 'show_graph',
                      nodes=nodes, edges=edges,
                      title=f'Call Graph: {target.get("name", function_id)}',
                      callsite_metadata=True)

        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'call_graph',
            'function_id': target['id'],
            'scope': scope,
            'depth': eff_depth,
            'include_possible': include_possible,
            'nodes': nodes,
            'edges': edges,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)

        return {
            'status': 'ok',
            'function_id': target['id'],
            'scope': scope,
            'depth': eff_depth,
            'include_possible': include_possible,
            'visualization_id': viz_id,
            'nodes_count': len(nodes),
            'edges_count': len(edges),
            'truncated': sub.get('truncated', False),
            'resolution_counts': _edge_resolution_counts(edges),
            'note': 'Call graph emitted to VR scene'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def _edge_resolution_counts(edges):
    counts = {}
    for e in edges:
        key = e.get('resolution') or e.get('kind') or 'unknown'
        counts[key] = counts.get(key, 0) + 1
    return counts


@safe
def visualize_dependency_graph(
    component_id: str,
    tool_context: ToolContext,
    scope: str = 'direct'
) -> dict:
    """Visualize dependency graph using CodeGraph and emit_graph."""
    try:
        from ..intelligence.graph_engine.codegraph import codegraph

        graph = codegraph.load_current_graph()

        # Get module and file nodes
        nodes = [n for n in graph._nodes.values() if n.get('level') in ('module', 'file')]

        # Get import edges
        edges = [e for e in graph._raw_data.get('edges', []) if e.get('type') == 'imports']

        # Emit the graph to Unity
        _emit_command(tool_context, 'show_graph',
                     nodes=nodes,
                     edges=edges,
                     title=f'Dependency Graph: {component_id}')

        return {
            'status': 'ok',
            'component_id': component_id,
            'scope': scope,
            'node_count': len(nodes),
            'edge_count': len(edges)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_control_flow(
    function_id: str,
    tool_context: ToolContext
) -> dict:
    """Visualize control flow using graph emission."""
    try:
        from ..intelligence.controlflow import cfg_to_unity_format
        from ..intelligence.controlflow.service import analyze_python_control_flow
        from ..intelligence.graph_engine.codegraph import codegraph

        graph = codegraph.load_current_graph()
        node = graph.get(function_id)

        if not node:
            return {
                'status': 'not_found',
                'function_id': function_id,
                'message': 'Function not found in graph'
            }

        from ._common import abs_repo_path
        rel_file = node.get('file', '')
        with open(abs_repo_path(rel_file), 'r', encoding='utf-8') as f:
            source = f.read()

        # Build CFG using the service (qualname-aware lookup)
        symbol = {
            'id': node.get('id', function_id),
            'name': node.get('name', ''),
            'file': rel_file,
            'source': source,
            'qualname': node.get('qualname', node.get('id', function_id))
        }
        result = analyze_python_control_flow(graph, symbol, use_cache=False)

        if result.get('error'):
            return {
                'status': 'error',
                'function_id': function_id,
                'error': result['error']
            }

        cfg = result['graph']
        if not cfg:
            return {
                'status': 'error',
                'function_id': function_id,
                'error': 'CFG build failed'
            }

        # Convert to Unity format
        unity_graph = cfg_to_unity_format(cfg)

        # Emit the graph to Unity
        _emit_command(tool_context, 'show_graph',
                     nodes=unity_graph['nodes'],
                     edges=unity_graph['edges'],
                     title=f'Control Flow: {function_id}',
                     graph_type='control_flow')

        return {
            'status': 'ok',
            'function_id': function_id,
            'node_count': len(unity_graph['nodes']),
            'edge_count': len(unity_graph['edges']),
            'graph_type': 'control_flow'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# visualize_data_flow is implemented in data_flow_intelligence_tools.py
# This consolidates the implementation to avoid duplication


def _build_cfg_dfg_for_node(graph, node, function_id):
    """Build (cfg, dfg) for one graph function node.
    Returns (cfg, dfg) or raises; callers handle errors."""
    from ..intelligence.dataflow.repository_dfg import build_function_artifacts
    art = build_function_artifacts(graph, node, function_id)
    return art['cfg'], art['dfg']


@safe
def visualize_unified_graph(
    function_id: str,
    tool_context: ToolContext,
    summarize: bool = True,
    max_nodes: int = 100,
    repository_scope: bool = False,
    max_repository_functions: int = 8
) -> dict:
    """Visualize unified CFG and DFG graph with optional summarization.
    With repository_scope=True, merges the function's unified graph with
    its confirmed call neighbours (capped by max_repository_functions) and
    adds interprocedural edges labelled confirmed/possible."""
    try:
        from ..intelligence.controlflow import cfg_to_unity_format
        from ..intelligence.dataflow import dfg_to_unity_format
        from ..intelligence.dataflow.unified_graph import UnifiedGraphBuilder
        from ..intelligence.dataflow.graph_summarizer import GraphSummarizer
        from ..intelligence.graph_engine.codegraph import codegraph

        # Get the graph
        graph = codegraph.load_current_graph()
        node = graph.get(function_id)

        if not node:
            return {
                'status': 'not_found',
                'function_id': function_id,
                'message': 'Function not found in graph'
            }

        if repository_scope:
            return _visualize_repository_unified(
                graph, function_id, node, tool_context,
                max_repository_functions=max_repository_functions,
                summarize=summarize, max_nodes=max_nodes)

        cfg, dfg = _build_cfg_dfg_for_node(graph, node, function_id)

        # Build unified graph
        unified_builder = UnifiedGraphBuilder()
        unified_graph = unified_builder.build_unified(
            cfg,
            dfg
        )

        # Convert to Unity format
        unity_nodes = []
        unity_edges = []

        # Add CFG nodes
        for node_dict in cfg_to_unity_format(cfg)['nodes']:
            node_dict['layer'] = 'cfg'
            unity_nodes.append(node_dict)

        # Add DFG nodes
        for node_dict in dfg_to_unity_format(dfg)['nodes']:
            node_dict['layer'] = 'dfg'
            unity_nodes.append(node_dict)

        # Add CFG edges
        for edge_dict in cfg_to_unity_format(cfg)['edges']:
            edge_dict['layer'] = 'cfg'
            unity_edges.append(edge_dict)

        # Add DFG edges
        for edge_dict in dfg_to_unity_format(dfg)['edges']:
            edge_dict['layer'] = 'dfg'
            unity_edges.append(edge_dict)

        # Summarize if requested and graph is large
        was_summarized = False
        original_count = len(unity_nodes)
        if summarize and len(unity_nodes) > max_nodes:
            summarizer = GraphSummarizer(max_nodes_per_view=max_nodes)
            graph_dict = {
                'function_id': function_id,
                'nodes': unity_nodes,
                'edges': unity_edges
            }
            summary = summarizer.summarize_graph(graph_dict, function_id)
            unity_nodes = summary.summarized_nodes
            unity_edges = summary.summarized_edges
            was_summarized = True
            original_count = summary.original_node_count

        # Emit the unified graph to Unity
        _emit_command(tool_context, 'show_graph',
                     nodes=unity_nodes,
                     edges=unity_edges,
                     title=f'Unified Graph: {function_id}',
                     graph_type='unified')

        return {
            'status': 'ok',
            'function_id': function_id,
            'node_count': len(unity_nodes),
            'edge_count': len(unity_edges),
            'graph_type': 'unified',
            'cfg_nodes': len(cfg_to_unity_format(cfg)['nodes']),
            'dfg_nodes': len(dfg_to_unity_format(dfg)['nodes']),
            'summarized': was_summarized,
            'original_node_count': original_count
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def _visualize_repository_unified(graph, function_id, node, tool_context,
                                  max_repository_functions=8, summarize=True,
                                  max_nodes=100):
    """Repository-scope variant of visualize_unified_graph: merges the
    function's unified graph with confirmed call neighbours and labels
    interprocedural edges confirmed/possible."""
    from ..intelligence.controlflow import cfg_to_unity_format
    from ..intelligence.dataflow import dfg_to_unity_format
    from ..intelligence.dataflow.unified_graph import UnifiedGraphBuilder
    from ..intelligence.dataflow.graph_summarizer import GraphSummarizer

    if not (node.get('file') or '').endswith('.py'):
        return {'status': 'unsupported', 'function_id': function_id,
                'scope': 'repository',
                'message': 'Repository DFG visualization is only supported for Python'}

    # Confirmed call neighbours only — possible edges never enter the graph.
    neighbour_ids = []
    for direction in ('callees', 'callers'):
        try:
            entries = getattr(graph, direction)(
                function_id, depth=1, include_possible=False,
                include_ambiguous=False)
        except TypeError:
            entries = getattr(graph, direction)(function_id, depth=1)
        except Exception:
            entries = []
        for e in entries or []:
            tid = e.get('to') if direction == 'callees' else e.get('from')
            if tid and tid != function_id and tid not in neighbour_ids:
                neighbour_ids.append(tid)
            if len(neighbour_ids) >= max_repository_functions - 1:
                break
        if len(neighbour_ids) >= max_repository_functions - 1:
            break

    fids = [function_id] + neighbour_ids[:max_repository_functions - 1]
    function_graphs = {}
    dfg_by_fid = {}
    inter_edges = []
    skipped = []
    for fid in fids:
        n = graph.get(fid)
        if not n:
            skipped.append(fid)
            continue
        try:
            cfg, dfg = _build_cfg_dfg_for_node(graph, n, fid)
        except Exception:
            skipped.append(fid)
            continue
        function_graphs[fid] = UnifiedGraphBuilder().build_unified(cfg, dfg)
        dfg_by_fid[fid] = dfg

    # Interprocedural edges from the index's confirmed call edges.
    for fid in function_graphs:
        for direction, kind in (('callees', 'call'), ('callers', 'call')):
            try:
                entries = getattr(graph, direction)(
                    fid, depth=1, include_possible=False,
                    include_ambiguous=False)
            except Exception:
                entries = []
            for e in entries or []:
                other = e.get('to') if direction == 'callees' else e.get('from')
                if other not in function_graphs:
                    continue
                src, dst = (fid, other) if direction == 'callees' else (other, fid)
                inter_edges.append({
                    'source_function': src, 'target_function': dst,
                    'kind': kind,
                    'resolution': 'confirmed'
                    if (e.get('kind') == 'confirmed'
                        or e.get('resolution') in ('confirmed', 'static_resolved'))
                    else 'possible',
                    'call_site_id': e.get('callsite_id'),
                    'evidence': {'file': e.get('file'), 'line': e.get('line')}})

    # Interprocedural argument/return edges from the repository DFG pipeline.
    dfg_counts = {'argument_edges': 0, 'return_edges': 0,
                  'global_edges': 0, 'unresolved': 0}
    dfg_status = 'completed'
    dfg_diagnostics = []
    try:
        from ..intelligence.dataflow.repository_dfg import build_repository_dfg
        repo_dfg = build_repository_dfg(graph, function_ids=list(function_graphs))
        dfg_counts['unresolved'] = len(repo_dfg.unresolved)
        for e in repo_dfg.edges:
            if e.source_kind == 'argument':
                sf, tf = e.caller_function_id, e.callee_function_id
            else:
                sf, tf = e.callee_function_id, e.caller_function_id
            if sf not in function_graphs or tf not in function_graphs:
                continue
            f2n_src = ((dfg_by_fid.get(sf).metadata or {}).get('fact_to_node', {})
                       if dfg_by_fid.get(sf) is not None else {})
            f2n_dst = ((dfg_by_fid.get(tf).metadata or {}).get('fact_to_node', {})
                       if dfg_by_fid.get(tf) is not None else {})
            inter_edges.append({
                'source_function': sf, 'target_function': tf,
                'kind': e.source_kind,
                'resolution': e.resolution,
                'call_site_id': e.call_site_id,
                'source_node': f2n_src.get(e.source_id),
                'target_node': f2n_dst.get(e.target_id),
                'file': e.source_file, 'line': e.source_line,
                'evidence': {'file': e.source_file, 'line': e.source_line,
                             'target_file': e.target_file,
                             'target_line': e.target_line}})
            if e.source_kind == 'argument':
                dfg_counts['argument_edges'] += 1
            else:
                dfg_counts['return_edges'] += 1

        # Global (cross-module) edges: module-level definitions have no
        # function, so endpoints are explicit node ids — a 'module_data'
        # node for the exporting definition and the consuming function's
        # unified DFG node for the use.
        use_owner = {}
        for fid, rd in (repo_dfg.reaching or {}).items():
            f2n = ((dfg_by_fid.get(fid).metadata or {}).get('fact_to_node', {})
                   if dfg_by_fid.get(fid) is not None else {})
            for u in rd.facts.uses:
                use_owner[u.id] = (fid, f2n.get(u.id))
        module_nodes = {}
        for g in repo_dfg.global_edges or []:
            src_def = g.get('source')
            tgt_use = g.get('target')
            owner = use_owner.get(tgt_use)
            if not src_def or owner is None:
                continue
            fid, dfg_node = owner
            if dfg_node is None:
                continue
            src_node_id = 'module_data::%s' % src_def
            if src_node_id not in module_nodes:
                module_nodes[src_node_id] = {
                    'id': src_node_id, 'kind': 'module_data',
                    'file': g.get('source_file') or g.get('target_file'),
                    'line': g.get('source_line') or g.get('line') or 0,
                    'variable': src_def,
                    'function_id': ''}
            tgt_node_id = '%s::unified_%s' % (fid, dfg_node)
            inter_edges.append({
                'kind': 'global',
                'resolution': g.get('resolution', 'possible'),
                'source_node_id': src_node_id,
                'target_node_id': tgt_node_id,
                'nodes': [module_nodes[src_node_id]],
                'call_site_id': None,
                'evidence': {
                    'file': g.get('file'), 'line': g.get('line'),
                    'source_file': g.get('source_file')
                    or g.get('target_file'),
                    'source_line': g.get('source_line'),
                    'target_file': g.get('target_file') or g.get('file'),
                    'target_line': g.get('target_line'),
                    'resolution': g.get('resolution'),
                    'scope': g.get('scope'),
                    'binding_key': g.get('binding_key')}})
            dfg_counts['global_edges'] += 1
    except Exception as exc:
        dfg_status = 'failed'
        dfg_diagnostics.append({'stage': 'global_edges',
                                'error': type(exc).__name__,
                                'message': str(exc)})

    repo_graph = UnifiedGraphBuilder().build_repository_graph(
        function_graphs, inter_edges)

    # Serialize every node the merged repository graph actually contains —
    # including module_data nodes added by global edges — so edge endpoints
    # never dangle. Node and edge ids already share the '<fid>::<id>' scheme.
    unity_nodes, unity_edges = [], []
    for n in repo_graph.nodes:
        meta = n.metadata or {}
        unity_nodes.append({
            'id': n.id,
            'label': meta.get('variable') or meta.get('label') or n.id,
            'kind': n.kind, 'layer': 'unified',
            'file': n.file, 'line': n.line,
            'function_id': n.function_id,
            'metadata': meta})
    for e in repo_graph.edges:
        unity_edges.append({'src': e.source, 'dst': e.target,
                            'kind': e.kind, 'layer': 'unified',
                            'resolution': e.subkind})

    node_ids = {n['id'] for n in unity_nodes}
    dangling = [e for e in unity_edges
                if e['src'] not in node_ids or e['dst'] not in node_ids]
    if dangling:
        # Never emit edges Unity cannot resolve; record them instead.
        unity_edges = [e for e in unity_edges
                       if e['src'] in node_ids and e['dst'] in node_ids]
        dfg_diagnostics.append({'stage': 'serialize',
                                'error': 'DanglingEdge',
                                'message': '%d edge(s) reference missing nodes'
                                           % len(dangling),
                                'edges': [{'src': e['src'], 'dst': e['dst'],
                                           'kind': e['kind']}
                                          for e in dangling[:20]]})
        if dfg_status == 'completed':
            dfg_status = 'partial'
    if dfg_status == 'completed' and any(
            e.get('resolution') != 'confirmed' for e in unity_edges):
        dfg_status = 'partial'

    was_summarized = False
    original_count = len(unity_nodes)
    if summarize and len(unity_nodes) > max_nodes:
        summarizer = GraphSummarizer(max_nodes_per_view=max_nodes)
        summary = summarizer.summarize_graph(
            {'function_id': 'repository', 'nodes': unity_nodes,
             'edges': unity_edges}, 'repository')
        unity_nodes = summary.summarized_nodes
        unity_edges = summary.summarized_edges
        was_summarized = True
        original_count = summary.original_node_count

    _emit_command(tool_context, 'show_graph',
                  nodes=unity_nodes, edges=unity_edges,
                  title='Repository Unified Graph: %s' % function_id,
                  graph_type='unified_repository')

    return {
        'status': 'ok',
        'function_id': function_id,
        'scope': 'repository',
        'function_ids': sorted(function_graphs),
        'skipped_functions': skipped,
        'node_count': len(unity_nodes),
        'edge_count': len(unity_edges),
        'graph_type': 'unified_repository',
        'truncated': repo_graph.metadata.get('truncated', False),
        'summarized': was_summarized,
        'original_node_count': original_count,
        'dfg_status': dfg_status,
        'diagnostics': dfg_diagnostics,
        **dfg_counts,
    }


@safe
def visualize_architecture(
    tool_context: ToolContext,
    scope: str = 'full'
) -> dict:
    """Visualize architecture using CodeGraph with real module/file nodes."""
    try:
        from ..intelligence.graph_engine.codegraph import codegraph

        graph = codegraph.load_current_graph()

        # Get module, file, and class nodes (skip leaf functions for high-level view)
        architecture_nodes = []
        for node_id, node in graph._nodes.items():
            if node.get('level') in ('module', 'file', 'class'):
                architecture_nodes.append(node)

        # Get contains edges (hierarchy) and imports edges (dependencies)
        architecture_edges = []
        for edge in graph._raw_data.get('edges', []):
            if edge.get('type') in ('contains', 'imports'):
                # Only include edges between architecture nodes
                src_id = edge.get('src')
                dst_id = edge.get('dst')
                if (src_id in graph._nodes and graph._nodes[src_id].get('level') in ('module', 'file', 'class') and
                    dst_id in graph._nodes and graph._nodes[dst_id].get('level') in ('module', 'file', 'class')):
                    architecture_edges.append(edge)

        # Emit the graph to Unity
        _emit_command(tool_context, 'show_graph',
                     nodes=architecture_nodes,
                     edges=architecture_edges,
                     title='Architecture Map')

        return {
            'status': 'ok',
            'scope': scope,
            'node_count': len(architecture_nodes),
            'edge_count': len(architecture_edges)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_change_impact(
    element_id: str,
    tool_context: ToolContext
) -> dict:
    """Visualize change impact using scene commands.

    Three test states are separate:
        - Associated: Test appears related to this function
        - Execution status: Passed, failed or not run
        - Code coverage: Measured coverage percentage or unknown
    """
    try:
        from .relationship_intelligence_tools import calculate_change_impact

        # Get the impact analysis
        impact_result = calculate_change_impact(element_id, tool_context)

        if impact_result.get('status') != 'ok':
            return impact_result

        # Build the list of affected node IDs (changed function + dependents)
        affected_ids = [element_id]
        for caller in impact_result.get('direct_callers', []):
            affected_ids.append(caller['from'])
        for dep in impact_result.get('indirect_dependents', []):
            affected_ids.append(dep['id'])
        for imp in impact_result.get('import_dependents', []):
            affected_ids.append(imp['id'])

        # Extract actual test IDs from covering tests
        # Each test object should have an 'id' field and a 'covers' field (list of function IDs)
        test_ids = []
        for test in impact_result.get('covering_tests', []):
            if 'id' in test:
                test_ids.append(test['id'])

        # Separate tests by execution status with names
        # Each test should have: id, name, status (passed/failed/not_run), coverage
        passed = []
        failed = []
        not_run = []
        for test in impact_result.get('covering_tests', []):
            test_id = test.get('id', '')
            test_name = test.get('name', test_id)
            status = test.get('status', 'not_run')  # passed, failed, or not_run
            if status == 'passed':
                passed.append(test_name)
            elif status == 'failed':
                failed.append(test_name)
            else:
                not_run.append(test_name)

        # Build lists of actual function names for display
        direct_caller_names = [c.get('name', c['from']) for c in impact_result.get('direct_callers', [])]
        indirect_dependent_names = [d.get('name', d['id']) for d in impact_result.get('indirect_dependents', [])]
        possible_caller_names = [c.get('name', c['from']) for c in impact_result.get('possible_callers', [])]
        import_dependent_names = [i.get('name', i['id']) for i in impact_result.get('import_dependents', [])]

        # Get the changed function name
        changed_function_name = element_id
        # Try to get the actual name from the graph
        from ..intelligence.graph_engine.codegraph import codegraph
        graph = codegraph.load_current_graph()
        node = graph.get(element_id)
        if node:
            changed_function_name = node.get('name', element_id)

        # Emit scene commands
        _emit_command(tool_context, 'dim_unrelated', keep_ids=affected_ids)
        _emit_command(tool_context, 'highlight_path', node_ids=affected_ids)
        _emit_command(tool_context, 'show_test_badges', passed=passed, failed=failed, not_run=not_run)
        _emit_command(tool_context, 'focus_camera', node_id=element_id)
        _emit_command(tool_context, 'show_impact_panel',
                     text=changed_function_name,
                     summary=impact_result.get('risk_level', 'unknown'),
                     depth=impact_result.get('direct_count', 0),
                     node_ids=affected_ids,
                     keep_ids=test_ids,
                     direct_callers=direct_caller_names,
                     indirect_dependents=indirect_dependent_names,
                     possible_callers=possible_caller_names,
                     import_dependents=import_dependent_names,
                     passed_tests=passed,
                     failed_tests=failed,
                     not_run_tests=not_run,
                     test_mapping=impact_result.get('test_mapping', ''),
                     risk_basis=impact_result.get('risk_basis', ''))

        return {
            'status': 'ok',
            'element_id': element_id,
            'direct_count': impact_result.get('direct_count', 0),
            'indirect_count': impact_result.get('indirect_count', 0),
            'possible_count': impact_result.get('possible_count', 0),
            'import_count': impact_result.get('import_count', 0),
            'total_affected': impact_result.get('total_affected', 0),
            'risk_level': impact_result.get('risk_level', 'unknown'),
            'untested': impact_result.get('untested', False),
            'test_count': len(test_ids)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Spatial Tools

@safe
def get_current_selection(tool_context: ToolContext) -> dict:
    """Identify the currently selected code element or graph node."""
    try:
        spatial_state = _get_session_state(tool_context, 'spatial_state', {})
        return {
            'status': 'ok',
            'selection': spatial_state.get('current_selection', {
                'type': 'none',
                'id': None
            }),
            'note': 'Selection requires VR input integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_spatial_selection_context(tool_context: ToolContext) -> dict:
    """Understand the selected object's surrounding relationships."""
    try:
        spatial_state = _get_session_state(tool_context, 'spatial_state', {})
        selection = spatial_state.get('current_selection', {})
        node_id = selection.get('id')

        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if node_id and node_id in graph_state:
            graph = graph_state[node_id]
            connected = [k for k in graph['edges'].keys() if node_id in k]

            return {
                'status': 'ok',
                'context': {
                    'selected_node': node_id,
                    'connected_nodes': connected
                }
            }

        return {
            'status': 'ok',
            'context': {
                'selected_node': None,
                'connected_nodes': []
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def select_code_element(
    element_id: str,
    tool_context: ToolContext
) -> dict:
    """Select a function, class, file or other code element. Emits select_node command."""
    try:
        _emit_command(tool_context, 'select_node', node_id=element_id)

        spatial_state = _get_session_state(tool_context, 'spatial_state', {})
        spatial_state['current_selection'] = {
            'type': 'code_element',
            'id': element_id
        }
        _set_session_state(tool_context, 'spatial_state', spatial_state)

        return {
            'status': 'ok',
            'element_id': element_id,
            'selected': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def focus_on_object(
    object_id: str,
    tool_context: ToolContext
) -> dict:
    """Bring an object into focus."""
    try:
        spatial_state = _get_session_state(tool_context, 'spatial_state', {})
        spatial_state['focused_object'] = object_id
        _set_session_state(tool_context, 'spatial_state', spatial_state)

        return {
            'status': 'ok',
            'object_id': object_id,
            'focused': True,
            'note': 'Focus requires VR rendering engine integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def expand_relationships(
    object_id: str,
    tool_context: ToolContext,
    relationship_type: Optional[str] = None
) -> dict:
    """Reveal connected code elements."""
    try:
        return {
            'status': 'ok',
            'object_id': object_id,
            'relationship_type': relationship_type,
            'note': 'Expansion requires code intelligence integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def trace_relationship_path(
    from_id: str,
    to_id: str,
    tool_context: ToolContext
) -> dict:
    """Follow a selected relationship through the graph."""
    try:
        # Find a path using BFS
        path = [from_id, to_id]  # Simplified
        
        return {
            'status': 'ok',
            'from_id': from_id,
            'to_id': to_id,
            'path': path,
            'highlighted': True,
            'note': 'Real path finding requires graph algorithms'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def isolate_relationship_path(
    path: List[str],
    tool_context: ToolContext
) -> dict:
    """Show only a particular investigation path."""
    try:
        spatial_state = _get_session_state(tool_context, 'spatial_state', {})
        spatial_state['isolated_path'] = path
        _set_session_state(tool_context, 'spatial_state', spatial_state)

        return {
            'status': 'ok',
            'path': path,
            'isolated': True,
            'note': 'Isolation requires VR rendering engine integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def show_graph(
    nodes: List[Dict],
    edges: List[Dict],
    tool_context: ToolContext
) -> dict:
    """Replace the visible graph with a new node/edge list. Emits show_graph command."""
    try:
        _emit_command(tool_context, 'show_graph', nodes=nodes, edges=edges)

        return {
            'status': 'ok',
            'node_count': len(nodes),
            'edge_count': len(edges),
            'command_queued': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_spatial_object_details(
    object_id: str,
    tool_context: ToolContext
) -> dict:
    """Retrieve information about a selected spatial object."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        # Try to find object in graph state
        for graph_id, graph in graph_state.items():
            if object_id in graph['nodes']:
                return {
                    'status': 'ok',
                    'object_id': object_id,
                    'details': graph['nodes'][object_id]
                }

        return {
            'status': 'not_found',
            'object_id': object_id,
            'message': 'Object not found in any graph'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# Aliases for missing spatial tools to match expected tool names
# These are wrapper functions that alias to existing implementations
@safe
def focus_on_graph_node(
    graph_id: str,
    node_id: str,
    tool_context: ToolContext,
    depth: int = 1
) -> dict:
    """Alias for expand_graph_node."""
    return expand_graph_node(graph_id, node_id, tool_context, depth)


@safe
def navigate_to_code_element(
    node_id: str,
    tool_context: ToolContext
) -> dict:
    """Alias for select_code_element."""
    return select_code_element(node_id, tool_context)


@safe
def navigate_to_relationship(
    node_id: str,
    tool_context: ToolContext
) -> dict:
    """Alias for trace_relationship_path."""
    return trace_relationship_path(node_id, tool_context)


@safe
def get_selected_node_details(
    object_id: str,
    tool_context: ToolContext
) -> dict:
    """Alias for get_spatial_object_details."""
    return get_spatial_object_details(object_id, tool_context)


@safe
def get_current_spatial_context(
    tool_context: ToolContext
) -> dict:
    """Alias for get_spatial_selection_context."""
    return get_spatial_selection_context(tool_context)


@safe
def explain_graph_edge(
    graph_id: str,
    edge_id: str,
    tool_context: ToolContext
) -> dict:
    """Explain a graph edge with plain-language reasoning."""
    try:
        from ..intelligence.dataflow.edge_explainer import EdgeExplainer

        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # Find the edge
        edge = None
        for edge_key, edge_data in graph_state[graph_id]['edges'].items():
            if edge_data.get('edge_id') == edge_id:
                edge = edge_data
                edge['id'] = edge_id
                break

        if not edge:
            return {
                'status': 'error',
                'error': f'Edge {edge_id} not found'
            }

        # Get nodes
        nodes = {node_id: node_data for node_id, node_data in graph_state[graph_id]['nodes'].items()}

        # Generate explanation
        explainer = EdgeExplainer()
        explanation = explainer.explain_edge(edge_id, edge, nodes)

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'edge_id': edge_id,
            'explanation': explanation.explanation,
            'rule': explanation.rule,
            'source_span': explanation.source_span,
            'confidence': explanation.confidence,
            'metadata': explanation.metadata
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def query_graph_path(
    graph_id: str,
    start_node: str,
    end_node: str,
    tool_context: ToolContext,
    query_type: str = 'shortest',
    max_depth: int = 20
) -> dict:
    """Query paths in the graph (shortest or all paths)."""
    try:
        from ..intelligence.dataflow.path_queries import PathQueryEngine

        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # Build graph dict for path engine
        graph_dict = {
            'nodes': graph_state[graph_id]['nodes'],
            'edges': graph_state[graph_id]['edges']
        }

        engine = PathQueryEngine()

        if query_type == 'shortest':
            path = engine.find_shortest_path(graph_dict, start_node, end_node)
            if path:
                # Highlight the path
                highlight = engine.highlight_path(graph_dict, path)
                _emit_command(tool_context, 'highlight_path',
                             highlighted_nodes=highlight['highlighted_nodes'],
                             highlighted_edges=highlight['highlighted_edges'])

                return {
                    'status': 'ok',
                    'graph_id': graph_id,
                    'query_type': 'shortest',
                    'path': path,
                    'path_length': len(path),
                    'highlighted': True
                }
            else:
                return {
                    'status': 'ok',
                    'graph_id': graph_id,
                    'query_type': 'shortest',
                    'path': None,
                    'message': 'No path found'
                }
        elif query_type == 'all':
            result = engine.find_all_paths(graph_dict, start_node, end_node, max_depth=max_depth)
            return {
                'status': 'ok',
                'graph_id': graph_id,
                'query_type': 'all',
                'paths': result.paths,
                'shortest_path': result.shortest_path,
                'all_paths_count': result.all_paths_count,
                'metadata': result.metadata
            }
        else:
            return {
                'status': 'error',
                'error': f'Unknown query type: {query_type}'
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def expand_graph_neighborhood(
    graph_id: str,
    focus_node: str,
    tool_context: ToolContext,
    depth: int = 2
) -> dict:
    """Expand a neighborhood around a focus node for large graphs."""
    try:
        from ..intelligence.dataflow.graph_summarizer import GraphSummarizer

        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # Build graph dict
        graph_dict = {
            'nodes': graph_state[graph_id]['nodes'],
            'edges': graph_state[graph_id]['edges']
        }

        summarizer = GraphSummarizer()
        neighborhood = summarizer.stream_neighborhood(graph_dict, focus_node, depth)

        # Update graph state with expanded neighborhood
        for node in neighborhood.nodes:
            graph_state[graph_id]['nodes'][node['id']] = node

        for edge in neighborhood.edges:
            edge_key = f"{edge['source']}->{edge['target']}"
            graph_state[graph_id]['edges'][edge_key] = edge

        _set_session_state(tool_context, 'graph_state', graph_state)

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'focus_node': focus_node,
            'depth': depth,
            'nodes_added': len(neighborhood.nodes),
            'edges_added': len(neighborhood.edges),
            'has_more': neighborhood.has_more,
            'cursor': neighborhood.cursor
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def focus_on_code_element(
    node_id: str,
    tool_context: ToolContext
) -> dict:
    """Alias for focus_on_object."""
    return focus_on_object(node_id, tool_context)
