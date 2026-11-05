"""Tool contracts for JARVIS skills architecture."""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class ToolSpec:
    """Specification for a tool."""
    name: str
    group: str
    level: str
    owner_agents: List[str] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
