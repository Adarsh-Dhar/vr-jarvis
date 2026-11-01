"""
Investigation Memory
Persists investigation findings across sessions.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import time


class InvestigationMemory:
    """Persists investigation findings to disk."""

    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def save_investigation(self, investigation_id: str, findings: List[Dict[str, Any]]) -> None:
        """Save investigation to disk."""
        file_path = self.memory_dir / f"{investigation_id}.json"
        with open(file_path, 'w') as f:
            json.dump({
                "investigation_id": investigation_id,
                "findings": findings,
                "saved_at": time.time()
            }, f, indent=2)

    def load_investigation(self, investigation_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load previous investigation."""
        file_path = self.memory_dir / f"{investigation_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data.get("findings", [])

    def search_investigations(self, query: str) -> List[Dict[str, Any]]:
        """Search across investigations."""
        results = []
        for file_path in self.memory_dir.glob("*.json"):
            with open(file_path, 'r') as f:
                data = json.load(f)
                findings = data.get("findings", [])
                for finding in findings:
                    if query.lower() in finding.get("claim", "").lower():
                        results.append(finding)
        return results
