#!/usr/bin/env python3
"""
Fixture for testing sibling module imports through the runtime trace runner.
Tests that imports from sibling files work correctly.
"""

# Import from sibling module
from test_import_helper import helper_function, another_helper


def main():
    """Test sibling module imports."""
    print("Testing sibling module imports...")

    # Use imported functions
    result1 = helper_function(5)
    print(f"helper_function(5) = {result1}")

    result2 = another_helper(10, 20)
    print(f"another_helper(10, 20) = {result2}")

    print("Import tests completed successfully.")


if __name__ == "__main__":
    main()
