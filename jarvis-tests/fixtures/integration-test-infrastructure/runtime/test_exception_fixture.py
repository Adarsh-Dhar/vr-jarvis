#!/usr/bin/env python3
"""
Fixture for testing exception deduplication.
Tests that two separate exceptions on the same line are recorded separately,
and that propagation of one exception doesn't create duplicates.
"""


def raise_at_same_line(message):
    """Helper to raise exceptions on the same source line."""
    raise ValueError(message)


def test_same_line_exceptions():
    """Test two different exceptions raised from the same source line."""
    for message in ["First error", "Second error"]:
        try:
            raise_at_same_line(message)
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
    test_same_line_exceptions()

    # Test 2: Exception propagation
    propagate_exception()

    print("Exception tests completed.")


if __name__ == "__main__":
    main()
