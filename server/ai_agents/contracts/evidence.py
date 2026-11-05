"""Evidence contracts for JARVIS skills architecture."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Evidence:
    """Evidence for a skill operation or graph relationship."""
    kind: str  # static_analysis, runtime_observation, ai_hypothesis
    file: str
    line: int
    column: int = 0
    expression: str = ""
    confidence: Optional[float] = None  # 0.0 to 1.0 for AI hypotheses
