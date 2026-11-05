"""Graph contracts for JARVIS skills architecture."""
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional
from .evidence import Evidence


class Resolution(Enum):
    """Resolution status for call graph edges."""
    STATIC_RESOLVED = "static_resolved"
    AMBIGUOUS = "ambiguous"
    POLYMORPHIC = "polymorphic"
    UNRESOLVED = "unresolved"
    EXTERNAL = "external"
    RUNTIME_OBSERVED = "runtime_observed"


class Dispatch(Enum):
    """Dispatch type for method calls."""
    DIRECT = "direct"
    METHOD = "method"
    DYNAMIC = "dynamic"


@dataclass
class Node:
    """Graph node."""
    id: str
    name: str
    kind: str
    file: str
    start: int
    end: int
    cluster: str = ""
    level: str = ""
    parent: str = ""
    legacy_id: str = ""
    class_name: str = ""


@dataclass
class Edge:
    """Graph edge."""
    id: str
    src: str
    dst: str
    type: str
    kind: str
    resolution: Resolution
    dispatch: Dispatch
    file: str
    line: int
    call_type: str = ""
    column: int = 0
    candidates: List[str] = None
    evidence: Evidence = None
    
    def __post_init__(self):
        if self.candidates is None:
            self.candidates = []


SCHEMA_VERSION = 2
