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
        task_type = "debugging"
        required_agents = ["debugging_intelligence", "runtime_intelligence"]
    elif "test" in request_lower:
        task_type = "testing"
        required_agents = ["testing_verification"]
    elif "security" in request_lower or "vulnerability" in request_lower:
        task_type = "security"
        required_agents = ["security_quality"]
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
    return {
        'status': 'ok',
        'plan': [],
        'note': 'Investigation planning to be implemented'
    }


@safe
def decompose_task(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Decompose a task into subtasks."""
    return {
        'status': 'ok',
        'subtasks': [],
        'note': 'Task decomposition to be implemented'
    }


@safe
def select_agents(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Select agents for a task."""
    return {
        'status': 'ok',
        'agents': [],
        'note': 'Agent selection to be implemented'
    }


@safe
def delegate_task(
    agent: str,
    task: str,
    tool_context: ToolContext
) -> dict:
    """Delegate a task to an agent."""
    return {
        'status': 'ok',
        'delegated': False,
        'note': 'Task delegation to be implemented'
    }


@safe
def run_agents_parallel(
    agents: list,
    task: str,
    tool_context: ToolContext
) -> dict:
    """Run multiple agents in parallel."""
    return {
        'status': 'ok',
        'results': [],
        'note': 'Parallel execution to be implemented'
    }


@safe
def run_agents_sequentially(
    agents: list,
    task: str,
    tool_context: ToolContext
) -> dict:
    """Run multiple agents sequentially."""
    return {
        'status': 'ok',
        'results': [],
        'note': 'Sequential execution to be implemented'
    }


@safe
def wait_for_agent(
    agent: str,
    tool_context: ToolContext
) -> dict:
    """Wait for an agent to complete."""
    return {
        'status': 'ok',
        'completed': False,
        'note': 'Agent waiting to be implemented'
    }


@safe
def get_agent_status(
    agent: str,
    tool_context: ToolContext
) -> dict:
    """Get the status of an agent."""
    return {
        'status': 'ok',
        'agent_status': 'idle',
        'note': 'Agent status tracking to be implemented'
    }


@safe
def cancel_agent_task(
    agent: str,
    tool_context: ToolContext
) -> dict:
    """Cancel an agent's task."""
    return {
        'status': 'ok',
        'cancelled': False,
        'note': 'Task cancellation to be implemented'
    }


@safe
def retry_agent_task(
    agent: str,
    tool_context: ToolContext
) -> dict:
    """Retry an agent's task."""
    return {
        'status': 'ok',
        'retried': False,
        'note': 'Task retry to be implemented'
    }


@safe
def merge_agent_results(
    results: list,
    tool_context: ToolContext
) -> dict:
    """Merge results from multiple agents."""
    return {
        'status': 'ok',
        'merged': [],
        'note': 'Result merging to be implemented'
    }


@safe
def resolve_conflicting_findings(
    findings: list,
    tool_context: ToolContext
) -> dict:
    """Resolve conflicting findings from agents."""
    return {
        'status': 'ok',
        'resolved': [],
        'note': 'Conflict resolution to be implemented'
    }


@safe
def request_more_evidence(
    agent: str,
    tool_context: ToolContext
) -> dict:
    """Request more evidence from an agent."""
    return {
        'status': 'ok',
        'evidence': [],
        'note': 'Evidence request to be implemented'
    }


@safe
def check_task_completion(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Check if a task is complete."""
    return {
        'status': 'ok',
        'complete': False,
        'note': 'Completion checking to be implemented'
    }


@safe
def request_user_approval(
    action: str,
    tool_context: ToolContext
) -> dict:
    """Request user approval for an action."""
    return {
        'status': 'ok',
        'approved': False,
        'note': 'User approval to be implemented'
    }


@safe
def manage_task_priority(
    task: str,
    priority: str,
    tool_context: ToolContext
) -> dict:
    """Manage task priority."""
    return {
        'status': 'ok',
        'note': 'Priority management to be implemented'
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
def invoke_runtime_intelligence(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Runtime Intelligence agent."""
    from ..agents.registry import get_agent
    
    agent = get_agent("runtime_intelligence")
    if not agent:
        return {
            'status': 'error',
            'error': 'Runtime Intelligence agent not found'
        }
    
    state = tool_context.state
    state['runtime_task'] = task
    
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'runtime_intelligence',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }


@safe
def invoke_debugging_intelligence(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Debugging Intelligence agent."""
    from ..agents.registry import get_agent
    
    agent = get_agent("debugging_intelligence")
    if not agent:
        return {
            'status': 'error',
            'error': 'Debugging Intelligence agent not found'
        }
    
    state = tool_context.state
    state['debugging_task'] = task
    
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'debugging_intelligence',
        'note': 'Task queued for agent invocation through main runner pipeline'
    }


@safe
def invoke_security_quality(
    task: str,
    tool_context: ToolContext
) -> dict:
    """Invoke the Security and Quality agent."""
    from ..agents.registry import get_agent
    
    agent = get_agent("security_quality")
    if not agent:
        return {
            'status': 'error',
            'error': 'Security and Quality agent not found'
        }
    
    state = tool_context.state
    state['security_task'] = task
    
    return {
        'status': 'task_queued',
        'task': task,
        'agent': 'security_quality',
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
