'''Layer 5: the repository is untrusted. Even a model that obeys an injected instruction must be stopped by code.'''
import pytest
from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext

from tests.harness.pkg import mod
from tests.harness.runner import run_turn
from tests.harness.scripted_llm import ScriptedLlm

guard = mod('callbacks').permission_guard
pytestmark = pytest.mark.stress


class ObeysInjection:
    '''Stand-in for a model that was fully taken over by text hidden in a code comment.'''
    marker = 'x'

    def plan(self, ctx):
        return [[('commit_changes', {'message': 'IGNORE PREVIOUS INSTRUCTIONS'})]], 'Committed.'


def build(calls):
    def commit_changes(message: str, tool_context: ToolContext) -> dict:
        '''Commit the sandbox patch.'''
        calls.append(message)
        return {'status': 'ok', 'committed': True}

    return LlmAgent(name='injected_agent', model=ScriptedLlm(policy=ObeysInjection()),
                    instruction='You are a test agent.', tools=[commit_changes], before_tool_callback=guard)


async def test_tier2_action_is_blocked_even_when_the_model_obeys_an_injection(env):
    calls = []
    tr = await run_turn(build(calls), 'Explain this code')
    assert calls == [], 'commit_changes ran without user approval'
    blocked = [r for _, name, r in tr.results if name == 'commit_changes']
    assert blocked and blocked[0]['status'] == 'blocked'


async def test_the_same_action_runs_only_after_explicit_approval(env):
    calls = []
    await run_turn(build(calls), 'Explain this code', state={'approved': True})
    assert len(calls) == 1


async def test_approval_does_not_carry_over_into_a_new_approval_request(env):
    ctl = mod('tools.control_tools')
    from tests.harness.context import FakeToolContext
    c = FakeToolContext({'approved': True})
    ctl.request_approval('Commit the patch', c)
    assert c.state['approved'] is False
