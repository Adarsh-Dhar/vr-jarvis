"""
Threaded Code Example
Demonstrates multi-threaded code with a deliberate race condition.
"""

import threading
import time
from typing import List


class Counter:
    """Counter class with race condition"""

    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()

    def increment_unsafe(self):
        """Increment without lock - race condition!"""
        # Read
        current = self.count
        # Simulate some work
        time.sleep(0.0001)
        # Write
        self.count = current + 1

    def increment_safe(self):
        """Increment with lock - no race condition"""
        with self.lock:
            current = self.count
            time.sleep(0.0001)
            self.count = current + 1


def worker_unsafe(counter: Counter, iterations: int):
    """Worker that increments counter unsafely"""
    for _ in range(iterations):
        counter.increment_unsafe()


def worker_safe(counter: Counter, iterations: int):
    """Worker that increments counter safely"""
    for _ in range(iterations):
        counter.increment_safe()


def main():
    """Main function demonstrating race condition"""
    counter_unsafe = Counter()
    counter_safe = Counter()

    iterations = 1000
    num_threads = 10

    # Unsafe version - will have race condition
    threads_unsafe = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker_unsafe, args=(counter_unsafe, iterations))
        threads_unsafe.append(t)
        t.start()

    for t in threads_unsafe:
        t.join()

    # Safe version - no race condition
    threads_safe = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker_safe, args=(counter_safe, iterations))
        threads_safe.append(t)
        t.start()

    for t in threads_safe:
        t.join()

    expected = iterations * num_threads

    print(f"Unsafe counter: {counter_unsafe.count} (expected: {expected})")
    print(f"Safe counter: {counter_safe.count} (expected: {expected})")
    print(f"Race condition detected: {counter_unsafe.count != expected}")


if __name__ == '__main__':
    main()
