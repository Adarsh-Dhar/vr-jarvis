"""
Runtime Intelligence Agent
Understands what actually happened when the code ran.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from ..base import make_specialist, create_agent_spec
from ..toolsets import TOOLSETS


INSTRUCTION = '''
You are the Runtime Intelligence specialist. You understand what actually happened
when the code ran.

Context:
- Sandbox worktree: {worktree}
- Active task: {active_task}

Process:
1. Start application in sandbox
2. Collect execution trace
3. Record function calls, timing, memory, CPU
4. Capture application logs
5. Compare execution traces if needed

Rules:
- Separate measured results from estimates
- Never run outside sandbox worktree
- Use record_finding for all runtime claims

Return your analysis to state['result_runtime']
'''


def build_runtime_intelligence_agent() -> LlmAgent:
    """Build the Runtime Intelligence agent."""
    spec = create_agent_spec(
        name="runtime_intelligence",
        instruction=INSTRUCTION,
        tools=TOOLSETS["runtime_intelligence"],
        output_key="result_runtime",
        permission_ceiling="execute",  # sandbox only
        description="Analyzes runtime behavior and execution traces",
    )

    agent = make_specialist(spec)
    return agent


runtime_intelligence_agent = build_runtime_intelligence_agent()
