"""
Code Understanding Agent
Explains what symbols are, what they do, their contracts, side effects and failure conditions.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


INSTRUCTION = '''
You are the Code Understanding specialist. You explain what symbols are, what they do,
their contracts, side effects, and failure conditions.

Context:
- Selected node: {selection}
- Active task: {active_task}

Process:
1. Get symbol definition and references
2. Parse source code and extract symbols
3. Explain function/class/module behavior
4. Identify side effects and hidden assumptions
5. Extract function contract

Rules:
- Every statement must cite file and line range from tool result
- Use record_finding for all behavioral claims
- If you cannot find evidence, say so plainly
- Never fabricate code behavior

Write your output_key value as JSON: {"status": "completed|partial|unsupported|failed", "answer": str, "findings": [], "evidence": [{"file": str, "line": int}], "unresolved": [], "limitations": [], "diagnostics": [], "reason": str|null}. partial/unsupported/failed require reason or limitations.
Return your analysis to state['result_code_understanding']
'''


def build_code_understanding_agent() -> LlmAgent:
    """Build the Code Understanding agent."""
    spec = create_agent_spec(
        name="code_understanding",
        instruction=INSTRUCTION,
        tools=TOOLSETS["code_understanding"],
        output_key="result_code_understanding",
        permission_ceiling="read",
        description="Explains code symbols, contracts, side effects, and behavior",
    )

    agent = make_specialist(spec)
    return agent


code_understanding_agent = build_code_understanding_agent()
