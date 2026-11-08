#!/usr/bin/env python3
"""
Fixture for testing manual stop of a long-running application.
This fixture sleeps for 10 seconds to ensure it's still running when manually stopped.
"""

import time


def main():
    """Long-running application that sleeps."""
    print("Starting long-running application...")
    print("Will sleep for 10 seconds.")
    
    for i in range(10):
        time.sleep(1)
        print(f"Still running... {i+1}/10 seconds")
    
    print("Long-running application completed naturally.")


if __name__ == "__main__":
    main()
