"""
Agent 12 - Visualization & Spatial Intelligence Tools
Makes the whole system feel like JARVIS inside VR.
"""

from typing import Optional, List, Dict, Any
import uuid
import time
from google.adk.tools import ToolContext
from ._safe import safe

# In-memory graph and visualization state
_graph_state = {}
_visualization_state = {}
_spatial_state = {}
_bookmarks = {}
_annotations = {}
_investigations = {}


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
        
        _graph_state[graph_id] = {
            'type': graph_type,
            'nodes': {},
            'edges': {},
            'created_at': time.time()
        }
        
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        _graph_state[graph_id]['nodes'][node_id] = node_data
        
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        if node_id in _graph_state[graph_id]['nodes']:
            del _graph_state[graph_id]['nodes'][node_id]
            # Remove associated edges
            edges_to_remove = [k for k in _graph_state[graph_id]['edges'].keys() 
                             if node_id in k]
            for edge in edges_to_remove:
                del _graph_state[graph_id]['edges'][edge]
        
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        edge_key = f"{source_id}->{target_id}"
        _graph_state[graph_id]['edges'][edge_key] = edge_data
        
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        edge_key = f"{source_id}->{target_id}"
        if edge_key in _graph_state[graph_id]['edges']:
            del _graph_state[graph_id]['edges'][edge_key]
        
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
    """Expand a node to show its connections."""
    try:
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        # In a real implementation, this would query code intelligence to find related nodes
        # For now, return the current state
        node_count = len(_graph_state[graph_id]['nodes'])
        edge_count = len(_graph_state[graph_id]['edges'])
        
        return {
            'status': 'ok',
            'graph_id': graph_id,
            'node_id': node_id,
            'depth': depth,
            'expanded': True,
            'total_nodes': node_count,
            'total_edges': edge_count,
            'note': 'Real expansion requires code intelligence integration'
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
    """Collapse a node to hide its connections."""
    try:
        if graph_id not in _graph_state:
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
    """Filter graph by criteria."""
    try:
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        # Apply filters to nodes
        visible_nodes = []
        for node_id, node_data in _graph_state[graph_id]['nodes'].items():
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        matches = []
        query_lower = query.lower()
        
        for node_id, node_data in _graph_state[graph_id]['nodes'].items():
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        # Store highlight state
        _graph_state[graph_id]['highlighted_path'] = path
        
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        # Find connected nodes
        connected_nodes = set()
        for edge_key in _graph_state[graph_id]['edges'].keys():
            if node_id in edge_key:
                parts = edge_key.split('->')
                connected_nodes.update(parts)
        
        _graph_state[graph_id]['highlighted_nodes'] = list(connected_nodes)
        
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        _graph_state[graph_id]['visible_nodes'] = node_ids
        
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
        if graph1_id not in _graph_state or graph2_id not in _graph_state:
            return {
                'status': 'error',
                'error': 'One or both graphs not found'
            }
        
        graph1 = _graph_state[graph1_id]
        graph2 = _graph_state[graph2_id]
        
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        # Simple circular layout for demo
        nodes = list(_graph_state[graph_id]['nodes'].keys())
        positions = {}
        
        import math
        for i, node in enumerate(nodes):
            angle = 2 * math.pi * i / len(nodes)
            radius = 200
            positions[node] = {
                'x': radius * math.cos(angle),
                'y': radius * math.sin(angle)
            }
        
        _graph_state[graph_id]['positions'] = positions
        
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        # Simple clustering by connected components
        nodes = list(_graph_state[graph_id]['nodes'].keys())
        clusters = {
            'cluster1': nodes[:len(nodes)//2],
            'cluster2': nodes[len(nodes)//2:] if len(nodes) > 1 else []
        }
        
        _graph_state[graph_id]['clusters'] = clusters
        
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        # Simple degree centrality
        nodes = list(_graph_state[graph_id]['nodes'].keys())
        scores = {}
        
        for node in nodes:
            # Count edges connected to this node
            degree = sum(1 for edge in _graph_state[graph_id]['edges'].keys() 
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
        if graph_id not in _graph_state:
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
            
            for edge_key in _graph_state[graph_id]['edges'].keys():
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
        if graph_id not in _graph_state:
            return {
                'status': 'error',
                'error': f'Graph {graph_id} not found'
            }
        
        graph = _graph_state[graph_id]
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
        
        _visualization_state[viz_id] = {
            'type': 'call_graph',
            'function_id': function_id,
            'scope': scope,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'dependency_graph',
            'component_id': component_id,
            'scope': scope,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'control_flow',
            'function_id': function_id,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'data_flow',
            'variable_id': variable_id,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'execution_flow',
            'trace_id': trace_id,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'class_hierarchy',
            'class_id': class_id,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'architecture',
            'scope': scope,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'database_relationships',
            'table_name': table_name,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'api_relationships',
            'endpoint': endpoint,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'event_flow',
            'event_source': event_source,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'memory_usage',
            'application_id': application_id,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'performance',
            'application_id': application_id,
            'metric': metric,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'security_flow',
            'component_id': component_id,
            'created_at': time.time()
        }
        
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
        
        _visualization_state[viz_id] = {
            'type': 'git_history',
            'repository_path': repository_path,
            'branch': branch,
            'created_at': time.time()
        }
        
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
            
            _visualization_state[viz_id] = {
                'type': 'test_coverage',
                'repository_path': repository_path,
                'coverage': coverage_result.get('coverage'),
                'created_at': time.time()
            }
            
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
        
        _visualization_state[viz_id] = {
            'type': 'change_impact',
            'element_id': element_id,
            'created_at': time.time()
        }
        
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
        return {
            'status': 'ok',
            'selection': _spatial_state.get('current_selection', {
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
        selection = _spatial_state.get('current_selection', {})
        node_id = selection.get('id')
        
        if node_id and node_id in _graph_state:
            graph = _graph_state[node_id]
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
    """Select a function, class, file or other code element."""
    try:
        _spatial_state['current_selection'] = {
            'type': 'code_element',
            'id': element_id
        }
        
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
        _spatial_state['focused_object'] = object_id
        
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
        _spatial_state['isolated_path'] = path
        
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
    """Compare multiple selected code elements."""
    try:
        from .code_understanding_tools import compare_implementations
        
        return compare_implementations(region1_id, region2_id, tool_context)
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
        _investigations[investigation_id] = {
            'pinned_at': time.time(),
            'state': 'preserved'
        }
        
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
        if investigation_id in _investigations:
            return {
                'status': 'ok',
                'investigation_id': investigation_id,
                'restored': True,
                'state': _investigations[investigation_id]
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
    """Bookmark a location in the code intelligence environment."""
    try:
        _bookmarks[bookmark_id] = {
            'description': description,
            'spatial_state': _spatial_state.copy(),
            'created_at': time.time()
        }
        
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
    """Attach an explanation or note to a code element."""
    try:
        if element_id not in _annotations:
            _annotations[element_id] = []
        
        _annotations[element_id].append({
            'annotation': annotation,
            'created_at': time.time()
        })
        
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
        
        _visualization_state[viz_id] = {
            'type': visualization_type,
            'parameters': parameters,
            'created_at': time.time()
        }
        
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
    """Expand or reduce graph depth."""
    try:
        if visualization_id in _visualization_state:
            _visualization_state[visualization_id]['depth'] = depth
        
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
    """Switch between local, direct, extended and runtime scopes."""
    try:
        if visualization_id in _visualization_state:
            _visualization_state[visualization_id]['scope'] = scope
        
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
        if visualization_id in _visualization_state:
            return {
                'status': 'ok',
                'visualization_id': visualization_id,
                'state': _visualization_state[visualization_id]
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
        # Try to find object in graph state
        for graph_id, graph in _graph_state.items():
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
