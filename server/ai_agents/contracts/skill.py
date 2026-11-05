"""Skill contracts and status definitions."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class SkillStatus(Enum):
    """Status of a skill implementation."""
    SCAFFOLDED = "scaffolded"
    IMPLEMENTED = "implemented"
    VALIDATED = "validated"
    STRESS_TESTED = "stress_tested"
    PRODUCTION = "production"


@dataclass
class SkillManifest:
    """Manifest for a skill."""
    id: str
    name: str
    version: str
    owner: str
    capabilities: List[str]
    supported_languages: List[str] = field(default_factory=lambda: ["python"])
    tools: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    status: SkillStatus = SkillStatus.SCAFFOLDED
    tests_required: bool = True
    description: str = ""


@dataclass
class SkillResult:
    """Result from running a skill."""
    status: SkillStatus
    data: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    unsupported: bool = False
