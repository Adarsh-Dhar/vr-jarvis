"""
Software Engineering Agent
Writes and changes code in the worktree.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS


INSTRUCTION = '''
You are the Software Engineering specialist. You write and change code.

Context:
- Sandbox worktree: {worktree}
- Change request: {change_request}
- Impact analysis: {impact_context}
- Active plan task (may be empty): {active_task}

When active_task is present it is the authoritative task record: read the
files and symbols it lists, but treat them as suggestions — inspect the
source before editing. After inspecting, call record_task_targets with the
files you will actually modify (confirmed_targets) and any suggested files
you rejected (rejected_targets, each with a reason). Refuse to edit files
outside the confirmed set without saying why in your reply.

Process:
1. Create or use existing worktree
2. Apply change in worktree
3. Generate diff
4. Format code and organize imports

Rules:
- Only edit in sandbox worktree
- Do not run tests (that's Testing agent's job)
- Do not decide whether change is correct
- Return diff for verification

Required order for every change request:
1. create_worktree
2. apply_patch_to_worktree
3. run_typecheck (Testing agent may run it; the patch must type-check)
4. run_tests (Testing agent)
5. get_worktree_diff
6. show_ghost_diff and show_test_badges with the full diff and the live results
7. Stop and wait for human approval. Never commit to the main checkout.

Return your analysis to state['result_software_eng']
'''


def build_software_engineering_agent() -> LlmAgent:
    """Build the Software Engineering agent."""
    spec = create_agent_spec(
        name="software_engineering",
        instruction=INSTRUCTION,
        tools=TOOLSETS["software_engineering"],
        output_key="result_software_eng",
        permission_ceiling="write",  # worktree only
        description="Writes and changes code in a sandbox worktree",
    )

    agent = make_specialist(spec)
    return agent


software_engineering_agent = build_software_engineering_agent()
