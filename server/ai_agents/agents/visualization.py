"""
Visualization and Spatial Intelligence Agent
Turns verified findings into scene commands and graphs.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


INSTRUCTION = '''
You are the Visualization and Spatial Intelligence specialist. You turn verified
findings into scene commands and graphs.

Context:
- Findings from other agents: {findings}
- Current selection: {selection}

Process:
1. Review verified findings from critic
2. Generate scene commands to highlight relevant nodes. Always finish by calling highlight_vr_path with the node ids from the findings, then open_code_panel for the main node. The graph changes only through these tools. Call set_mode with the tab that fits (MAP, CODE, FLOW, TESTS, IMPACT, AGENT, REPOS).
3. Create graphs for relationships, data flow, or impact
4. Apply visualization filters and layouts

Rules:
- Only draw nodes and edges that exist in verified findings
- Never fabricate graph elements
- Rendering is done by Unity, not by you

Return your analysis to state['result_visualization']
'''


def build_visualization_agent() -> LlmAgent:
    """Build the Visualization agent."""
    spec = create_agent_spec(
        name="visualization_spatial",
        instruction=INSTRUCTION,
        tools=TOOLSETS["visualization_spatial"],
        output_key="result_visualization",
        permission_ceiling="read",
        description="Turns findings into VR visualizations and scene commands",
    )

    agent = make_specialist(spec)
    return agent


visualization_agent = build_visualization_agent()
