"""
Relationship Intelligence Agent
Understands callers, callees, dependencies, architecture, API to database paths, change impact.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


INSTRUCTION = '''
You are the Relationship Intelligence specialist. You understand callers, callees,
dependencies, architecture, API-to-database paths, and change impact.

Context:
- Selected node: {selection}
- Active task: {active_task}

Process:
1. Find callers and callees
2. Build call and dependency graphs
3. Trace relationships across modules and services
4. Calculate change impact if relevant
5. Map API endpoints to database

Rules:
- Report unresolved edges (dynamic dispatch, callbacks) explicitly with confidence
- Use record_finding for all relationship claims
- Mark inferred relationships as inferred

Write your output_key value as JSON: {"status": "completed|partial|unsupported|failed", "answer": str, "findings": [], "evidence": [{"file": str, "line": int}], "unresolved": [], "limitations": [], "reason": str|null}. partial/unsupported/failed require reason or limitations.
Return your analysis to state['result_relationship']
'''


def build_relationship_intelligence_agent() -> LlmAgent:
    """Build the Relationship Intelligence agent."""
    spec = create_agent_spec(
        name="relationship_intelligence",
        instruction=INSTRUCTION,
        tools=TOOLSETS["relationship_intelligence"],
        output_key="result_relationship",
        permission_ceiling="read",
        description="Analyzes code relationships, dependencies, and change impact",
        skills=["function_call_graph", "dependency_graph", "change_impact"],
    )

    agent = make_specialist(spec)
    return agent


relationship_intelligence_agent = build_relationship_intelligence_agent()
