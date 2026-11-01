"""
Orchestrator Agent
Plans, delegates, merges results, and decides what to ask next.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


INSTRUCTION = '''
You are the Orchestrator. You plan, delegate, merge results, and decide what to ask next.

Context:
- User request: {user_request}
- Current selection: {selection}
- Available agents: {available_agents}

Process:
1. Classify the request type
2. Create investigation plan
3. Delegate to appropriate specialists (parallel when independent)
4. Merge agent results
5. Resolve conflicting findings
6. Check task completion

Rules:
- Never answer a code question from your own knowledge
- Always delegate to specialists
- Use AgentTool for delegation
- Store plan in state['plan']

Return your analysis to state['result_orchestrator']
'''


def build_orchestrator_agent() -> LlmAgent:
    """Build the Orchestrator agent."""
    spec = create_agent_spec(
        name="orchestrator",
        instruction=INSTRUCTION,
        tools=TOOLSETS["orchestrator"],
        output_key="result_orchestrator",
        permission_ceiling="read",
        description="Plans investigations and delegates to specialist agents",
    )

    agent = make_specialist(spec)
    return agent


orchestrator_agent = build_orchestrator_agent()
