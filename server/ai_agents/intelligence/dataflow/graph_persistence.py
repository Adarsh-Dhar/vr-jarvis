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
    timestamp: float
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
        callee_hashes: Dict[str, str]
    ) -> GraphCacheEntry:
        """Cache a graph with its hashes."""
        content_hash = self.compute_content_hash(source)
        cfg_hash = self.compute_cfg_hash(cfg)
        dfg_hash = self.compute_dfg_hash(dfg)

        entry = GraphCacheEntry(
            function_id=function_id,
            content_hash=content_hash,
            cfg_hash=cfg_hash,
            dfg_hash=dfg_hash,
            callee_hashes=callee_hashes,
            timestamp=__import__('time').time(),
            metadata={}
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
        callee_hashes: Dict[str, str]
    ) -> bool:
        """Check if cached graph is still valid."""
        entry = self.get_cached_graph(function_id)
        if not entry:
            return False

        # Check content hash
        if self.compute_content_hash(source) != entry.content_hash:
            return False

        # Check callee hashes
        if callee_hashes != entry.callee_hashes:
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
