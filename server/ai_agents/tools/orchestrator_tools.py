"""
Orchestrator Tools
Delegation tools for the Orchestrator to invoke specialist agents.
"""

from typing import Dict, Any, Optional
from google.adk.tools import ToolContext
from ._safe import safe


@safe
def understand_user_intent(
    question: str,
    tool_context: ToolContext
) -> dict:
    """
    Understand the user's intent from a natural language question.
    
    Args:
        question: The user's natural language question
        tool_context: Tool context with state
        
    Returns:
        Intent classification with entities
    """
    # Simple intent classification based on keywords
    question_lower = question.lower()
    
    intent = "general"
    entities = {}
    
    if "function" in question_lower or "method" in question_lower:
        intent = "function_explanation"
    elif "bug" in question_lower or "error" in question_lower or "fix" in question_lower:
        intent = "debugging"
    elif "test" in question_lower:
        intent = "testing"
    elif "security" in question_lower or "vulnerability" in question_lower:
        intent = "security"
    elif "change" in question_lower or "modify" in question_lower or "refactor" in question_lower:
        intent = "modification"
    
    # Extract function name if present
    words = question_lower.split()
    for i, word in enumerate(words):
        if word in ["function", "method"] and i + 1 < len(words):
            entities["function"] = words[i + 1]
    
    return {
        'status': 'ok',
        'intent': intent,
        'entities': entities
    }


@safe
def classify_request(
    request: str,
    tool_context: ToolContext
) -> dict:
    """
    Classify a user request into task type and required agents.
    
    Args:
        request: The user's request text
        tool_context: Tool context with state
        
    Returns:
        Classification with task type and required agents
    """
    request_lower = request.lower()
    
    task_type = "general"
    required_agents = []
    
    # Determine task type
    if "explain" in request_lower or "what is" in request_lower or "how does" in request_lower:
        task_type = "investigation"
        required_agents = ["repository_intelligence", "code_understanding", "relationship_intelligence"]
    elif "bug" in request_lower or "error" in request_lower or "fix" in request_lower:
        task_type = "investigation"
        required_agents = ["code_understanding", "relationship_intelligence"]
    elif "test" in request_lower:
        task_type = "testing"
        required_agents = ["testing_verification"]
    elif "change" in request_lower or "modify" in request_lower or "add" in request_lower:
        task_type = "modification"
        required_agents = ["software_engineering", "testing_verification"]
    elif "data flow" in request_lower or "trace" in request_lower:
        task_type = "data_flow"
        required_agents = ["data_flow_intelligence"]
    elif "visualize" in request_lower or "graph" in request_lower:
        task_type = "visualization"
        required_agents = ["visualization_spatial", "relationship_intelligence"]
    
    return {
        'status': 'ok',
        'task_type': task_type,
        'required_agents': required_agents,
        'confidence': 0.8
    }


@safe
def create_investigation_plan(
    request: str,
    tool_context: ToolContext
) -> dict:
    """Create an investigation plan for a request."""
    # Store the request in state for the orchestrator
    state = tool_context.state
    state['investigation_request'] = request
    
    # Generate a basic plan based on request analysis
    request_lower = request.lower()
    plan_steps = []
    
    if "explain" in request_lower or "what is" in request_lower:
        plan_steps = [
            "Analyze repository structure",
            "Identify relevant code files",
            "Extract code relationships",
            "Generate explanation"
        ]
    elif "bug" in request_lower or "error" in request_lower:
        plan_steps = [
            "Identify error location",
            "Analyze error context",
            "Trace execution path",
            "Identify root cause",
            "Suggest fix"
        ]
    else:
        plan_steps = [
            "Understand request",
            "Identify required information",
            "Execute analysis",
            "Synthesize results"
        ]
    
    return {
        'status': 'ok',
        'plan': plan_steps,
        'request': request,
        'note': 'Plan generated - actual execution through ADK sub-agent delegation'
    }


