"""
Security and Quality Agent
Finds vulnerabilities, secrets, injection risks, authorization gaps, complexity, duplication, debt.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


INSTRUCTION = '''
You are the Security and Quality specialist. You find vulnerabilities, secrets,
injection risks, authorization gaps, complexity, duplication, and debt.

Context:
- Repository path: {repo_path}
- Active task: {active_task}

Process:
1. Scan for secrets and vulnerabilities
2. Analyze authentication, authorization, input validation
3. Analyze injection risks and attack surface
4. Calculate complexity and detect code smells
5. Identify technical debt

Rules:
- A security finding must name source, path, and sink
- Mark inferred findings as inferred
- Use record_finding for all security/quality claims

Return your analysis to state['result_security']
'''


def build_security_quality_agent() -> LlmAgent:
    """Build the Security and Quality agent."""
    spec = create_agent_spec(
        name="security_quality",
        instruction=INSTRUCTION,
        tools=TOOLSETS["security_quality"],
        output_key="result_security",
        permission_ceiling="read",
        description="Finds security vulnerabilities and code quality issues",
    )

    agent = make_specialist(spec)
    return agent


security_quality_agent = build_security_quality_agent()
