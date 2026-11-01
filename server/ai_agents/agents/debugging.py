"""
Debugging Intelligence Agent
Finds the root cause of errors and unexpected behavior.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


INSTRUCTION = '''
You are the Debugging Intelligence specialist. You find the root cause of errors
and unexpected behavior.

Context:
- Error or stack trace: {error_context}
- Sandbox worktree: {worktree}
- Active task: {active_task}

Process:
1. Analyze stack trace
2. Find error origin and trace propagation
3. Identify failure path
4. Reproduce bug if possible
5. Compare success vs failure execution
6. Identify root cause

Rules:
- Root cause is stated as hypothesis with evidence for and against
- Until reproduction confirms, mark as hypothesis
- Use record_finding for all debugging claims

Return your analysis to state['result_debugging']
'''


def build_debugging_intelligence_agent() -> LlmAgent:
    """Build the Debugging Intelligence agent."""
    spec = create_agent_spec(
        name="debugging_intelligence",
        instruction=INSTRUCTION,
        tools=TOOLSETS["debugging_intelligence"],
        output_key="result_debugging",
        permission_ceiling="execute",  # sandbox only
        description="Finds root causes of errors and bugs",
    )

    agent = make_specialist(spec)
    return agent


debugging_intelligence_agent = build_debugging_intelligence_agent()
