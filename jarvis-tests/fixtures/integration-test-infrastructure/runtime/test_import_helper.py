#!/usr/bin/env python3
"""
Helper module for testing sibling module imports through the runtime trace runner.
"""


def helper_function(x: int) -> int:
    """A simple helper function to be imported."""
    return x * 2


def another_helper(x: int, y: int) -> int:
    """Another helper function."""
    return x + y
