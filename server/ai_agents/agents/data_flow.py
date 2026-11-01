"""
Data Flow Intelligence Agent
Traces where data comes from, how it changes, and where it ends up.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from ..base import make_specialist, create_agent_spec
from ..toolsets import TOOLSETS


INSTRUCTION = '''
You are the Data Flow Intelligence specialist. You trace where data comes from,
how it changes, and where it ends up.

Context:
- Selected node: {selection}
- Active task: {active_task}

Process:
1. Trace variable origin and usage
2. Trace parameter and return value flow
3. Trace transformations across functions
4. Identify data sources, sinks, and leaks
5. Trace database and API data flow

Rules:
- Report only what tools return
- Mark inferred paths as inferred
- Use record_finding for all data flow claims

Return your analysis to state['result_data_flow']
'''


def build_data_flow_agent() -> LlmAgent:
    """Build the Data Flow Intelligence agent."""
    spec = create_agent_spec(
        name="data_flow_intelligence",
        instruction=INSTRUCTION,
        tools=TOOLSETS["data_flow_intelligence"],
        output_key="result_data_flow",
        permission_ceiling="read",
        description="Traces data flow through the codebase",
    )

    agent = make_specialist(spec)
    return agent


data_flow_intelligence_agent = build_data_flow_agent()
