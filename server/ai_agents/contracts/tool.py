"""Tool contracts for JARVIS skills architecture."""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass(frozen=True)
class Constraint:
    """A JSON-schema fragment attached to a parameter via Annotated.

    Type hints cannot express value constraints like minimum: 1; wrap the
    annotation as ``Annotated[int, Min(1)]`` and the registry merges the
    constraint into the generated schema."""
    schema: Dict[str, Any]


Min = lambda n: Constraint({'minimum': n})
Max = lambda n: Constraint({'maximum': n})
MinLen = lambda n: Constraint({'minLength': n})


@dataclass
class ToolSpec:
    """Specification for a tool."""
    name: str
    group: str
    level: str
    owner_agents: List[str] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
