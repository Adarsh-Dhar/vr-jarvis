"""Tests for skill and tool registries."""
import pytest
from pathlib import Path
import tempfile
import yaml

from ai_agents.contracts.skill import SkillManifest, SkillStatus
from ai_agents.contracts.tool import ToolSpec
from ai_agents.registry.skill_registry import SkillRegistry
from ai_agents.registry.tool_registry import ToolRegistry


def test_skill_registry_basic():
    """Test basic skill registry operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir)
        
        # Create a sample skill
        skill_path = skills_dir / "test_skill"
        skill_path.mkdir()
        
        manifest_data = {
            'id': 'test_skill',
            'name': 'Test Skill',
            'version': '1.0.0',
            'owner': 'test_agent',
            'capabilities': ['test'],
            'supported_languages': ['python'],
            'tools': [],
            'permissions': [],
            'status': 'implemented',
            'tests_required': True,
            'description': 'A test skill'
        }
        
        with open(skill_path / "manifest.yaml", 'w') as f:
            yaml.dump(manifest_data, f)
        
        # Load registry
        registry = SkillRegistry(skills_dir)
        
        # Test get
        skill = registry.get('test_skill')
        assert skill is not None
        assert skill.id == 'test_skill'
        assert skill.name == 'Test Skill'
        assert skill.status == SkillStatus.IMPLEMENTED
        
        # Test list
        skills = registry.list()
        assert len(skills) == 1
        assert skills[0].id == 'test_skill'
        
        # Test list with owner filter
        test_agent_skills = registry.list(owner='test_agent')
        assert len(test_agent_skills) == 1


def test_tool_registry_basic():
    """Test basic tool registry operations."""
    registry = ToolRegistry()
    
    # Test that tools are loaded from TOOLSETS
    tools = registry.list()
    assert len(tools) > 0
    
    # Test get
    # Find a known tool
    if tools:
        tool = registry.get(tools[0].name)
        assert tool is not None
        assert tool.name == tools[0].name
        assert tool.group is not None
        assert tool.level is not None
    
    # Test by_level - check that at least one level has tools
    levels = set(t.level for t in tools)
    assert len(levels) > 0
    
    # Check a level that exists
    if levels:
        first_level = list(levels)[0]
        level_tools = registry.by_level(first_level)
        assert len(level_tools) > 0
