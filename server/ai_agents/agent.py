from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent

from .agents.briefing import briefing_agent
from .agents.critic import make_critic
from .agents.fix import patch_agent, patch_repair, verifier
from .agents.impact import change_loader, impact_synthesizer, static_impact, test_mapper
from .agents.investigator import investigator
from .agents.scene_director import make_scene_director, make_result_scene_director
# Phase 2 agents
from .agents.repository_intelligence import repository_intelligence_agent
from .agents.code_understanding import code_understanding_agent
from .agents.relationship_intelligence import relationship_intelligence_agent
from .agents.data_flow import data_flow_intelligence_agent
from .agents.runtime import runtime_intelligence_agent
from .agents.debugging import debugging_intelligence_agent
from .agents.security_quality import security_quality_agent
from .agents.software_engineering import software_engineering_agent
from .agents.testing_verification import testing_verification_agent
from .agents.visualization import visualization_agent
from .agents.conversational import conversational_agent
from .agents.orchestrator import orchestrator_agent
from .callbacks import init_state, trim_history
from .config import MODEL
from .tools.control_tools import request_approval


def _with_scene(agent, key):
    return SequentialAgent(name=agent.name + '_pipeline', description=agent.description,
                           sub_agents=[agent, make_result_scene_director(agent.name + '_scene', key)])


data_flow_pipeline = _with_scene(data_flow_intelligence_agent, 'result_data_flow')
runtime_pipeline = _with_scene(runtime_intelligence_agent, 'result_runtime')
debugging_pipeline = _with_scene(debugging_intelligence_agent, 'result_debugging')
security_pipeline = _with_scene(security_quality_agent, 'result_security')
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

fix_pipeline = SequentialAgent(
    name='fix_pipeline',
    description=('Proposes a code change with a test in a sandbox, verifies it, and shows the result '
                 'as a reviewable diff. Use for add, fix or change requests.'),
    sub_agents=[patch_agent, verify_loop,
                make_critic('fix_critic', 'proposed_patch'),
                make_scene_director('fix_scene')],
)

briefing_pipeline = SequentialAgent(
    name='briefing_pipeline',
    description='Opening briefing for a project: what changed, what is risky, what is untested.',
    sub_agents=[briefing_agent, make_scene_director('briefing_scene')],
)

# Phase 2: New pipeline for vertical slice
phase2_specialists = ParallelAgent(
    name='phase2_specialists',
    description='Run Repository, Code Understanding, and Relationship in parallel',
    sub_agents=[repository_intelligence_agent, code_understanding_agent, relationship_intelligence_agent],
)

phase2_pipeline = SequentialAgent(
    name='phase2_pipeline',
    description='First vertical slice: explain function and show connections',
    sub_agents=[
        orchestrator_agent,
        phase2_specialists,
        make_critic('phase2_critic', 'findings'),
        visualization_agent,
        conversational_agent
    ],
)

ROOT_INSTRUCTION = '''
You are JARVIS, a voice-and-hands assistant that helps a developer understand and change code inside
a VR headset. Requests arrive as spoken text or as a pinch on a graph node.
Current selection (may be empty): {selection}

Route each request by delegating to exactly one sub-agent:
- phase2_pipeline: explain code and show connections (new vertical slice)
- investigate_pipeline: how existing code works, where something happens, what a selected node does.
- impact_pipeline: what breaks, what is affected, risk of changing or removing something, change review.
- fix_pipeline: add, fix or change code, propose a patch.
- briefing_pipeline: the user opens a project, asks for a status, or asks what is new.

For security, debugging, data flow, runtime, engineering or testing requests, delegate to exactly one of:
- security_quality_pipeline, debugging_intelligence_pipeline, data_flow_intelligence_pipeline,
  runtime_intelligence_pipeline, software_engineering_pipeline, testing_verification_pipeline.

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
    sub_agents=[phase2_pipeline, investigate_pipeline, impact_pipeline, fix_pipeline, briefing_pipeline,
                data_flow_pipeline, runtime_pipeline, debugging_pipeline,
                security_pipeline, engineering_pipeline, testing_pipeline],
    before_agent_callback=init_state,
    before_model_callback=trim_history,
)
