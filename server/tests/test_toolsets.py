"""
Test that all toolsets resolve to valid tools.
"""
import pytest
from ai_agents.agents.toolsets import TOOLSETS, get_toolset, validate_toolsets


def test_every_toolset_resolves():
    """Test that every toolset name can be resolved to actual tools."""
    validate_toolsets()
    for name in TOOLSETS:
        assert get_toolset(name) is not None, f"Toolset {name} did not resolve"
