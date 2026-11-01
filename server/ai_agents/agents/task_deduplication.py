"""
Task Deduplication
Prevents duplicate tasks from being executed.
"""

from typing import Dict, Any, Optional
import hashlib
import json


class TaskDeduplicator:
    """Prevents duplicate task execution."""

    def __init__(self):
        self.running_tasks: Dict[str, Dict] = {}

    def _task_key(self, task: Dict) -> str:
        """Generate a unique key for a task."""
        # Use a hash of the task content
        task_str = json.dumps(task, sort_keys=True)
        return hashlib.md5(task_str.encode()).hexdigest()

    def is_duplicate(self, task: Dict) -> bool:
        """Check if a task is a duplicate of a running task."""
        key = self._task_key(task)
        return key in self.running_tasks

    def register(self, task: Dict) -> str:
        """Register a task as running."""
        key = self._task_key(task)
        self.running_tasks[key] = {
            "task": task,
            "started_at": None,  # Timestamp would go here
        }
        return key

    def unregister(self, task: Dict) -> bool:
        """Unregister a task as complete."""
        key = self._task_key(task)
        if key in self.running_tasks:
            del self.running_tasks[key]
            return True
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get status of all running tasks."""
        return {
            "running_count": len(self.running_tasks),
            "tasks": list(self.running_tasks.keys()),
        }


# Global deduplicator instance
task_deduplicator = TaskDeduplicator()
