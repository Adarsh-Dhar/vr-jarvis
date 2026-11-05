"""Tests for skill status validation."""
import pytest
from ai_agents.contracts.skill import SkillStatus
from ai_agents.registry.skill_registry import get_skill_registry


def test_skill_status_not_validated_without_tests():
    """A skill should not be marked validated without passing tests."""
    registry = get_skill_registry()
    
    # Check function_call_graph skill
    skill = registry.get('function_call_graph')
    assert skill is not None
    
    # It should be implemented, not validated (tests not yet written)
    assert skill.status == SkillStatus.IMPLEMENTED
    assert skill.status != SkillStatus.VALIDATED
    
    # Note: Status will change to validated after M10 ground-truth tests pass