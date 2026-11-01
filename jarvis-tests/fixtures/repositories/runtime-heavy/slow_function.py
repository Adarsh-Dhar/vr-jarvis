"""
Slow Function Example
Intentionally slow function for timeout testing.
"""

import time
from typing import List


def slow_fibonacci(n: int) -> int:
    """Deliberately slow recursive Fibonacci implementation"""
    if n <= 1:
        return n
    return slow_fibonacci(n - 1) + slow_fibonacci(n - 2)


def slow_sort(arr: List[int]) -> List[int]:
    """Deliberately slow bubble sort"""
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr


def slow_string_match(text: str, pattern: str) -> bool:
    """Deliberately slow string matching"""
    if pattern not in text:
        return False

    # Very slow matching algorithm
    for i in range(len(text)):
        if text[i:i+len(pattern)] == pattern:
            # Artificial delay
            time.sleep(0.001)
            return True

    return False


if __name__ == '__main__':
    # Test slow functions
    print("Testing slow fibonacci...")
    start = time.time()
    result = slow_fibonacci(35)
    duration = time.time() - start
    print(f"Fibonacci(35) = {result}, took {duration:.2f}s")

    print("\nTesting slow sort...")
    arr = list(range(1000, 0, -1))
    start = time.time()
    sorted_arr = slow_sort(arr.copy())
    duration = time.time() - start
    print(f"Sorted 1000 elements, took {duration:.2f}s")

    print("\nTesting slow string match...")
    text = "a" * 10000 + "target" + "b" * 10000
    start = time.time()
    found = slow_string_match(text, "target")
    duration = time.time() - start
    print(f"Found pattern: {found}, took {duration:.2f}s")
