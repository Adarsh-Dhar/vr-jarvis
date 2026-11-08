#!/usr/bin/env python3
"""
Fixture for testing exception deduplication.
Tests that two separate exceptions on the same line are recorded separately,
and that propagation of one exception doesn't create duplicates.
"""


def raise_separate_exceptions():
    """Raise two separate ValueError instances on the same line."""
    # First exception
    try:
        raise ValueError("First error")
    except ValueError:
        pass

    # Second exception (same type, same line, different instance)
    try:
        raise ValueError("Second error")
    except ValueError:
        pass


def propagate_exception():
    """Propagate an exception through multiple function calls."""
    try:
        inner_function()
    except ValueError as e:
        print(f"Caught propagated exception: {e}")


def inner_function():
    """Raise an exception that will propagate."""
    raise ValueError("Propagated error")


def main():
    """Run exception tests."""
    print("Testing exception deduplication...")

    # Test 1: Two separate exceptions on same line
    raise_separate_exceptions()

    # Test 2: Exception propagation
    propagate_exception()

    print("Exception tests completed.")


if __name__ == "__main__":
    main()
