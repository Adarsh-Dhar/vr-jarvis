from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent

from .agents.critic import make_critic
from .agents.fix import code_reviewer, patch_agent, patch_repair, make_patch_review_repair, make_review_verifier, verifier
from .agents.impact import change_loader, impact_synthesizer, static_impact, test_mapper
from .agents.investigator import investigator
from .agents.navigator import make_navigator
from .agents.scene_director import make_scene_director, make_result_scene_director
# Phase 2 agents
from .agents.repository_intelligence import repository_intelligence_agent
from .agents.code_understanding import code_understanding_agent
from .agents.relationship_intelligence import relationship_intelligence_agent
from .agents.data_flow import data_flow_intelligence_agent, build_data_flow_agent
from .agents.software_engineering import software_engineering_agent
from .agents.testing_verification import testing_verification_agent
from .agents.visualization import visualization_agent
from .agents.conversational import conversational_agent
from .agents.architecture_design import architecture_design_agent
from .callbacks import init_state, trim_history
from .config import MODEL
from .tools.control_tools import request_approval


def _with_scene(agent, key):
    return SequentialAgent(name=agent.name + '_pipeline', description=agent.description,
                           sub_agents=[agent, make_result_scene_director(agent.name + '_scene', key)])


data_flow_pipeline = _with_scene(data_flow_intelligence_agent, 'result_data_flow')
engineering_pipeline = _with_scene(software_engineering_agent, 'result_software_eng')
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

verify_loop = LoopAgent(
    name='verify_loop',
    description='Tests the patch, and repairs it if tests fail, up to three rounds.',
    sub_agents=[verifier, patch_repair],
    max_iterations=3,
)

review_loop = LoopAgent(
    name='review_loop',
    description='Reviews the patch and repairs requested changes, up to two rounds.',
    sub_agents=[code_reviewer, make_patch_review_repair(), make_review_verifier()],
    max_iterations=2,
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

phase2_pipeline = SequentialAgent(
    name='phase2_pipeline',
    description='First vertical slice: explain function and show connections',
    sub_agents=[
        phase2_specialists,
        make_critic('phase2_critic', 'findings'),
        visualization_agent,
        conversational_agent
    ],
)

navigator_agent = make_navigator()

ROOT_INSTRUCTION = '''
You are JARVIS, a voice-and-hands assistant that helps a developer understand and change code inside
a VR headset. Requests arrive as spoken text or as a pinch on a graph node.
Current selection (may be empty): {selection}

Route each request by delegating to exactly one sub-agent:
- phase2_pipeline: explain code and show connections (new vertical slice)
- investigate_pipeline: how existing code works, where something happens, what a selected node does.
- impact_pipeline: what breaks, what is affected, risk of changing or removing something, change review.
- fix_pipeline: add, fix or change code, propose a patch. This is the ONLY route that changes code,
  including every request that carries an active plan task (WORK ON IT).
- architecture_design: turn an idea into requirements and a proposed component architecture (design mode requests).
- For error, stack trace or 'why does X fail' requests: run investigator, then pass its findings to relationship_intelligence and data_flow_intelligence via findings; call fix_pipeline only if the developer asks for a fix. The final answer must contain likely cause, evidence references, proposed correction and explanation.
- For broad 'how does this project work' questions, use phase2_pipeline.
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
    sub_agents=[phase2_pipeline, investigate_pipeline, impact_pipeline, fix_pipeline,
                data_flow_pipeline, testing_pipeline,   # engineering_pipeline removed: fix_pipeline is the only code-change route
                architecture_design_agent, navigator_agent],
    before_agent_callback=init_state,
    before_model_callback=trim_history,
)
