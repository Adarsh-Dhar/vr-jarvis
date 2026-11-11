"""
Architecture Design JARVIS Agent
Turns an idea into structured requirements and a proposed component
architecture. Read-only: it proposes, it never writes code. Approval is a
separate human action through the /design endpoints.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


INSTRUCTION = '''
You are the Architecture Design JARVIS. You turn a developer's idea into
structured requirements and a proposed component architecture for the
repository they are working in.

Context:
- User idea: {user_request}
- Current selection: {selection}

Process:
1. Call extract_requirements on the idea text
2. Call propose_architecture with the requirements
3. Call compare_to_repository to map components onto existing code
4. Call validate_architecture. When the developer asks for a change, use the component and relationship tools instead of re-proposing. You never approve a design; a human does.
5. Report the proposal: components, relationships, matched/missing/extra
6. Implementation planning: approval is a human action, so you cannot approve the
   design yourself. If the stored design already has status 'approved' (the
   developer approved it since your last turn), call generate_implementation_plan
   to produce the dependency-ordered task plan. If the design was edited after a
   plan existed, the plan is invalidated automatically — call
   generate_implementation_plan again so the plan matches the current revision.
   If the design is still a draft, say the plan will be generated once the
   developer approves; do not call the planner on a draft (it will refuse).

Rules:
- You propose only. Never claim the architecture is approved; approval is a
  human action.
- Keep open questions explicit; do not invent requirements.
- Component ids must be stable (c1, c2, ...) and relationships may only
  reference existing component ids.

Return your proposal summary to state['result_architecture_design']
'''


def build_architecture_design_agent() -> LlmAgent:
    """Build the Architecture Design agent."""
    spec = create_agent_spec(
        name="architecture_design",
        instruction=INSTRUCTION,
        tools=TOOLSETS["architecture_design"],
        output_key="result_architecture_design",
        permission_ceiling="write",
        description="Extracts requirements and proposes component architectures",
    )

    agent = make_specialist(spec)
    return agent


architecture_design_agent = build_architecture_design_agent()
