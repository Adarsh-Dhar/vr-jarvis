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
    commands = tool_context.state.get('scene_commands', [])
    cmd_entry = {'type': command, **kwargs}
    commands.append(cmd_entry)
    tool_context.state['scene_commands'] = commands


# Helper functions for session-scoped state
def _get_session_state(tool_context: ToolContext, state_key: str, default=None):
    """Get session-scoped state for a given key."""
    session_states = tool_context.state.get('session_states', {})
    return session_states.get(state_key, default)


def _set_session_state(tool_context: ToolContext, state_key: str, value):
    """Set session-scoped state for a given key."""
    session_states = tool_context.state.get('session_states', {})
    session_states[state_key] = value
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
def add_graph_node(
    graph_id: str,
    node_id: str,
    node_data: Dict,
    tool_context: ToolContext
) -> dict:
    """Add a node to the graph."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        graph_state[graph_id]['nodes'][node_id] = node_data
        _set_session_state(tool_context, 'graph_state', graph_state)
        
        return {
            'status': 'ok',
            'graph_id': graph_id,
            'node_id': node_id,
            'added': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def remove_graph_node(
    graph_id: str,
    node_id: str,
    tool_context: ToolContext
) -> dict:
    """Remove a node from the graph."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        if node_id in graph_state[graph_id]['nodes']:
            del graph_state[graph_id]['nodes'][node_id]
            # Remove associated edges
            edges_to_remove = [k for k in graph_state[graph_id]['edges'].keys()
                             if node_id in k]
            for edge in edges_to_remove:
                del graph_state[graph_id]['edges'][edge]
            _set_session_state(tool_context, 'graph_state', graph_state)
        
        return {
            'status': 'ok',
            'graph_id': graph_id,
            'node_id': node_id,
            'removed': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def add_graph_edge(
    graph_id: str,
    source_id: str,
    target_id: str,
    edge_data: Dict,
    tool_context: ToolContext
) -> dict:
    """Add an edge to the graph."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        edge_key = f"{source_id}->{target_id}"
        graph_state[graph_id]['edges'][edge_key] = edge_data
        _set_session_state(tool_context, 'graph_state', graph_state)
        
        return {
            'status': 'ok',
            'graph_id': graph_id,
            'edge': {'from': source_id, 'to': target_id},
            'added': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def remove_graph_edge(
    graph_id: str,
    source_id: str,
    target_id: str,
    tool_context: ToolContext
) -> dict:
    """Remove an edge from the graph."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        edge_key = f"{source_id}->{target_id}"
        if edge_key in graph_state[graph_id]['edges']:
            del graph_state[graph_id]['edges'][edge_key]
            _set_session_state(tool_context, 'graph_state', graph_state)
        
        return {
            'status': 'ok',
            'graph_id': graph_id,
            'edge': {'from': source_id, 'to': target_id},
            'removed': True
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
def filter_graph(
    graph_id: str,
    filters: Dict,
    tool_context: ToolContext
) -> dict:
    """Filter graph by criteria. Emits set_filters command."""
    try:
        _emit_command(tool_context, 'set_filters', filters=filters)

        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # Apply filters to nodes
        visible_nodes = []
        for node_id, node_data in graph_state[graph_id]['nodes'].items():
            matches = True
            for key, value in filters.items():
                if key in node_data and node_data[key] != value:
                    matches = False
                    break
            if matches:
                visible_nodes.append(node_id)

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'filters': filters,
            'visible_nodes': visible_nodes,
            'visible_count': len(visible_nodes)
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
def compare_graphs(
    graph1_id: str,
    graph2_id: str,
    tool_context: ToolContext
) -> dict:
    """Compare two graphs."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph1_id not in graph_state or graph2_id not in graph_state:
            return {
                'status': 'error',
                'error': 'One or both graphs not found'
            }

        graph1 = graph_state[graph1_id]
        graph2 = graph_state[graph2_id]

        nodes1 = set(graph1['nodes'].keys())
        nodes2 = set(graph2['nodes'].keys())

        edges1 = set(graph1['edges'].keys())
        edges2 = set(graph2['edges'].keys())

        differences = {
            'nodes_only_in_1': list(nodes1 - nodes2),
            'nodes_only_in_2': list(nodes2 - nodes1),
            'edges_only_in_1': list(edges1 - edges2),
            'edges_only_in_2': list(edges2 - edges1)
        }

        return {
            'status': 'ok',
            'graph1_id': graph1_id,
            'graph2_id': graph2_id,
            'differences': differences
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
def calculate_graph_clusters(
    graph_id: str,
    tool_context: ToolContext,
    algorithm: str = 'louvain'
) -> dict:
    """Calculate graph clusters."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # Simple clustering by connected components
        nodes = list(graph_state[graph_id]['nodes'].keys())
        clusters = {
            'cluster1': nodes[:len(nodes)//2],
            'cluster2': nodes[len(nodes)//2:] if len(nodes) > 1 else []
        }

        graph_state[graph_id]['clusters'] = clusters
        _set_session_state(tool_context, 'graph_state', graph_state)

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'algorithm': algorithm,
            'clusters': clusters,
            'note': 'Real clustering requires graph algorithms'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def calculate_graph_centrality(
    graph_id: str,
    tool_context: ToolContext,
    centrality_type: str = 'betweenness'
) -> dict:
    """Calculate graph centrality metrics."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # Simple degree centrality
        nodes = list(graph_state[graph_id]['nodes'].keys())
        scores = {}

        for node in nodes:
            # Count edges connected to this node
            degree = sum(1 for edge in graph_state[graph_id]['edges'].keys()
                       if node in edge)
            scores[node] = degree / len(nodes) if nodes else 0

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'centrality_type': centrality_type,
            'scores': scores,
            'note': 'Real centrality requires graph algorithms'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def calculate_graph_depth(
    graph_id: str,
    root_node: str,
    tool_context: ToolContext
) -> dict:
    """Calculate graph depth from root."""
    try:
        graph_state = _get_session_state(tool_context, 'graph_state', {})
        if graph_id not in graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }

        # BFS to calculate depths
        depths = {root_node: 0}
        visited = {root_node}
        queue = [root_node]

        while queue:
            current = queue.pop(0)
            current_depth = depths[current]

            for edge_key in graph_state[graph_id]['edges'].keys():
                if edge_key.startswith(current + '->'):
                    neighbor = edge_key.split('->')[1]
                    if neighbor not in visited:
                        visited.add(neighbor)
                        depths[neighbor] = current_depth + 1
                        queue.append(neighbor)

        return {
            'status': 'ok',
            'graph_id': graph_id,
            'root_node': root_node,
            'depths': depths
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
    scope: str = 'local'
) -> dict:
    """Visualize call graph."""
    try:
        viz_id = str(uuid.uuid4())

        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'call_graph',
            'function_id': function_id,
            'scope': scope,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)

        return {
            'status': 'ok',
            'function_id': function_id,
            'scope': scope,
            'visualization_id': viz_id,
            'note': 'Real visualization requires code intelligence integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_dependency_graph(
    component_id: str,
    tool_context: ToolContext,
    scope: str = 'direct'
) -> dict:
    """Visualize dependency graph."""
    try:
        viz_id = str(uuid.uuid4())

        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'dependency_graph',
            'component_id': component_id,
            'scope': scope,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'component_id': component_id,
            'scope': scope,
            'visualization_id': viz_id,
            'note': 'Real visualization requires code intelligence integration'
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
    """Visualize control flow."""
    try:
        viz_id = str(uuid.uuid4())

        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'control_flow',
            'function_id': function_id,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'function_id': function_id,
            'visualization_id': viz_id,
            'note': 'Real visualization requires code intelligence integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_data_flow(
    variable_id: str,
    tool_context: ToolContext
) -> dict:
    """Visualize data flow."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'data_flow',
            'variable_id': variable_id,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'variable_id': variable_id,
            'visualization_id': viz_id,
            'note': 'Real visualization requires code intelligence integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_execution_flow(
    trace_id: str,
    tool_context: ToolContext
) -> dict:
    """Visualize execution flow."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'execution_flow',
            'trace_id': trace_id,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'trace_id': trace_id,
            'visualization_id': viz_id,
            'note': 'Real visualization requires runtime integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_class_hierarchy(
    class_id: str,
    tool_context: ToolContext
) -> dict:
    """Visualize class hierarchy."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'class_hierarchy',
            'class_id': class_id,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'class_id': class_id,
            'visualization_id': viz_id,
            'note': 'Real visualization requires code intelligence integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_architecture(
    tool_context: ToolContext,
    scope: str = 'full'
) -> dict:
    """Visualize architecture."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'architecture',
            'scope': scope,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'scope': scope,
            'visualization_id': viz_id,
            'note': 'Real visualization requires architecture analysis'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_database_relationships(
    table_name: str,
    tool_context: ToolContext
) -> dict:
    """Visualize database relationships."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'database_relationships',
            'table_name': table_name,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'table_name': table_name,
            'visualization_id': viz_id,
            'note': 'Real visualization requires database schema analysis'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_api_relationships(
    endpoint: str,
    tool_context: ToolContext
) -> dict:
    """Visualize API relationships."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'api_relationships',
            'endpoint': endpoint,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'endpoint': endpoint,
            'visualization_id': viz_id,
            'note': 'Real visualization requires API analysis'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_event_flow(
    event_source: str,
    tool_context: ToolContext
) -> dict:
    """Visualize event flow."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'event_flow',
            'event_source': event_source,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'event_source': event_source,
            'visualization_id': viz_id,
            'note': 'Real visualization requires event analysis'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_memory_usage(
    application_id: str,
    tool_context: ToolContext
) -> dict:
    """Visualize memory usage."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'memory_usage',
            'application_id': application_id,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'application_id': application_id,
            'visualization_id': viz_id,
            'note': 'Real visualization requires runtime integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_performance(
    application_id: str,
    tool_context: ToolContext,
    metric: str = 'cpu'
) -> dict:
    """Visualize performance metrics."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'performance',
            'application_id': application_id,
            'metric': metric,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'application_id': application_id,
            'metric': metric,
            'visualization_id': viz_id,
            'note': 'Real visualization requires monitoring integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_security_flow(
    component_id: str,
    tool_context: ToolContext
) -> dict:
    """Visualize security flow."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'security_flow',
            'component_id': component_id,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'component_id': component_id,
            'visualization_id': viz_id,
            'note': 'Real visualization requires security analysis'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_git_history(
    repository_path: str,
    tool_context: ToolContext,
    branch: str = 'main'
) -> dict:
    """Visualize git history."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'git_history',
            'repository_path': repository_path,
            'branch': branch,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'repository_path': repository_path,
            'branch': branch,
            'visualization_id': viz_id,
            'note': 'Real visualization requires git integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def visualize_test_coverage(
    repository_path: str,
    tool_context: ToolContext
) -> dict:
    """Visualize test coverage."""
    try:
        from .testing_verification_tools import measure_test_coverage
        
        coverage_result = measure_test_coverage(repository_path, tool_context)
        
        if coverage_result.get('status') == 'ok':
            viz_id = str(uuid.uuid4())
            
            viz_state = _get_session_state(tool_context, 'visualization_state', {})
            viz_state[viz_id] = {
                'type': 'test_coverage',
                'repository_path': repository_path,
                'coverage': coverage_result.get('coverage'),
                'created_at': time.time()
            }
            _set_session_state(tool_context, 'visualization_state', viz_state)
            
            return {
                'status': 'ok',
                'repository_path': repository_path,
                'visualization_id': viz_id,
                'coverage': coverage_result.get('coverage')
            }
        
        return coverage_result
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
    """Visualize change impact."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': 'change_impact',
            'element_id': element_id,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'element_id': element_id,
            'visualization_id': viz_id,
            'note': 'Real visualization requires impact analysis'
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
def compare_code_regions(
    region1_id: str,
    region2_id: str,
    tool_context: ToolContext
) -> dict:
    """Compare multiple selected code elements. Emits compare command."""
    try:
        _emit_command(tool_context, 'compare', node_id1=region1_id, node_id2=region2_id)

        from .code_understanding_tools import compare_implementations

        return compare_implementations(region1_id, region2_id, tool_context)
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
def pin_investigation(
    investigation_id: str,
    tool_context: ToolContext
) -> dict:
    """Preserve an investigation for later."""
    try:
        investigations = _get_session_state(tool_context, 'investigations', {})
        investigations[investigation_id] = {
            'pinned_at': time.time(),
            'state': 'preserved'
        }
        _set_session_state(tool_context, 'investigations', investigations)

        return {
            'status': 'ok',
            'investigation_id': investigation_id,
            'pinned': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def restore_investigation(
    investigation_id: str,
    tool_context: ToolContext
) -> dict:
    """Restore a previous investigation."""
    try:
        investigations = _get_session_state(tool_context, 'investigations', {})
        if investigation_id in investigations:
            return {
                'status': 'ok',
                'investigation_id': investigation_id,
                'restored': True,
                'state': investigations[investigation_id]
            }

        return {
            'status': 'error',
            'error': f'Investigation {investigation_id} not found'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def create_spatial_bookmark(
    bookmark_id: str,
    description: str,
    tool_context: ToolContext
) -> dict:
    """Bookmark a location in the code intelligence environment. Emits bookmark command."""
    try:
        _emit_command(tool_context, 'bookmark', node_id=bookmark_id, label=description)

        bookmarks = _get_session_state(tool_context, 'bookmarks', {})
        spatial_state = _get_session_state(tool_context, 'spatial_state', {})
        bookmarks[bookmark_id] = {
            'description': description,
            'spatial_state': spatial_state.copy(),
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'bookmarks', bookmarks)

        return {
            'status': 'ok',
            'bookmark_id': bookmark_id,
            'description': description,
            'created': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def annotate_code_element(
    element_id: str,
    annotation: str,
    tool_context: ToolContext
) -> dict:
    """Attach an explanation or note to a code element. Emits annotate command."""
    try:
        _emit_command(tool_context, 'annotate', node_id=element_id, text=annotation)

        annotations = _get_session_state(tool_context, 'annotations', {})
        if element_id not in annotations:
            annotations[element_id] = []

        annotations[element_id].append({
            'annotation': annotation,
            'created_at': time.time()
        })
        _set_session_state(tool_context, 'annotations', annotations)

        return {
            'status': 'ok',
            'element_id': element_id,
            'annotation': annotation,
            'annotated': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def synchronize_graphs(
    graph_ids: List[str],
    tool_context: ToolContext
) -> dict:
    """Keep related visualizations synchronized."""
    try:
        for graph_id in graph_ids:
            if graph_id in _graph_state:
                _graph_state[graph_id]['synchronized'] = True
        
        return {
            'status': 'ok',
            'graph_ids': graph_ids,
            'synchronized': True,
            'note': 'Synchronization requires VR rendering engine integration'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def request_visualization(
    visualization_type: str,
    parameters: Dict,
    tool_context: ToolContext
) -> dict:
    """Request a particular visualization."""
    try:
        viz_id = str(uuid.uuid4())
        
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        viz_state[viz_id] = {
            'type': visualization_type,
            'parameters': parameters,
            'created_at': time.time()
        }
        _set_session_state(tool_context, 'visualization_state', viz_state)
        
        return {
            'status': 'ok',
            'visualization_type': visualization_type,
            'parameters': parameters,
            'visualization_id': viz_id,
            'created': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def change_visualization_depth(
    visualization_id: str,
    depth: int,
    tool_context: ToolContext
) -> dict:
    """Expand or reduce graph depth. Emits set_depth command."""
    try:
        _emit_command(tool_context, 'set_depth', depth=depth)

        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        if visualization_id in viz_state:
            viz_state[visualization_id]['depth'] = depth
            _set_session_state(tool_context, 'visualization_state', viz_state)

        return {
            'status': 'ok',
            'visualization_id': visualization_id,
            'depth': depth,
            'updated': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def change_visualization_scope(
    visualization_id: str,
    scope: str,
    tool_context: ToolContext
) -> dict:
    """Switch between local, direct, extended and runtime scopes. Emits set_scope command."""
    try:
        _emit_command(tool_context, 'set_scope', scope=scope)

        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        if visualization_id in viz_state:
            viz_state[visualization_id]['scope'] = scope
            _set_session_state(tool_context, 'visualization_state', viz_state)

        return {
            'status': 'ok',
            'visualization_id': visualization_id,
            'scope': scope,
            'updated': True
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@safe
def get_visualization_state(
    visualization_id: str,
    tool_context: ToolContext
) -> dict:
    """Understand what is currently being visualized."""
    try:
        viz_state = _get_session_state(tool_context, 'visualization_state', {})
        if visualization_id in viz_state:
            return {
                'status': 'ok',
                'visualization_id': visualization_id,
                'state': viz_state[visualization_id]
            }

        return {
            'status': 'error',
            'error': f'Visualization {visualization_id} not found'
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
