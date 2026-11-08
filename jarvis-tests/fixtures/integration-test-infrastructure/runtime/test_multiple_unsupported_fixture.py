#!/usr/bin/env python3
"""
Fixture for testing that multiple unsupported execution types are all reported.
Tests async, generator, and background thread cases in one application.
"""

import asyncio
import threading
import time


def generator_function():
    """A generator function (unsupported)."""
    for i in range(5):
        yield i


async def async_function():
    """An async function (unsupported)."""
    await asyncio.sleep(0.1)
    return "async result"


def background_thread_task():
    """A task to run in a background thread (unsupported)."""
    time.sleep(0.1)
    print("Background thread completed.")


def main():
    """Test multiple unsupported execution types."""
    print("Testing multiple unsupported execution types...")

    # Test 1: Generator
    print("Testing generator...")
    gen = generator_function()
    for value in gen:
        print(f"  Generator yielded: {value}")

    # Test 2: Async (run in event loop)
    print("Testing async...")
    try:
        result = asyncio.run(async_function())
        print(f"  Async result: {result}")
    except Exception as e:
        print(f"  Async error: {e}")

    # Test 3: Background thread
    print("Testing background thread...")
    thread = threading.Thread(target=background_thread_task)
    thread.start()
    thread.join()

    print("Multiple unsupported tests completed.")


if __name__ == "__main__":
    main()
