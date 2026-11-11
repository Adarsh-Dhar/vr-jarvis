"""
Test that all toolsets resolve to valid tools.
"""
import pytest
from ai_agents.agents.toolsets import TOOLSETS, TOOL_LEVELS, get_toolset, validate_toolsets


def test_every_toolset_resolves():
    """Test that every toolset name can be resolved to actual tools."""
    validate_toolsets()
    for name in TOOLSETS:
        assert get_toolset(name) is not None, f"Toolset {name} did not resolve"


def test_all_exported_tools_have_permission_levels():
    """Test that every tool exported from the tools module has a permission level in TOOL_LEVELS."""
    import inspect
    from ai_agents import tools as tools_module

    # Get all exported tools
    exported_tools = set(
        name for name, obj in inspect.getmembers(tools_module)
        if callable(obj) and not name.startswith('_')
    )

    # Check each exported tool has a permission level
    missing_levels = []
    for tool_name in exported_tools:
        if tool_name not in TOOL_LEVELS:
            missing_levels.append(tool_name)

    if missing_levels:
        pytest.fail(
            f"The following {len(missing_levels)} exported tools are missing from TOOL_LEVELS: "
            f"{sorted(missing_levels)}. Add them to TOOL_LEVELS in toolsets.py with appropriate "
            f"permission levels ('read', 'execute', or 'write')."
        )


def test_instructions_only_name_available_tools():
    from ai_agents.agents import (software_engineering, data_flow, testing_verification,
                                  code_understanding, relationship_intelligence,
                                  repository_intelligence)
    from ai_agents.agents.toolsets import validate_instruction_tools
    errors = validate_instruction_tools({
        'software_engineering': software_engineering.INSTRUCTION,
        'data_flow_intelligence': data_flow.INSTRUCTION,
        'testing_verification': testing_verification.INSTRUCTION,
        'code_understanding': code_understanding.INSTRUCTION,
        'relationship_intelligence': relationship_intelligence.INSTRUCTION,
        'repository_intelligence': repository_intelligence.INSTRUCTION,
    })
    assert errors == []
