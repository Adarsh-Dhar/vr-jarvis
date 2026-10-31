#!/usr/bin/env python3
"""
Sample application for runtime tracing and execution testing
"""

import time
import random
from typing import List, Dict


class DataProcessor:
    """A class for processing data"""

    def __init__(self, name: str):
        self.name = name
        self.processed_count = 0

    def process(self, data: List[int]) -> List[int]:
        """Process a list of integers"""
        self.processed_count += len(data)
        return [x * 2 for x in data]

    def filter_data(self, data: List[int], threshold: int) -> List[int]:
        """Filter data based on threshold"""
        return [x for x in data if x > threshold]


def calculate_statistics(data: List[int]) -> Dict[str, float]:
    """Calculate basic statistics"""
    if not data:
        return {}

    return {
        'mean': sum(data) / len(data),
        'min': min(data),
        'max': max(data),
        'sum': sum(data)
    }


def fibonacci(n: int) -> int:
    """Calculate fibonacci number (recursive)"""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def bubble_sort(arr: List[int]) -> List[int]:
    """Bubble sort implementation"""
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr


def simulate_api_call(endpoint: str, delay: float = 0.1) -> Dict:
    """Simulate an API call with delay"""
    time.sleep(delay)
    return {
        'endpoint': endpoint,
        'status': 'success',
        'timestamp': time.time()
    }


def main():
    """Main application flow"""
    print("Starting sample application...")

    # Create processor
    processor = DataProcessor("MainProcessor")

    # Generate sample data
    data = [random.randint(1, 100) for _ in range(10)]
    print(f"Generated data: {data}")

    # Process data
    processed = processor.process(data)
    print(f"Processed data: {processed}")

    # Filter data
    filtered = processor.filter_data(processed, 50)
    print(f"Filtered data: {filtered}")

    # Calculate statistics
    stats = calculate_statistics(filtered)
    print(f"Statistics: {stats}")

    # Run fibonacci
    fib_result = fibonacci(10)
    print(f"Fibonacci(10): {fib_result}")

    # Sort data
    sorted_data = bubble_sort(data.copy())
    print(f"Sorted data: {sorted_data}")

    # Simulate API calls
    api_result = simulate_api_call("/api/data")
    print(f"API result: {api_result}")

    print("Application completed.")


if __name__ == "__main__":
    main()
