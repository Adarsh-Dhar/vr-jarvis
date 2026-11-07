"""Path highlighting and query functionality for unified graphs."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from collections import deque


@dataclass
class PathQuery:
    """A query for paths in the graph."""
    start_node: str
    end_node: str
    max_depth: int
    edge_kinds: Optional[Set[str]] = None
    honor_call_return: bool = True


@dataclass
class PathResult:
    """Result of a path query."""
    paths: List[List[str]]  # List of node IDs representing paths
    shortest_path: Optional[List[str]]
    all_paths_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class PathQueryEngine:
    """
    Perform path queries over the unified graph.

    Provides:
    - Shortest path between two nodes
    - All paths between two nodes (with cap)
    - Path highlighting for VR
    - Call/return matching for context sensitivity
    """

    def __init__(self):
        self._graph_cache: Dict[str, Any] = {}

    def find_shortest_path(
        self,
        graph: Dict[str, Any],
        start: str,
        end: str,
        honor_call_return: bool = True
    ) -> Optional[List[str]]:
        """
        Find the shortest path between two nodes using BFS.

        Returns a list of node IDs, or None if no path exists.
        """
        if start not in graph.get('nodes', {}):
            return None
        if end not in graph.get('nodes', {}):
            return None

        # Build adjacency list
        adj = self._build_adjacency(graph, honor_call_return)

        # BFS to find shortest path
        queue = deque([[start]])
        visited = {start}
        parent = {start: None}

        while queue:
            path = queue.popleft()
            node = path[-1]

            if node == end:
                return path

            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = node
                    queue.append(path + [neighbor])

        return None

    def find_all_paths(
        self,
        graph: Dict[str, Any],
        start: str,
        end: str,
        max_paths: int = 100,
        max_depth: int = 20,
        honor_call_return: bool = True
    ) -> PathResult:
        """
        Find all paths between two nodes with depth cap.

        Returns a PathResult with paths and metadata.
        """
        if start not in graph.get('nodes', {}):
            return PathResult(paths=[], shortest_path=None, all_paths_count=0, metadata={})
        if end not in graph.get('nodes', {}):
            return PathResult(paths=[], shortest_path=None, all_paths_count=0, metadata={})

        # Build adjacency list
        adj = self._build_adjacency(graph, honor_call_return)

        # DFS to find all paths with depth cap
        paths = []
        self._dfs_all_paths(
            graph,
            adj,
            start,
            end,
            [start],
            set(),
            paths,
            max_depth,
            max_paths
        )

        # Find shortest path
        shortest = self.find_shortest_path(graph, start, end, honor_call_return)

        return PathResult(
            paths=paths,
            shortest_path=shortest,
            all_paths_count=len(paths),
            metadata={
                'max_depth': max_depth,
                'max_paths': max_paths
            }
        )

    def _dfs_all_paths(
        self,
        graph: Dict[str, Any],
        adj: Dict[str, Set[str]],
        current: str,
        end: str,
        path: List[str],
        visited: Set[str],
        paths: List[List[str]],
        max_depth: int,
        max_paths: int
    ):
        """DFS helper to find all paths."""
        if len(paths) >= max_paths:
            return

        if current == end:
            paths.append(path.copy())
            return

        if len(path) >= max_depth:
            return

        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                path.append(neighbor)
                self._dfs_all_paths(
                    graph,
                    adj,
                    neighbor,
                    end,
                    path,
                    visited,
                    paths,
                    max_depth,
                    max_paths
                )
                path.pop()
                visited.remove(neighbor)

    def _build_adjacency(
        self,
        graph: Dict[str, Any],
        honor_call_return: bool
    ) -> Dict[str, Set[str]]:
        """Build adjacency list from graph edges."""
        adj: Dict[str, Set[str]] = {}

        for edge in graph.get('edges', []):
            source = edge.get('source')
            target = edge.get('target')
            kind = edge.get('kind')

            if source not in adj:
                adj[source] = set()

            # Honor call/return matching if requested
            if honor_call_return:
                if kind == 'call':
                    # Only add call edge if there's a matching return edge
                    if self._has_matching_return(graph, edge):
                        adj[source].add(target)
                elif kind == 'return':
                    # Only add return edge if it matches a call
                    adj[source].add(target)
                else:
                    adj[source].add(target)
            else:
                adj[source].add(target)

        return adj

    def _has_matching_return(self, graph: Dict[str, Any], call_edge: Dict[str, Any]) -> bool:
        """Check if a call edge has a matching return edge."""
        call_site_id = call_edge.get('call_site_id')
        if not call_site_id:
            return True  # No call_site_id means no context to match

        for edge in graph.get('edges', []):
            if (edge.get('kind') == 'return' and
                edge.get('call_site_id') == call_site_id):
                return True

        return False

    def highlight_path(
        self,
        graph: Dict[str, Any],
        path: List[str]
    ) -> Dict[str, Any]:
        """
        Generate highlight data for a path.

        Returns node and edge highlighting information for VR.
        """
        highlighted_nodes = set(path)
        highlighted_edges = []

        # Find edges between consecutive nodes in path
        for i in range(len(path) - 1):
            source = path[i]
            target = path[i + 1]

            for edge in graph.get('edges', []):
                if edge.get('source') == source and edge.get('target') == target:
                    highlighted_edges.append(edge.get('id'))

        return {
            'highlighted_nodes': list(highlighted_nodes),
            'highlighted_edges': highlighted_edges,
            'path_length': len(path)
        }