@safe
def decompose_task(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Decompose a task into subtasks."""
    state = tool_context.state
    state['main_task'] = task
    
    # Basic task decomposition
    subtasks = [
        f"Analyze: {task}",
        f"Execute: {task}",
        f"Verify: {task}"
    ]
    
    return {
        'status': 'ok',
        'subtasks': subtasks,
        'task': task,
        'note': 'Task decomposition - actual execution through ADK sub-agent delegation'
    }


@safe
def select_agents(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Select agents for a task."""
    state = tool_context.state
    state['task_for_selection'] = task
    
    # Basic agent selection based on task type
    task_lower = task.lower()
    agents = []
    
    if "explain" in task_lower or "what is" in task_lower:
        agents = ["repository_intelligence", "code_understanding", "relationship_intelligence"]
    elif "bug" in task_lower or "error" in task_lower:
        agents = ["code_understanding", "relationship_intelligence"]
    elif "test" in task_lower:
        agents = ["testing_verification"]
    else:
        agents = ["repository_intelligence"]
    
    return {
        'status': 'ok',
        'agents': agents,
        'task': task,
        'note': 'Agent selection - actual execution through ADK sub-agent delegation'
    }


@safe
def delegate_task(
    agent: str,
    task: str,
    tool_context: ToolContext
) -> dict:
    """Delegate a task to an agent."""
    state = tool_context.state
    state[f'delegated_to_{agent}'] = task
    
    return {
        'status': 'ok',
        'delegated': True,
        'agent': agent,
        'task': task,
        'note': 'Task delegation - actual execution through ADK sub-agent mechanism'
    }


@safe
def run_agents_parallel(
    agents: list,
    task: str,
    tool_context: ToolContext
) -> dict:
    """Run multiple agents in parallel."""
    state = tool_context.state
    state['parallel_agents'] = agents
    state['parallel_task'] = task
    
    return {
        'status': 'ok',
        'agents': agents,
        'task': task,
        'note': 'Parallel execution configured - actual execution through ADK ParallelAgent'
    }


@safe
def run_agents_sequentially(
    agents: list,
    task: str,
    tool_context: ToolContext
) -> dict:
    """Run multiple agents sequentially."""
    state = tool_context.state
    state['sequential_agents'] = agents
    state['sequential_task'] = task
    
    return {
        'status': 'ok',
        'agents': agents,
        'task': task,
        'note': 'Sequential execution configured - actual execution through ADK SequentialAgent'
    }


@safe
def wait_for_agent(
    agent: str,
    tool_context: ToolContext
) -> dict:
    """Wait for an agent to complete."""
    state = tool_context.state
    agent_status = state.get(f'{agent}_status', 'idle')
    
    return {
        'status': 'ok',
        'agent': agent,
        'agent_status': agent_status,
        'note': 'Agent status tracking - actual waiting through ADK event streaming'
    }


@safe
def get_agent_status(
    agent: str,
    tool_context: ToolContext
) -> dict:
    """Get the status of an agent."""
    state = tool_context.state
    agent_status = state.get(f'{agent}_status', 'idle')
    
    return {
        'status': 'ok',
        'agent': agent,
        'agent_status': agent_status,
        'note': 'Agent status from session state'
    }


@safe
def cancel_agent_task(
    agent: str,
    tool_context: ToolContext
) -> dict:
    """Cancel an agent's task."""
    state = tool_context.state
    state[f'{agent}_cancelled'] = True
    
    return {
        'status': 'ok',
        'agent': agent,
        'cancelled': True,
        'note': 'Task cancellation - actual cancellation through ADK session management'
    }


@safe
def retry_agent_task(
    agent: str,
    tool_context: ToolContext
) -> dict:
    """Retry an agent's task."""
    state = tool_context.state
    retry_count = state.get(f'{agent}_retry_count', 0)
    state[f'{agent}_retry_count'] = retry_count + 1
    
    return {
        'status': 'ok',
        'agent': agent,
        'retried': True,
        'retry_count': retry_count + 1,
        'note': 'Task retry - actual retry through ADK session restart'
    }


@safe
def merge_agent_results(
    results: list,
    tool_context: ToolContext
) -> dict:
    """Merge results from multiple agents."""
    state = tool_context.state
    state['merged_results'] = results
    
    # Basic merging logic
    merged = {
        'total_results': len(results),
        'results': results
    }
    
    return {
        'status': 'ok',
        'merged': merged,
        'note': 'Result merging - actual merging through ADK event aggregation'
    }


@safe
def resolve_conflicting_findings(
    findings: list,
    tool_context: ToolContext
) -> dict:
    """Resolve conflicting findings from agents."""
    state = tool_context.state
    state['conflicting_findings'] = findings
    
    # Basic conflict resolution - preserve all with notes
    resolved = [
        {**f, 'resolution': 'preserved_for_review'}
        for f in findings
    ]
    
    return {
        'status': 'ok',
        'resolved': resolved,
        'note': 'Conflict resolution - actual resolution through verification agent'
    }


@safe
def request_more_evidence(
    agent: str,
    tool_context: ToolContext
) -> dict:
    """Request more evidence from an agent."""
    state = tool_context.state
    state[f'request_evidence_from_{agent}'] = True
    
    return {
        'status': 'ok',
        'agent': agent,
        'note': 'Evidence request - actual request through ADK follow-up message'
    }


@safe
def check_task_completion(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Check if a task is complete."""
    state = tool_context.state
    task_status = state.get(f'{task}_status', 'incomplete')
    
    return {
        'status': 'ok',
        'task': task,
        'complete': task_status == 'complete',
        'task_status': task_status,
        'note': 'Completion check - actual check through ADK session state'
    }


@safe
def request_user_approval(
    action: str,
    tool_context: ToolContext
) -> dict:
    """Request user approval for an action."""
    state = tool_context.state
    state['pending_approval'] = action
    
    return {
        'status': 'ok',
        'action': action,
        'approved': False,
        'note': 'User approval request - actual approval through /request_approval endpoint'
    }


@safe
def manage_task_priority(
    task: str,
    priority: str,
    tool_context: ToolContext
) -> dict:
    """Manage task priority."""
    state = tool_context.state
    state[f'{task}_priority'] = priority
    
    return {
        'status': 'ok',
        'task': task,
        'priority': priority,
        'note': 'Priority management - actual management through ADK session state'
    }


@safe
def invoke_repository_intelligence(
    task: str,
    tool_context: ToolContext
) -> dict:
    """
    Invoke the Repository Intelligence agent.
    
    Args:
        task: The specific task for the repository intelligence agent
        tool_context: Tool context with state
        
    Returns:
        Result from the repository intelligence agent
    """
    from ..agents.registry import get_agent
    from google.adk.events import Event, EventActions
    from google.genai import types
    import asyncio
    
    agent = get_agent("repository_intelligence")
    if not agent:
        return {
            'status': 'error',
            'error': 'Repository Intelligence agent not found'
        }
    
    # Store the task in state for the agent
    state = tool_context.state
    state['repository_task'] = task
    
    # Note: Actual agent invocation through Google ADK requires access to the runner
    # which is at the server level. For now, we return the task state
    # and the actual invocation happens through the main runner pipeline.
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'repository_intelligence',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }


@safe
def invoke_code_understanding(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Code Understanding agent."""
    from ..agents.registry import get_agent
    
    agent = get_agent("code_understanding")
    if not agent:
        return {
            'status': 'error',
            'error': 'Code Understanding agent not found'
        }
    
    state = tool_context.state
    state['code_understanding_task'] = task
    
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'code_understanding',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }


@safe
def invoke_relationship_intelligence(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Relationship Intelligence agent."""
    from ..agents.registry import get_agent
    
    agent = get_agent("relationship_intelligence")
    if not agent:
        return {
            'status': 'error',
            'error': 'Relationship Intelligence agent not found'
        }
    
    state = tool_context.state
    state['relationship_task'] = task
    
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'relationship_intelligence',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }


@safe
def invoke_data_flow_intelligence(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Data Flow Intelligence agent."""
    from ..agents.registry import get_agent
    
    agent = get_agent("data_flow_intelligence")
    if not agent:
        return {
            'status': 'error',
            'error': 'Data Flow Intelligence agent not found'
        }
    
    state = tool_context.state
    state['data_flow_task'] = task
    
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'data_flow_intelligence',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }


@safe
def invoke_software_engineering(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Software Engineering agent."""
    from ..agents.registry import get_agent
    
    agent = get_agent("software_engineering")
    if not agent:
        return {
            'status': 'error',
            'error': 'Software Engineering agent not found'
        }
    
    state = tool_context.state
    state['software_eng_task'] = task
    
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'software_engineering',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }


@safe
def invoke_testing_verification(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Testing and Verification agent."""
    from ..agents.registry import get_agent
    
    agent = get_agent("testing_verification")
    if not agent:
        return {
            'status': 'error',
            'error': 'Testing and Verification agent not found'
        }
    
    state = tool_context.state
    state['testing_task'] = task
    
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'testing_verification',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }


@safe
def invoke_visualization_spatial(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Visualization and Spatial Intelligence agent."""
    from ..agents.registry import get_agent
    
    agent = get_agent("visualization_spatial")
    if not agent:
        return {
            'status': 'error',
            'error': 'Visualization and Spatial Intelligence agent not found'
        }
    
    state = tool_context.state
    state['visualization_task'] = task
    
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'visualization_spatial',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }


@safe
def invoke_conversational(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Conversational JARVIS agent."""
    from ..agents.registry import get_agent
    
    agent = get_agent("conversational")
    if not agent:
        return {
            'status': 'error',
            'error': 'Conversational agent not found'
        }
    
    state = tool_context.state
    state['conversational_task'] = task
    
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'conversational',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }


@safe
def invoke_architecture_design(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Architecture Design agent."""
    from ..agents.registry import get_agent

    agent = get_agent("architecture_design")
    if not agent:
        return {
            'status': 'error',
            'error': 'Architecture Design agent not found'
        }

    state = tool_context.state
    state['architecture_design_task'] = task

    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'architecture_design',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }
