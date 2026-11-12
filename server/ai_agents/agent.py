from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent, BaseAgent

from .agents.critic import make_critic
from .agents.fix import (code_reviewer, patch_agent, patch_repair,
                         make_patch_repair, make_patch_review_repair,
                         make_review_verifier, verifier)
from .agents.impact import change_loader, impact_synthesizer, static_impact, test_mapper
from .agents.investigator import investigator, make_investigator
from .agents.navigator import make_navigator
from .agents.scene_director import make_scene_director, make_result_scene_director
# Phase 2 agents
from .agents.repository_intelligence import repository_intelligence_agent
from .agents.code_understanding import code_understanding_agent
from .agents.relationship_intelligence import (relationship_intelligence_agent,
                                               build_relationship_intelligence_agent)
from .agents.data_flow import data_flow_intelligence_agent, build_data_flow_agent
from .agents.testing_verification import testing_verification_agent
from .agents.visualization import visualization_agent
from .agents.conversational import conversational_agent
from .agents.architecture_design import architecture_design_agent
from .agents.implementation_planning import implementation_planning_agent
from .callbacks import init_state, trim_history
from .config import MODEL
from .tools.control_tools import request_approval


def _with_scene(agent, key):
    return SequentialAgent(name=agent.name + '_pipeline', description=agent.description,
                           sub_agents=[agent, make_result_scene_director(agent.name + '_scene', key)])


data_flow_pipeline = _with_scene(data_flow_intelligence_agent, 'result_data_flow')
testing_pipeline = _with_scene(testing_verification_agent, 'result_testing')

investigate_pipeline = SequentialAgent(
    name='investigate_pipeline',
    description=('Explains and investigates existing code: where something happens, how a flow works, '
                 'what a selected function does. Does not modify code.'),
    sub_agents=[investigator,
                make_critic('investigate_critic', 'answer_draft'),
                make_scene_director('investigate_scene')],
)

impact_fanout = ParallelAgent(
    name='impact_fanout',
    description='Runs static impact analysis and test mapping at the same time.',
    sub_agents=[static_impact, test_mapper],
)

impact_pipeline = SequentialAgent(
    name='impact_pipeline',
    description=('Analyses what a change or a selected node affects: dependents, risk, untested paths. '
                 'Use for what-breaks questions and change reviews.'),
    sub_agents=[change_loader, impact_fanout, impact_synthesizer,
                make_critic('impact_critic', 'impact_report'),
                make_scene_director('impact_scene')],
)

# Composed debugging workflow: the investigator finds where the failure lives,
# then relationship and data-flow intelligence analyse it in parallel, and the
# critic synthesizes likely cause, evidence and a proposed correction. This is
# the ONLY route for error/stack-trace debugging; it never modifies code —
# fix_pipeline is invoked separately and only when the developer asks for a fix.
# Fresh instances: ADK agents cannot have two parents, and the module-level
# specialists already belong to phase2/data_flow pipelines.
debug_analysis = ParallelAgent(
    name='debug_analysis',
    description='Relationship intelligence and data-flow intelligence analyse the investigation in parallel.',
    sub_agents=[build_relationship_intelligence_agent(), build_data_flow_agent()],
)

debug_pipeline = SequentialAgent(
    name='debug_pipeline',
    description=('Debugs an error, stack trace or failure: investigates the code, analyses relationships '
                 'and data flow, then reports likely cause, evidence, a proposed correction and an '
                 'explanation. Read-only; does not modify code.'),
    sub_agents=[make_investigator(), debug_analysis,
                make_critic('debug_critic', 'findings'),
                make_scene_director('debug_scene')],
)

verify_loop = LoopAgent(
    name='verify_loop',
    description='Tests the patch, and repairs it if tests fail, up to three rounds.',
    sub_agents=[verifier, patch_repair],
    max_iterations=3,
)

class ReviewVerifyRepairGate(BaseAgent):
    """Deterministic gate inside review_loop.

    The loop's own repair+verifier pair only runs once per iteration; when the
    verifier leaves failing test evidence behind, this gate re-runs repair and
    verification (bounded by max_repairs) BEFORE the independent reviewer sees
    the diff. A nested LoopAgent was rejected for this role: an escalate event
    from a sub-agent inside a nested loop can propagate to the outer loop and
    end review_loop before the review runs. This gate never escalates — it
    only re-verifies, and exit_loop remains the reviewer's alone."""

    max_repairs: int = 2

    async def _run_async_impl(self, ctx):
        from .tools.exec_tools import verification_passed
        for _ in range(self.max_repairs):
            if verification_passed(ctx.session.state):
                return
            for agent in self.sub_agents:
                async for event in agent.run_async(ctx):
                    yield event


# Review-repair-verify-gate-review order matters: each iteration repairs the
# findings from the PREVIOUS review, re-runs tests/typecheck on the corrected
# patch, and the gate re-repairs until the recorded evidence passes (bounded).
# Only then does the independent reviewer see the diff. The reviewer owns
# exit_loop — and exit_loop itself refuses while verification has not passed —
# so the loop can only end on an approval of a verified patch.
review_loop = LoopAgent(
    name='review_loop',
    description='Repairs review findings, re-verifies until tests pass, and re-reviews the final patch, up to three rounds.',
    sub_agents=[make_patch_review_repair(), make_review_verifier(),
                ReviewVerifyRepairGate(
                    name='review_verify_gate',
                    sub_agents=[make_patch_repair(),
                                make_review_verifier('gate_review_verifier_agent')]),
                code_reviewer],
    max_iterations=3,
)

fix_pipeline = SequentialAgent(
    name='fix_pipeline',
    description=('Proposes a code change with a test in a sandbox, verifies it, and shows the result '
                 'as a reviewable diff. Use for add, fix or change requests.'),
    sub_agents=[patch_agent, verify_loop, review_loop,
                make_critic('fix_critic', 'proposed_patch'),
                make_scene_director('fix_scene')],
)

# Phase 2: New pipeline for vertical slice
phase2_specialists = ParallelAgent(
    name='phase2_specialists',
    description='Run Repository, Code Understanding, and Relationship in parallel',
    sub_agents=[repository_intelligence_agent, code_understanding_agent, relationship_intelligence_agent, build_data_flow_agent()],
)

# Single project-understanding role: one named pipeline that routes to the
# four specialists (repository, code, relationship, data-flow) plus critic,
# visualization and conversational synthesis.
project_understanding_agent = SequentialAgent(
    name='project_understanding_agent',
    description=('Project understanding: explains the repository, code, '
                 'relationships and data flow. Runs the repository, code '
                 'understanding, relationship and data-flow specialists, '
                 'then critiques, visualizes and answers.'),
    sub_agents=[
        phase2_specialists,
        make_critic('project_understanding_critic', 'findings'),
        visualization_agent,
        conversational_agent
    ],
)

navigator_agent = make_navigator()

ROOT_INSTRUCTION = '''
You are JARVIS, a voice-and-hands assistant that helps a developer understand and change code inside
a VR headset. Requests arrive as spoken text or as a pinch on a graph node.
Current selection (may be empty): {selection}

Route each request by delegating to the ONE sub-agent or pipeline that owns it:
- project_understanding_agent: explain the repository, code, relationships and data flow
- investigate_pipeline: how existing code works, where something happens, what a selected node does.
- impact_pipeline: what breaks, what is affected, risk of changing or removing something, change review.
- fix_pipeline: add, fix or change code, propose a patch. This is the ONLY route that changes code,
  including every request that carries an active plan task (WORK ON IT).
- architecture_design: turn an idea into requirements and a proposed component architecture (design mode requests).
- implementation_planning: produce or refine the implementation plan for an APPROVED architecture.
- debug_pipeline: every error, stack trace, exception or 'why does X fail' request. It runs the
  investigator, then relationship and data-flow intelligence in parallel, and answers with likely
  cause, evidence references, a proposed correction and an explanation. Call fix_pipeline afterwards
  ONLY if the developer asks you to apply a fix — debugging itself never modifies code.
- For broad 'how does this project work' questions, use project_understanding_agent.
- navigator: open or switch a repository, show a folder or file, change tab, or move, resize, hide, pin, zoom or recenter anything in the workspace.

For data flow or testing requests, delegate to exactly one of:
- data_flow_intelligence_pipeline, testing_verification_pipeline.

Rules:
- Do not answer code questions yourself. You have no code tools.
- Before any step that would change code outside the sandbox, call request_approval and wait.
- Spoken replies are at most two sentences.
- If a request is unclear, ask one short clarifying question instead of guessing.
'''

root_agent = LlmAgent(
    name='jarvis_orchestrator',
    model=MODEL,
    description='Voice-and hands assistant for understanding and changing code in VR.',
    instruction=ROOT_INSTRUCTION,
    tools=[request_approval],
    sub_agents=[project_understanding_agent, investigate_pipeline, impact_pipeline, fix_pipeline,
                debug_pipeline,
                data_flow_pipeline, testing_pipeline,   # engineering_pipeline removed: fix_pipeline is the only code-change route
                architecture_design_agent, implementation_planning_agent, navigator_agent],
    before_agent_callback=init_state,
    before_model_callback=trim_history,
)
