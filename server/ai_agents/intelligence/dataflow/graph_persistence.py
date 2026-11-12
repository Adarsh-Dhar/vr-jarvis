"""Persistence and incremental invalidation for graph data."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
import hashlib
import json
from pathlib import Path


@dataclass
class GraphCacheEntry:
    """A cached graph entry with hash-based invalidation."""
    function_id: str
    content_hash: str
    cfg_hash: str
    dfg_hash: str
    callee_hashes: Dict[str, str]
    # Digests of callee summaries this entry was computed against
    # ({callee_id: digest}); an entry is valid only while every one still
    # matches, so a change inside any transitive callee invalidates it.
    dependency_digests: Dict[str, str] = field(default_factory=dict)
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class GraphPersistenceManager:
    """
    Manage persistence and incremental invalidation of graph data.

    Provides:
    - Cache keyed by content hash
    - Incremental invalidation on function change
    - Callee summary change propagation
    - Disk-based persistence
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self._cache_dir = cache_dir or Path('.devin/graph_cache')
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, GraphCacheEntry] = {}

    def compute_content_hash(self, source: str) -> str:
        """Compute a hash of function source code."""
        return hashlib.md5(source.encode()).hexdigest()

    def compute_cfg_hash(self, cfg: Dict[str, Any]) -> str:
        """Compute a hash of the CFG structure."""
        # Simplified - hash the node/edge count and structure
        data = f"{len(cfg.get('nodes', []))}:{len(cfg.get('edges', []))}"
        return hashlib.md5(data.encode()).hexdigest()

    def compute_dfg_hash(self, dfg: Dict[str, Any]) -> str:
        """Compute a hash of the DFG structure."""
        data = f"{len(dfg.get('nodes', []))}:{len(dfg.get('edges', []))}"
        return hashlib.md5(data.encode()).hexdigest()

    def cache_graph(
        self,
        function_id: str,
        source: str,
        cfg: Dict[str, Any],
        dfg: Dict[str, Any],
        callee_hashes: Dict[str, str],
        dependency_digests: Optional[Dict[str, str]] = None,
        import_hashes: Optional[Dict[str, str]] = None
    ) -> GraphCacheEntry:
        """Cache a graph with its hashes.

        ``dependency_digests`` maps callee function ids to the summary
        digests they had when this entry was computed. ``import_hashes``
        maps imported file paths to their sha256 for module-level edges.
        """
        content_hash = self.compute_content_hash(source)
        cfg_hash = self.compute_cfg_hash(cfg)
        dfg_hash = self.compute_dfg_hash(dfg)

        metadata = {}
        if import_hashes:
            metadata['import_hashes'] = dict(import_hashes)

        entry = GraphCacheEntry(
            function_id=function_id,
            content_hash=content_hash,
            cfg_hash=cfg_hash,
            dfg_hash=dfg_hash,
            callee_hashes=callee_hashes,
            dependency_digests=dict(dependency_digests or {}),
            timestamp=__import__('time').time(),
            metadata=metadata
        )

        self._cache[function_id] = entry
        self._persist_entry(entry)

        return entry

    def invalidate_function(self, function_id: str):
        """Invalidate a function's cache entry."""
        if function_id in self._cache:
            del self._cache[function_id]
            self._remove_persisted_entry(function_id)

    def get_cached_graph(self, function_id: str) -> Optional[GraphCacheEntry]:
        """Get a cached graph entry."""
        return self._cache.get(function_id)

    def is_cache_valid(
        self,
        function_id: str,
        source: str,
        cfg: Dict[str, Any],
        dfg: Dict[str, Any],
        callee_hashes: Dict[str, str],
        dependency_digests: Optional[Dict[str, str]] = None,
        import_hashes: Optional[Dict[str, str]] = None
    ) -> bool:
        """Check if cached graph is still valid.

        Valid only when the entry's own content hash matches AND every
        recorded dependency digest still matches the current one — a change
        inside any callee (direct or transitive) invalidates the entry.
        Module-level entries additionally require every recorded import
        file hash to match.
        """
        entry = self.get_cached_graph(function_id)
        if not entry:
            return False

        # Check content hash
        if self.compute_content_hash(source) != entry.content_hash:
            return False

        # Check callee hashes
        if callee_hashes != entry.callee_hashes:
            return False

        # Check dependency digests: every recorded digest must match, and
        # no new dependencies may appear.
        current_deps = dict(dependency_digests or {})
        if current_deps != dict(entry.dependency_digests or {}):
            return False
        for callee_id, digest in (entry.dependency_digests or {}).items():
            if current_deps.get(callee_id) != digest:
                return False

        # Module-level edges: imported file contents must be unchanged.
        stored_imports = (entry.metadata or {}).get('import_hashes') or {}
        if stored_imports:
            current_imports = dict(import_hashes or {})
            for path, digest in stored_imports.items():
                if current_imports.get(path) != digest:
                    return False

        return True

    def _persist_entry(self, entry: GraphCacheEntry):
        """Persist a cache entry to disk."""
        cache_file = self._cache_dir / f"{entry.function_id}.json"
        with open(cache_file, 'w') as f:
            json.dump({
                'function_id': entry.function_id,
                'content_hash': entry.content_hash,
                'cfg_hash': entry.cfg_hash,
                'dfg_hash': entry.dfg_hash,
                'callee_hashes': entry.callee_hashes,
                'dependency_digests': entry.dependency_digests,
                'timestamp': entry.timestamp,
                'metadata': entry.metadata
            }, f, indent=2)

    def _remove_persisted_entry(self, function_id: str):
        """Remove a persisted cache entry."""
        cache_file = self._cache_dir / f"{function_id}.json"
        if cache_file.exists():
            cache_file.unlink()

    def load_all_cached(self):
        """Load all cached entries from disk."""
        for cache_file in self._cache_dir.glob('*.json'):
            with open(cache_file) as f:
                data = json.load(f)
                entry = GraphCacheEntry(**data)
                self._cache[entry.function_id] = entry
