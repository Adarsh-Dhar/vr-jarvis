#!/usr/bin/env python3
"""
Fixture for testing event and duration limits.
Generates many function calls to test event limit truncation.
Can sleep to test duration limit enforcement.
"""

import time


def generate_events(count: int):
    """Generate a specified number of function call events."""
    for i in range(count):
        simple_function(i)


def simple_function(n: int) -> int:
    """A simple function that returns its input."""
    return n * 2


def long_running_task(seconds: float):
    """A task that runs for a specified duration."""
    print(f"Sleeping for {seconds} seconds...")
    time.sleep(seconds)
    print("Task completed.")


def main():
    """Main entry point - can be configured for different limit tests."""
    import sys

    # Check command line arguments to determine test type
    if len(sys.argv) > 1 and sys.argv[1] == "--event-limit":
        # Generate many events to test event limit
        event_count = 100
        if len(sys.argv) > 2:
            event_count = int(sys.argv[2])
        print(f"Generating {event_count} events...")
        generate_events(event_count)
        print(f"Generated {event_count} events.")

    elif len(sys.argv) > 1 and sys.argv[1] == "--duration-limit":
        # Run for a long time to test duration limit
        duration = 10
        if len(sys.argv) > 2:
            duration = float(sys.argv[2])
        print(f"Running for {duration} seconds...")
        long_running_task(duration)

    else:
        # Default: moderate number of events
        print("Generating default test events...")
        generate_events(50)
        print("Default test completed.")


if __name__ == "__main__":
    main()
