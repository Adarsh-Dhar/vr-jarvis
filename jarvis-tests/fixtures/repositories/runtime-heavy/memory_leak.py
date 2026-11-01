"""
Memory Leak Example
Demonstrates a memory leak through a growing list.
"""

import time
from typing import List


class DataCache:
    """Cache that leaks memory by never clearing old entries"""

    def __init__(self):
        self.cache: List[dict] = []

    def add_data(self, key: str, value: any):
        """Add data to cache - never removes old entries"""
        self.cache.append({
            'key': key,
            'value': value,
            'timestamp': time.time()
        })

    def get_data(self, key: str) -> any:
        """Get data from cache"""
        for entry in self.cache:
            if entry['key'] == key:
                return entry['value']
        return None

    def get_cache_size(self) -> int:
        """Get current cache size"""
        return len(self.cache)


def simulate_leak():
    """Simulate memory leak over time"""
    cache = DataCache()

    for i in range(10000):
        cache.add_data(f'key_{i}', f'value_{i}')

        if i % 1000 == 0:
            print(f"Iteration {i}, cache size: {cache.get_cache_size()}")

    print(f"Final cache size: {cache.get_cache_size()}")
    print("Memory leaked: cache never cleared")


if __name__ == '__main__':
    simulate_leak()
