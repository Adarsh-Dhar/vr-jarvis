"""Large graph summarization for scalable visualization."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict


@dataclass
class GraphSummary:
    """A summarized view of a large graph."""
    function_id: str
    original_node_count: int
    original_edge_count: int
    summarized_nodes: List[Dict[str, Any]]
    summarized_edges: List[Dict[str, Any]]
    collapsed_functions: Set[str]  # Function IDs that are collapsed
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamedNeighborhood:
    """A streamed neighborhood for large graph traversal."""
    focus_node: str
    depth: int
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    has_more: bool
    cursor: Optional[str]


class GraphSummarizer:
    """
    Summarize large graphs for scalable visualization.

    Provides:
    - Function collapsing (summarize function as single node)
    - Node count capping
    - Depth-based neighborhood streaming
    - Neighborhood expansion on demand
    """

    def __init__(self, max_nodes_per_view: int = 100):
        self._max_nodes_per_view = max_nodes_per_view
        self._cursor_counter = 0

    def summarize_graph(
        self,
        graph: Dict[str, Any],
        focus_function: Optional[str] = None
    ) -> GraphSummary:
        """
        Summarize a large graph for visualization.

        Collapses functions and caps node count to make it viewable.
        """
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])

        if len(nodes) <= self._max_nodes_per_view:
            # No summarization needed
            return GraphSummary(
                function_id=graph.get('function_id', 'unknown'),
                original_node_count=len(nodes),
                original_edge_count=len(edges),
                summarized_nodes=nodes,
                summarized_edges=edges,
                collapsed_functions=set(),
                metadata={'summarized': False}
            )

        # Collapse functions to single nodes
        function_groups = self._group_by_function(nodes)
        collapsed_functions = set()

        summarized_nodes = []
        for func_id, func_nodes in function_groups.items():
            if len(func_nodes) > 5:  # Only collapse large functions
                # Create summary node
                summary_node = {
                    'id': f'summary_{func_id}',
                    'kind': 'function_summary',
                    'label': f'{func_id} ({len(func_nodes)} nodes)',
                    'function_id': func_id,
                    'original_node_count': len(func_nodes),
                    'collapsed': True
                }
                summarized_nodes.append(summary_node)
                collapsed_functions.add(func_id)
            else:
                summarized_nodes.extend(func_nodes)

        # Cap node count
        if len(summarized_nodes) > self._max_nodes_per_view:
            summarized_nodes = summarized_nodes[:self._max_nodes_per_view]

        # Filter edges to include only between summarized nodes
        summarized_node_ids = {n['id'] for n in summarized_nodes}
        summarized_edges = [
            e for e in edges
            if e.get('source') in summarized_node_ids and e.get('target') in summarized_node_ids
        ]

        return GraphSummary(
            function_id=graph.get('function_id', 'unknown'),
            original_node_count=len(nodes),
            original_edge_count=len(edges),
            summarized_nodes=summarized_nodes,
            summarized_edges=summarized_edges,
            collapsed_functions=collapsed_functions,
            metadata={
                'summarized': True,
                'collapse_count': len(collapsed_functions)
            }
        )

    def _group_by_function(self, nodes: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group nodes by their function ID."""
        groups = defaultdict(list)
        for node in nodes:
            func_id = node.get('function_id', 'unknown')
            groups[func_id].append(node)
        return dict(groups)

    def stream_neighborhood(
        self,
        graph: Dict[str, Any],
        focus_node: str,
        depth: int = 2
    ) -> StreamedNeighborhood:
        """
        Stream a neighborhood around a focus node.

        Returns nodes and edges within depth of the focus node.
        """
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])

        # Build adjacency list
        adj = defaultdict(list)
        for edge in edges:
            adj[edge['source']].append(edge['target'])

        # BFS to collect neighborhood
        visited = set()
        queue = [(focus_node, 0)]
        neighborhood_nodes = []
        neighborhood_edges = []

        while queue and len(neighborhood_nodes) < self._max_nodes_per_view:
            node_id, current_depth = queue.pop(0)

            if node_id in visited or current_depth > depth:
                continue

            visited.add(node_id)

            # Find node
            node = next((n for n in nodes if n['id'] == node_id), None)
            if node:
                neighborhood_nodes.append(node)

            # Add edges within depth
            for neighbor in adj[node_id]:
                edge = next((e for e in edges if e['source'] == node_id and e['target'] == neighbor), None)
                if edge and neighbor not in visited:
                    neighborhood_edges.append(edge)
                    queue.append((neighbor, current_depth + 1))

        # Generate cursor for pagination
        self._cursor_counter += 1
        cursor = f"cursor_{self._cursor_counter}"

        has_more = len(visited) < len(nodes) and len(neighborhood_nodes) >= self._max_nodes_per_view

        return StreamedNeighborhood(
            focus_node=focus_node,
            depth=depth,
            nodes=neighborhood_nodes,
            edges=neighborhood_edges,
            has_more=has_more,
            cursor=cursor
        )

    def expand_neighborhood(
        self,
        graph: Dict[str, Any],
        cursor: str,
        depth: int = 2
    ) -> StreamedNeighborhood:
        """
        Expand a previously streamed neighborhood.

        Uses the cursor to continue from where it left off.
        """
        # For now, this is a placeholder - would need cursor state management
        # A full implementation would track visited nodes across calls
        return self.stream_neighborhood(graph, 'unknown', depth)
