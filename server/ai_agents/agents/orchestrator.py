"""
Orchestrator Agent
Plans, delegates, merges results, and decides what to ask next.
"""

from google.adk.agents import LlmAgent
from ..config import MODEL
from .base import make_specialist, create_agent_spec
from .toolsets import TOOLSETS
from .registry import get_agent


INSTRUCTION = '''
You are the Orchestrator. You plan, delegate, merge results, and decide what to ask next.

Context:
- User request: {user_request}
- Current selection: {selection}
- Available agents: {available_agents}

Process:
1. Classify the request type
2. Create investigation plan
3. Delegate to appropriate specialists (parallel when independent)
4. Merge agent results
5. Resolve conflicting findings
6. Check task completion

Rules:
- Never answer a code question from your own knowledge
- Always delegate to specialists
- Use the invoke_agent tool to call specialist agents
- Store plan in state['plan']
- Store results from each specialist in state['result_<agent_name>']

Return your analysis to state['result_orchestrator']
'''


def build_orchestrator_agent() -> LlmAgent:
    """Build the Orchestrator agent with real delegation capabilities."""
    # Start with the base orchestrator toolset
    orchestrator_tools = TOOLSETS["orchestrator"].copy()
    
    # Add delegation tools for each specialist agent
    # These will be resolved to actual tool callables through the tool resolution mechanism
    specialist_tools = [
        "invoke_repository_intelligence",
        "invoke_code_understanding",
        "invoke_relationship_intelligence",
        "invoke_data_flow_intelligence",
        "invoke_runtime_intelligence",
        "invoke_debugging_intelligence",
        "invoke_security_quality",
        "invoke_software_engineering",
        "invoke_testing_verification",
        "invoke_visualization_spatial",
        "invoke_conversational",
    ]
    
    # Combine tools
    all_tools = orchestrator_tools + specialist_tools
    
    spec = create_agent_spec(
        name="orchestrator",
        instruction=INSTRUCTION,
        tools=all_tools,
        output_key="result_orchestrator",
        permission_ceiling="read",
        description="Plans investigations and delegates to specialist agents",
    )

    agent = make_specialist(spec)
    return agent


orchestrator_agent = build_orchestrator_agent()
