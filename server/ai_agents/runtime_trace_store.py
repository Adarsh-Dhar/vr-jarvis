"""
Runtime Trace Store
Session-scoped storage for execution traces with isolation and cleanup.

Provides:
- save_trace(trace_id, session_id, trace_data): Save JSON trace with session ownership
- get_trace(trace_id, session_id): Load trace with session validation
- delete_trace(trace_id, session_id): Clean up trace files
- cleanup_old_traces(): Automatic cleanup of old traces
"""

import json
import os
import time
import threading
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime, timedelta


class RuntimeTraceStore:
    """Session-scoped trace storage with isolation and automatic cleanup."""

    def __init__(self, storage_dir: Optional[Path] = None, max_trace_size_mb: int = 10, max_age_hours: int = 24):
        """
        Initialize the trace store.

        Args:
            storage_dir: Directory for trace files (defaults to server/data/runtime_traces)
            max_trace_size_mb: Maximum size of a single trace in MB
            max_age_hours: Maximum age of traces before cleanup
        """
        if storage_dir is None:
            # Default to server/data/runtime_traces (outside source repository)
            from ai_agents import config
            storage_dir = config.ROOT / 'data' / 'runtime_traces'

        self.storage_dir = Path(storage_dir).resolve()
        self.max_trace_size_bytes = max_trace_size_mb * 1024 * 1024
        self.max_age_hours = max_age_hours
        self.lock = threading.Lock()

        # Create storage directory if it doesn't exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Metadata file to track trace ownership
        self.metadata_file = self.storage_dir / 'metadata.json'
        self.metadata: Dict[str, Dict[str, Any]] = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Load metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_metadata(self):
        """Save metadata to disk atomically."""
        temp_file = self.metadata_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            temp_file.replace(self.metadata_file)
        except Exception as e:
            print(f"Warning: Failed to save trace metadata: {e}")

    def _get_trace_path(self, trace_id: str) -> Path:
        """Get the file path for a trace."""
        return self.storage_dir / f"{trace_id}.json"

    def save_trace(self, trace_id: str, session_id: str, trace_data: Dict[str, Any]) -> bool:
        """
        Save a trace with session ownership validation.

        Args:
            trace_id: Unique trace identifier
            session_id: Session ID for ownership
            trace_data: Trace data to save

        Returns:
            True if saved successfully, False otherwise
        """
        with self.lock:
            trace_path = self._get_trace_path(trace_id)

            # Check trace size
            trace_json = json.dumps(trace_data)
            if len(trace_json.encode('utf-8')) > self.max_trace_size_bytes:
                print(f"Warning: Trace {trace_id} exceeds maximum size, not saved")
                return False

            # Write trace atomically
            temp_path = trace_path.with_suffix('.tmp')
            try:
                with open(temp_path, 'w') as f:
                    json.dump(trace_data, f, indent=2)
                temp_path.replace(trace_path)

                # Update metadata
                self.metadata[trace_id] = {
                    'session_id': session_id,
                    'created_at': datetime.utcnow().isoformat(),
                    'size_bytes': len(trace_json.encode('utf-8')),
                    'application_id': trace_data.get('application_id', 'unknown')
                }
                self._save_metadata()

                return True
            except Exception as e:
                print(f"Error saving trace {trace_id}: {e}")
                # Clean up temp file if it exists
                if temp_path.exists():
                    temp_path.unlink()
                return False

    def get_trace(self, trace_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a trace with session validation.

        Args:
            trace_id: Unique trace identifier
            session_id: Session ID to validate ownership

        Returns:
            Trace data if found and session matches, None otherwise
        """
        with self.lock:
            # Check metadata for session ownership
            if trace_id not in self.metadata:
                return None

            trace_meta = self.metadata[trace_id]
            if trace_meta['session_id'] != session_id:
                # Session mismatch - access denied
                return None

            trace_path = self._get_trace_path(trace_id)
            if not trace_path.exists():
                # Metadata exists but file missing - clean up metadata
                del self.metadata[trace_id]
                self._save_metadata()
                return None

            try:
                with open(trace_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading trace {trace_id}: {e}")
                return None

    def delete_trace(self, trace_id: str, session_id: str) -> bool:
        """
        Delete a trace with session validation.

        Args:
            trace_id: Unique trace identifier
            session_id: Session ID to validate ownership

        Returns:
            True if deleted successfully, False otherwise
        """
        with self.lock:
            # Check metadata for session ownership
            if trace_id not in self.metadata:
                return False

            trace_meta = self.metadata[trace_id]
            if trace_meta['session_id'] != session_id:
                # Session mismatch - access denied
                return False

            trace_path = self._get_trace_path(trace_id)
            try:
                if trace_path.exists():
                    trace_path.unlink()

                # Remove from metadata
                del self.metadata[trace_id]
                self._save_metadata()

                return True
            except Exception as e:
                print(f"Error deleting trace {trace_id}: {e}")
                return False

    def cleanup_old_traces(self) -> int:
        """
        Clean up traces older than max_age_hours.

        Returns:
            Number of traces cleaned up
        """
        with self.lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=self.max_age_hours)
            cleaned = 0

            trace_ids_to_delete = []

            for trace_id, meta in self.metadata.items():
                try:
                    created_at = datetime.fromisoformat(meta['created_at'])
                    if created_at < cutoff:
                        trace_ids_to_delete.append(trace_id)
                except Exception:
                    # If we can't parse the date, delete it
                    trace_ids_to_delete.append(trace_id)

            for trace_id in trace_ids_to_delete:
                trace_path = self._get_trace_path(trace_id)
                try:
                    if trace_path.exists():
                        trace_path.unlink()
                    del self.metadata[trace_id]
                    cleaned += 1
                except Exception as e:
                    print(f"Error cleaning up trace {trace_id}: {e}")

            if cleaned > 0:
                self._save_metadata()

            return cleaned

    def get_session_traces(self, session_id: str) -> list:
        """
        Get all trace IDs for a given session.

        Args:
            session_id: Session ID

        Returns:
            List of trace IDs
        """
        with self.lock:
            return [
                trace_id
                for trace_id, meta in self.metadata.items()
                if meta['session_id'] == session_id
            ]


# Global singleton instance
_trace_store_instance: Optional[RuntimeTraceStore] = None
_trace_store_lock = threading.Lock()


def get_trace_store() -> RuntimeTraceStore:
    """Get the global trace store singleton."""
    global _trace_store_instance
    with _trace_store_lock:
        if _trace_store_instance is None:
            _trace_store_instance = RuntimeTraceStore()
        return _trace_store_instance
