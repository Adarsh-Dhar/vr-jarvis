"""
Testing and Verification Agent
Finds tests, runs them, measures coverage, verifies changes.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


INSTRUCTION = '''
You are the Testing and Verification specialist. You find tests, run them,
measure coverage, and verify changes.

Context:
- Sandbox worktree: {worktree}
- Proposed patch: {proposed_patch}
- Active task: {active_task}

Process:
1. Discover tests and map to functions
2. Run tests in worktree
3. Measure coverage
4. Verify compilation, lint, types, security
5. Compare before and after

Rules:
- Cannot edit files
- Label results as live, cached, or simulated
- Report 'passed' only when check really ran
- Use record_finding for all verification claims

Return your analysis to state['result_testing']
'''


def build_testing_verification_agent() -> LlmAgent:
    """Build the Testing and Verification agent."""
    spec = create_agent_spec(
        name="testing_verification",
        instruction=INSTRUCTION,
        tools=TOOLSETS["testing_verification"],
        output_key="result_testing",
        permission_ceiling="execute",  # sandbox only
        description="Finds tests, runs them, and verifies changes",
    )

    agent = make_specialist(spec)
    return agent


testing_verification_agent = build_testing_verification_agent()
