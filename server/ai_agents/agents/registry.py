"""
Agent Registry
Central registry for all agents, used by server endpoints.
"""

from typing import Dict, List, Optional, Any
from google.adk.agents import Agent


# Global agent registry
AGENTS: Dict[str, Agent] = {}

# Agent configuration for permissions and budgets (stored separately from agents)
AGENT_CONFIG: Dict[str, Dict[str, Any]] = {}


def register_agent(name: str, agent: Agent) -> None:
    """
    Register an agent in the global registry.

    Args:
        name: Agent name
        agent: Agent instance
    """
    AGENTS[name] = agent


def get_agent(name: str) -> Optional[Agent]:
    """
    Get an agent by name.

    Args:
        name: Agent name

    Returns:
        Agent instance or None if not found
    """
    return AGENTS.get(name)


def list_agents() -> List[str]:
    """
    List all registered agent names.

    Returns:
        List of agent names
    """
    return list(AGENTS.keys())


def get_agent_status(name: str) -> Dict[str, Any]:
    """
    Get agent status for server endpoints.

    Args:
        name: Agent name

    Returns:
        Status dict with agent metadata
    """
    agent = get_agent(name)
    if agent is None:
        return {
            "name": name,
            "status": "not_found",
            "error": f"Agent {name} not registered"
        }

    return {
        "name": agent.name,
        "model": getattr(agent, "model", "unknown"),
        "description": getattr(agent, "description", ""),
        "status": "registered",
        "tool_count": len(getattr(agent, "tools", [])),
    }


def get_all_agent_statuses() -> Dict[str, Dict[str, Any]]:
    """
    Get status for all registered agents.

    Returns:
        Dict mapping agent names to their status
    """
    return {name: get_agent_status(name) for name in list_agents()}


def unregister_agent(name: str) -> bool:
    """
    Unregister an agent.

    Args:
        name: Agent name

    Returns:
        True if agent was removed, False if not found
    """
    if name in AGENTS:
        del AGENTS[name]
        return True
    return False


# Auto-register all agents on import
def _register_all_agents():
    """Register all agents when this module is imported."""
    try:
        from .repository_intelligence import repository_intelligence_agent
        register_agent("repository_intelligence", repository_intelligence_agent)
    except ImportError:
        pass

    try:
        from .code_understanding import code_understanding_agent
        register_agent("code_understanding", code_understanding_agent)
    except ImportError:
        pass

    try:
        from .relationship_intelligence import relationship_intelligence_agent
        register_agent("relationship_intelligence", relationship_intelligence_agent)
    except ImportError:
        pass

    try:
        from .data_flow import data_flow_intelligence_agent
        register_agent("data_flow", data_flow_intelligence_agent)
    except ImportError:
        pass

    try:
        from .runtime import runtime_intelligence_agent
        register_agent("runtime_intelligence", runtime_intelligence_agent)
    except ImportError:
        pass

    try:
        from .debugging import debugging_intelligence_agent
        register_agent("debugging_intelligence", debugging_intelligence_agent)
    except ImportError:
        pass

    try:
        from .security_quality import security_quality_agent
        register_agent("security_quality", security_quality_agent)
    except ImportError:
        pass

    try:
        from .software_engineering import software_engineering_agent
        register_agent("software_engineering", software_engineering_agent)
    except ImportError:
        pass

    try:
        from .testing_verification import testing_verification_agent
        register_agent("testing_verification", testing_verification_agent)
    except ImportError:
        pass

    try:
        from .visualization import visualization_agent
        register_agent("visualization", visualization_agent)
    except ImportError:
        pass

    try:
        from .conversational import conversational_agent
        register_agent("conversational", conversational_agent)
    except ImportError:
        pass

    try:
        from .orchestrator import orchestrator_agent
        register_agent("orchestrator", orchestrator_agent)
    except ImportError:
        pass


# Register all agents on module load
_register_all_agents()
