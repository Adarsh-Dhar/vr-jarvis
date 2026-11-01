"""
Queue Client - Simulated Message Queue
In production this would connect to RabbitMQ or similar.
"""

from typing import Dict, Any, Callable
from collections import defaultdict
import threading


class QueueClient:
    """Simulated message queue client"""

    def __init__(self):
        self.queues = defaultdict(list)
        self.subscribers = defaultdict(list)
        self.lock = threading.Lock()

    def publish(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """Publish a message to a queue"""
        with self.lock:
            self.queues[queue_name].append(message)
            # Notify subscribers
            for callback in self.subscribers[queue_name]:
                callback(message)
        return True

    def subscribe(self, queue_name: str, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to a queue"""
        with self.lock:
            self.subscribers[queue_name].append(callback)

    def get_messages(self, queue_name: str) -> list:
        """Get all messages from a queue"""
        with self.lock:
            return self.queues[queue_name].copy()

    def clear_queue(self, queue_name: str):
        """Clear a queue"""
        with self.lock:
            self.queues[queue_name].clear()
