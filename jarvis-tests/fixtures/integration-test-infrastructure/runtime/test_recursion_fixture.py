#!/usr/bin/env python3
"""
Fixture for testing recursive function calls.
Tests that recursive invocations receive distinct call IDs and correct parent relationships.
"""


def fibonacci(n: int) -> int:
    """Calculate fibonacci number (recursive)."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def factorial(n: int) -> int:
    """Calculate factorial (recursive)."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def main():
    """Test recursive functions."""
    print("Testing recursive functions...")

    # Test fibonacci
    fib_result = fibonacci(8)
    print(f"fibonacci(8) = {fib_result}")

    # Test factorial
    fact_result = factorial(6)
    print(f"factorial(6) = {fact_result}")

    print("Recursion tests completed.")


if __name__ == "__main__":
    main()
