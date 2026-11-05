"""Skill registry for discovering and managing skills."""
from pathlib import Path
from typing import List, Dict, Optional
import yaml
import json

from ..contracts.skill import SkillManifest, SkillStatus, SkillResult


class SkillRegistry:
    """Registry for managing JARVIS skills."""
    
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: Dict[str, SkillManifest] = {}
        self._load_skills()
    
    def _load_skills(self):
        """Load all skills from the skills directory."""
        if not self.skills_dir.exists():
            return
        
        for skill_path in self.skills_dir.iterdir():
            if skill_path.is_dir() and (skill_path / "manifest.yaml").exists():
                self._load_skill(skill_path)
    
    def _load_skill(self, skill_path: Path):
        """Load a single skill from its manifest."""
        manifest_path = skill_path / "manifest.yaml"
        with open(manifest_path) as f:
            manifest_data = yaml.safe_load(f)
        
        manifest = SkillManifest(
            id=manifest_data['id'],
            name=manifest_data['name'],
            version=manifest_data['version'],
            owner=manifest_data['owner'],
            capabilities=manifest_data.get('capabilities', []),
            supported_languages=manifest_data.get('supported_languages', ['python']),
            tools=manifest_data.get('tools', []),
            permissions=manifest_data.get('permissions', []),
            status=SkillStatus(manifest_data.get('status', 'scaffolded')),
            tests_required=manifest_data.get('tests_required', True),
            description=manifest_data.get('description', '')
        )
        self._skills[manifest.id] = manifest
    
    def get(self, skill_id: str) -> Optional[SkillManifest]:
        """Get a skill by ID."""
        return self._skills.get(skill_id)
    
    def list(self, owner: Optional[str] = None) -> List[SkillManifest]:
        """List all skills, optionally filtered by owner."""
        skills = list(self._skills.values())
        if owner:
            skills = [s for s in skills if s.owner == owner]
        return skills
    
    def run(self, skill_id: str, args: Dict, tool_context: Dict) -> SkillResult:
        """Run a skill (placeholder - implementation depends on skill workflows)."""
        manifest = self.get(skill_id)
        if not manifest:
            return SkillResult(
                status=SkillStatus.SCAFFOLDED,
                errors=[f"Skill not found: {skill_id}"]
            )
        
        # Placeholder - actual implementation would load and run skill workflows
        return SkillResult(
            status=manifest.status,
            data={"skill_id": skill_id, "args": args},
            unsupported=True
        )


def get_skill_registry(skills_dir: Optional[Path] = None) -> SkillRegistry:
    """Get the global skill registry instance."""
    if skills_dir is None:
        # Default to repository root / ai_agents / skills
        import os
        repo_root = Path(os.getcwd())
        skills_dir = repo_root / "ai_agents" / "skills"
    return SkillRegistry(skills_dir)
