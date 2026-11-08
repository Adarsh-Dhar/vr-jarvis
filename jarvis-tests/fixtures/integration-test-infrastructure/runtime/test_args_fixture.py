#!/usr/bin/env python3
"""
Fixture for testing argument forwarding through the runtime trace runner.
Tests positional arguments, options with --, and arguments with spaces.
"""

import sys


def main():
    """Test argument handling."""
    print("Arguments received:")
    for i, arg in enumerate(sys.argv):
        print(f"  argv[{i}]: {arg}")

    # Check for expected arguments
    if len(sys.argv) > 1:
        print(f"Positional arg: {sys.argv[1]}")

    # Check for --config option
    if "--config" in sys.argv:
        idx = sys.argv.index("--config")
        if idx + 1 < len(sys.argv):
            print(f"Config file: {sys.argv[idx + 1]}")

    print("Test completed successfully.")


if __name__ == "__main__":
    main()
