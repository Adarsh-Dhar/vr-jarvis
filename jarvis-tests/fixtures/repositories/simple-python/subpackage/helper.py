# Helper module for cross-package import testing

def helper_function():
    """Helper function called from main module"""
    return "helper"


def helper_with_imports():
    """Helper function with imports"""
    import os
    import json
    return os.path.exists(".")
