"""
Repository Intelligence Agent
Understands codebase structure, languages, frameworks, build system, and what changed.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


# Instruction template for Repository Intelligence agent
INSTRUCTION = '''
You are the Repository Intelligence specialist. You understand the codebase structure,
languages, frameworks, build system, and what changed.

Context:
- Repository path: {repo_path}
- Active task: {active_task}

Process:
1. Detect languages, frameworks, build system
2. Analyze repository structure and entry points
3. Identify external services and generated files
4. Detect recent changes if relevant

Rules:
- Report only what tools return
- Mark inferred information as inferred
- Use record_finding for all structural claims
- Never fabricate repository metadata

Return your analysis to state['result_repository']
'''


def build_repository_intelligence_agent() -> LlmAgent:
    """Build the Repository Intelligence agent."""
    spec = create_agent_spec(
        name="repository_intelligence",
        instruction=INSTRUCTION,
        tools=TOOLSETS["repository_intelligence"],
        output_key="result_repository",
        permission_ceiling="read",
        description="Analyzes repository structure, languages, frameworks, and changes",
        skills=["repository_architecture", "repository_browser"],
    )

    agent = make_specialist(spec)
    return agent


# Create singleton instance
repository_intelligence_agent = build_repository_intelligence_agent()
