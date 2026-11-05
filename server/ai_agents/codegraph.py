"""Central graph access layer with caching and standardized traversal."""
import json
import os
from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict, Any

from . import config


class CodeGraph:
    """Single source of truth for graph data with cached loading and standardized traversal."""

    def __init__(self, graph_path: Path):
        self.graph_path = graph_path
        self._raw_data = None
        self._nodes = {}
        self._out = {}
        self._inn = {}
        self._tests = []
        self._load()

    def _load(self):
        """Load and index the graph from disk."""
        if not self.graph_path.exists():
            raise FileNotFoundError(f"Graph file not found: {self.graph_path}")

        with open(self.graph_path) as f:
            self._raw_data = json.load(f)

        # Index nodes by id
        self._nodes = {n['id']: n for n in self._raw_data.get('nodes', [])}

        # Index edges by source and destination
        self._out = {}
        self._inn = {}
        for edge in self._raw_data.get('edges', []):
            src, dst = edge['src'], edge['dst']
            if src not in self._out:
                self._out[src] = []
            if dst not in self._inn:
                self._inn[dst] = []
            self._out[src].append(edge)
            self._inn[dst].append(edge)

        # Load tests
        self._tests = self._raw_data.get('tests', [])

    def get(self, ref: str) -> Optional[Dict[str, Any]]:
        """
        Resolve a reference to a node.
        Priority: exact id match, dotted suffix match, unique name match, then file path match.
        """
        # Exact id match
        if ref in self._nodes:
            return self._nodes[ref]

        # Dotted suffix match (e.g., 'make_dataset' matches 'eutro.data.make_dataset')
        suffix_matches = [n for n in self._nodes.values() if n['id'].endswith('.' + ref)]
        if len(suffix_matches) == 1:
            return suffix_matches[0]
        if len(suffix_matches) > 1:
            # If multiple suffix matches, prefer the one with the shortest id (most specific)
            return min(suffix_matches, key=lambda n: len(n['id']))

        # Unique name match
        name_matches = [n for n in self._nodes.values() if n['name'] == ref]
        if len(name_matches) == 1:
            return name_matches[0]

        # File path match
        file_matches = [n for n in self._nodes.values() if n.get('file', '') == ref]
        if len(file_matches) == 1:
            return file_matches[0]

        return None

    def callers(self, node_id: str, depth: int = 1) -> List[Dict[str, Any]]:
        """
        Get callers of a node following only 'calls' edges.
        Returns list of {from, file, line, kind} for each caller.
        Depth is hop count: 1 = direct callers, 2 = callers of callers, etc.
        """
        result = []
        visited = set()
        queue = deque([(node_id, 0)])

        while queue:
            current, current_depth = queue.popleft()
            if current_depth > depth or current in visited:
                continue
            visited.add(current)

            for edge in self._inn.get(current, []):
                if edge['type'] != 'calls':
                    continue
                caller = edge['src']
                caller_depth = current_depth + 1
                
                if caller_depth <= depth:
                    if caller_depth == 1:
                        # Direct caller (1 hop from target)
                        result.append({
                            'from': caller,
                            'file': edge.get('file'),
                            'line': edge.get('line'),
                            'kind': edge.get('kind', 'unresolved')
                        })
                    else:
                        # Indirect caller (more than 1 hop)
                        result.append({
                            'from': caller,
                            'file': edge.get('file'),
                            'line': edge.get('line'),
                            'kind': edge.get('kind', 'unresolved'),
                            'depth': caller_depth
                        })
                    queue.append((caller, caller_depth))

        return result

    def callees(self, node_id: str, depth: int = 1) -> List[Dict[str, Any]]:
        """
        Get callees of a node following only 'calls' edges.
        Returns list of {to, file, line, kind} for each callee.
        """
        result = []
        visited = set()
        queue = deque([(node_id, 0)])

        while queue:
            current, d = queue.popleft()
            if d > depth or current in visited:
                continue
            visited.add(current)

            for edge in self._out.get(current, []):
                if edge['type'] != 'calls':
                    continue
                callee = edge['dst']
                if d == 0:
                    # Direct callee
                    result.append({
                        'to': callee,
                        'file': edge.get('file'),
                        'line': edge.get('line'),
                        'kind': edge.get('kind', 'unresolved')
                    })
                else:
                    # Indirect callee
                    result.append({
                        'to': callee,
                        'file': edge.get('file'),
                        'line': edge.get('line'),
                        'kind': edge.get('kind', 'unresolved'),
                        'depth': d
                    })
                queue.append((callee, d + 1))

        return result

    def children(self, node_id: str) -> List[Dict[str, Any]]:
        """
        Get children of a node following only 'contains' edges.
        Returns list of child node dicts.
        """
        result = []
        for edge in self._out.get(node_id, []):
            if edge['type'] == 'contains':
                child_id = edge['dst']
                if child_id in self._nodes:
                    result.append(self._nodes[child_id])
        return result

    def deps(self, node_id: str) -> List[Dict[str, Any]]:
        """
        Get dependencies of a node following only 'imports' edges.
        Returns list of {to, file, kind} for each dependency.
        """
        result = []
        for edge in self._out.get(node_id, []):
            if edge['type'] == 'imports':
                dep_id = edge['dst']
                result.append({
                    'to': dep_id,
                    'file': edge.get('file'),
                    'kind': edge.get('kind', 'confirmed')
                })
        return result

    def subgraph(self, ids: List[str], include_edges: bool = True) -> Dict[str, Any]:
        """
        Extract a subgraph containing the specified nodes and their edges.
        Returns {nodes, edges} in Unity DTO shape.
        """
        nodes = []
        edges = []

        for node_id in ids:
            if node_id in self._nodes:
                nodes.append(self._nodes[node_id])

        if include_edges:
            edge_set = set()
            for node_id in ids:
                # Outgoing edges
                for edge in self._out.get(node_id, []):
                    if edge['dst'] in ids:
                        edge_key = (edge['src'], edge['dst'])
                        if edge_key not in edge_set:
                            edge_set.add(edge_key)
                            edges.append(edge)
                # Incoming edges
                for edge in self._inn.get(node_id, []):
                    if edge['src'] in ids:
                        edge_key = (edge['src'], edge['dst'])
                        if edge_key not in edge_set:
                            edge_set.add(edge_key)
                            edges.append(edge)

        return {'nodes': nodes, 'edges': edges}

    def covering_tests(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get tests that cover the specified nodes.
        Returns list of {id, file, covers} for each covering test.
        """
        id_set = set(ids)
        result = []
        for test in self._tests:
            test_covers = set(test.get('covers', []))
            if test_covers & id_set:
                result.append(test)
        return result


@lru_cache(maxsize=1)
def get_graph(graph_path_str: str, mtime: float) -> CodeGraph:
    """
    Get a cached CodeGraph instance for the given graph path.
    Cache is keyed by both path and mtime to auto-invalidate on file changes.
    """
    return CodeGraph(Path(graph_path_str))


def load_current_graph() -> CodeGraph:
    """Load the graph for the currently active repository."""
    if not config.GRAPH_PATH.exists():
        raise FileNotFoundError(f"Graph file not found: {config.GRAPH_PATH}")
    mtime = config.GRAPH_PATH.stat().st_mtime
    return get_graph(str(config.GRAPH_PATH), mtime)


def clear_cache():
    """Clear the graph cache (call when repository is reactivated)."""
    get_graph.cache_clear()
