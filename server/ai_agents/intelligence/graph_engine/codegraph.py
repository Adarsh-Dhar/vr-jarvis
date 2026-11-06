"""Central graph access layer with caching and standardized traversal."""
import json
import os
from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict, Any

from ... import config


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
        
        # Check schema version
        schema_version = self._raw_data.get('meta', {}).get('schema_version', 1)
        if schema_version == 1:
            # Schema v1 needs re-indexing
            raise ValueError("Graph schema version 1 is deprecated. Please re-index the repository to upgrade to schema version 3.")
        self.schema_version = schema_version

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

        # Load tests and call sites (schema v3)
        self._tests = self._raw_data.get('tests', [])
        self._call_sites = {c['id']: c for c in self._raw_data.get('call_sites', [])
                            if isinstance(c, dict) and c.get('id')}
        # index call-site edges by callsite_id for candidate lookup
        self._edges_by_callsite = {}
        for edge in self._raw_data.get('edges', []):
            csid = edge.get('callsite_id')
            if csid:
                self._edges_by_callsite.setdefault(csid, []).append(edge)

    # -- reference resolution -------------------------------------------------
    def resolve(self, ref: str) -> Dict[str, Any]:
        """Resolve a reference strictly.

        Returns {'status': 'ok'|'ambiguous'|'not_found', 'node': ..., 'candidates': [...]}.
        Ambiguous name/suffix matches are reported, never silently first-picked.
        """
        # Exact id match
        if ref in self._nodes:
            return {'status': 'ok', 'node': self._nodes[ref], 'candidates': [self._nodes[ref]]}

        # Legacy ID match (old dotted format)
        legacy = [n for n in self._nodes.values() if n.get('legacy_id') == ref]
        if len(legacy) == 1:
            return {'status': 'ok', 'node': legacy[0], 'candidates': legacy}
        if len(legacy) > 1:
            return {'status': 'ambiguous', 'node': None, 'candidates': legacy}

        # Dotted suffix match (e.g., 'make_dataset' matches 'eutro.data.make_dataset')
        suffix_matches = [n for n in self._nodes.values() if n['id'].endswith('::' + ref)]
        if len(suffix_matches) == 1:
            return {'status': 'ok', 'node': suffix_matches[0], 'candidates': suffix_matches}
        if len(suffix_matches) > 1:
            return {'status': 'ambiguous', 'node': None, 'candidates': suffix_matches}

        # Unique name match
        name_matches = [n for n in self._nodes.values() if n['name'] == ref]
        if len(name_matches) == 1:
            return {'status': 'ok', 'node': name_matches[0], 'candidates': name_matches}
        if len(name_matches) > 1:
            return {'status': 'ambiguous', 'node': None, 'candidates': name_matches}

        # File path match
        file_matches = [n for n in self._nodes.values() if n.get('file', '') == ref]
        if len(file_matches) == 1:
            return {'status': 'ok', 'node': file_matches[0], 'candidates': file_matches}
        if len(file_matches) > 1:
            return {'status': 'ambiguous', 'node': None, 'candidates': file_matches}

        return {'status': 'not_found', 'node': None, 'candidates': []}

    def get(self, ref: str) -> Optional[Dict[str, Any]]:
        """Resolve a reference to a node; returns None when ambiguous or unknown."""
        return self.resolve(ref)['node']

    # -- edge filtering helpers ----------------------------------------------
    @staticmethod
    def _edge_confidence(edge: Dict[str, Any]) -> Optional[float]:
        conf = edge.get('confidence')
        if conf is None:
            # legacy edges: infer from kind
            kind = edge.get('kind', '')
            conf = {'confirmed': 1.0, 'likely': 0.7, 'inferred': 0.5,
                    'possible': 0.7, 'ambiguous': 0.4}.get(kind)
        return conf

    def _call_edge_visible(self, edge: Dict[str, Any], include_possible: bool,
                           include_ambiguous: bool, min_confidence: Optional[float]) -> bool:
        """Decide whether an edge participates in callers/callees traversal."""
        etype = edge.get('type')
        if etype == 'calls':
            pass  # confirmed call edge
        elif etype == 'may_call':
            kind = edge.get('kind', '')
            res = edge.get('resolution', '')
            if kind == 'possible' or res == 'polymorphic':
                if not include_possible:
                    return False
            elif kind == 'ambiguous' or res == 'ambiguous':
                if not include_ambiguous:
                    return False
            else:
                if not (include_possible or include_ambiguous):
                    return False
        else:
            return False
        if min_confidence is not None:
            conf = self._edge_confidence(edge)
            if conf is None or conf < min_confidence:
                return False
        return True

    def callers(self, node_id: str, depth: int = 1, include_candidates: bool = False,
                include_possible: bool = False, include_ambiguous: bool = False,
                min_confidence: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Get callers of a node following call edges.

        By default only confirmed ``calls`` edges are returned. Pass
        ``include_possible``/``include_ambiguous`` (or the legacy
        ``include_candidates``) to also traverse ``may_call`` edges.
        Returns list of {from, file, line, kind, resolution, callsite_id,
        confidence, evidence} for each caller.
        """
        include_possible = include_possible or include_candidates
        result = []
        visited = set()
        queue = deque([(node_id, 0)])

        while queue:
            current, current_depth = queue.popleft()
            if current_depth > depth or current in visited:
                continue
            visited.add(current)

            for edge in self._inn.get(current, []):
                if not self._call_edge_visible(edge, include_possible, include_ambiguous,
                                               min_confidence):
                    continue
                caller = edge['src']
                caller_depth = current_depth + 1

                if caller_depth <= depth:
                    entry = {
                        'from': caller,
                        'file': edge.get('file'),
                        'line': edge.get('line'),
                        'column': edge.get('column'),
                        'kind': edge.get('kind', 'unresolved'),
                        'resolution': edge.get('resolution', 'unresolved'),
                        'callsite_id': edge.get('callsite_id'),
                        'confidence': self._edge_confidence(edge),
                        'evidence': edge.get('evidence'),
                    }
                    if caller_depth > 1:
                        entry['depth'] = caller_depth
                    result.append(entry)
                    queue.append((caller, caller_depth))

        return result

    def callees(self, node_id: str, depth: int = 1, include_possible: bool = False,
                include_ambiguous: bool = False,
                min_confidence: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Get callees of a node following call edges.

        By default only confirmed ``calls`` edges are returned. Each entry
        carries callsite_id, line, resolution, confidence and evidence.
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
                if not self._call_edge_visible(edge, include_possible, include_ambiguous,
                                               min_confidence):
                    continue
                callee = edge['dst']
                entry = {
                    'to': callee,
                    'file': edge.get('file'),
                    'line': edge.get('line'),
                    'column': edge.get('column'),
                    'kind': edge.get('kind', 'unresolved'),
                    'resolution': edge.get('resolution', 'unresolved'),
                    'callsite_id': edge.get('callsite_id'),
                    'confidence': self._edge_confidence(edge),
                    'evidence': edge.get('evidence'),
                }
                if d > 0:
                    entry['depth'] = d
                result.append(entry)
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
    
    def neighborhood(self, node_id: str, depth: int = 2, direction: str = 'both', 
                    include_unresolved: bool = False, hide_external: bool = False, 
                    max_nodes: int = 1000) -> Dict[str, Any]:
        """
        Get the neighborhood of a node with configurable options.
        Returns {nodes, edges, truncated}.
        """
        visited = set()
        nodes = {}
        edges = []
        queue = deque([(node_id, 0)])
        node_ids_to_include = set([node_id])
        
        while queue and len(node_ids_to_include) < max_nodes:
            current, d = queue.popleft()
            if current in visited or d > depth:
                continue
            visited.add(current)
            
            # Add node if not already added
            if current in self._nodes:
                nodes[current] = self._nodes[current]
                node_ids_to_include.add(current)
            
            # Determine which edges to follow based on direction
            follow_possible = include_unresolved  # uncertain edges only on request
            if direction in ['both', 'out']:
                for edge in self._out.get(current, []):
                    etype = edge.get('type')
                    if etype == 'calls':
                        pass
                    elif etype == 'may_call' and follow_possible:
                        pass
                    else:
                        continue
                    # Skip unresolved edges if include_unresolved is False
                    if not include_unresolved and edge.get('resolution') == 'unresolved':
                        continue
                    # Skip external edges if hide_external is True
                    if hide_external and edge.get('resolution') == 'external':
                        continue
                    queue.append((edge['dst'], d + 1))
                    if edge['dst'] in self._nodes:
                        nodes[edge['dst']] = self._nodes[edge['dst']]
                        node_ids_to_include.add(edge['dst'])
                    edges.append(edge)

            if direction in ['both', 'in']:
                for edge in self._inn.get(current, []):
                    etype = edge.get('type')
                    if etype == 'calls':
                        pass
                    elif etype == 'may_call' and follow_possible:
                        pass
                    else:
                        continue
                    if not include_unresolved and edge.get('resolution') == 'unresolved':
                        continue
                    if hide_external and edge.get('resolution') == 'external':
                        continue
                    queue.append((edge['src'], d + 1))
                    if edge['src'] in self._nodes:
                        nodes[edge['src']] = self._nodes[edge['src']]
                        node_ids_to_include.add(edge['src'])
                    edges.append(edge)
        
        truncated = len(node_ids_to_include) >= max_nodes
        
        return {
            'nodes': list(nodes.values()),
            'edges': edges,
            'truncated': truncated
        }
    
    def candidates(self, callsite_id: str) -> List[Dict[str, Any]]:
        """
        Get candidate targets for a call site.

        Looks up ``may_call`` edges carrying this ``callsite_id`` (schema v3),
        falling back to the legacy layout where may_call edges hang off a
        call-site node id. Returns candidate node dicts annotated with the
        edge metadata (resolution, kind, reason, confidence).
        """
        result = []
        seen = set()
        edge_groups = [self._edges_by_callsite.get(callsite_id, [])]
        # legacy fallback: callsite_id is itself a node with outgoing may_call edges
        if callsite_id in self._nodes:
            edge_groups.append([e for e in self._out.get(callsite_id, [])
                                if e.get('type') == 'may_call'])
        for edges in edge_groups:
            for edge in edges:
                if edge.get('type') != 'may_call':
                    continue
                candidate_id = edge['dst']
                if candidate_id in seen:
                    continue
                seen.add(candidate_id)
                node = self._nodes.get(candidate_id)
                if node:
                    entry = dict(node)
                    entry['edge'] = {
                        'resolution': edge.get('resolution'),
                        'kind': edge.get('kind'),
                        'reason': edge.get('reason'),
                        'confidence': self._edge_confidence(edge),
                        'callsite_id': edge.get('callsite_id'),
                    }
                    result.append(entry)
        return result

    def call_site(self, callsite_id: str) -> Optional[Dict[str, Any]]:
        """Return the recorded call-site dict (schema v3) if present."""
        return self._call_sites.get(callsite_id)
    
    def edges_between(self, src: str, dst: str) -> List[Dict[str, Any]]:
        """
        Get all edges between two nodes (handles parallel call sites).
        Returns list of edges with aggregation info.
        """
        result = []
        for edge in self._out.get(src, []):
            if edge['dst'] == dst:
                result.append(edge)
        
        # Add aggregation info
        for edge in result:
            # Count parallel edges at the same line
            parallel_count = sum(1 for e in result if e.get('line') == edge.get('line'))
            edge['parallel_count'] = parallel_count
        
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
