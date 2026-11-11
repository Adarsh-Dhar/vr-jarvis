"""
Agent Registry
Central registry for all agents, used by server endpoints.
"""

from typing import Dict, List, Optional, Any
from google.adk.agents import Agent
import logging

logger = logging.getLogger(__name__)


# Global agent registry
AGENTS: Dict[str, Agent] = {}

# Agent configuration for permissions and budgets (stored separately from agents)
AGENT_CONFIG: Dict[str, Dict[str, Any]] = {}

# Expected agents - must all be registered for the system to be valid
EXPECTED_AGENTS = [
    "orchestrator",
    "conversational",
    "repository_intelligence",
    "code_understanding",
    "relationship_intelligence",
    "data_flow_intelligence",
    "software_engineering",
    "testing_verification",
    "visualization_spatial",
    "architecture_design",
]

# Default tool budgets and permission ceilings for each agent
DEFAULT_AGENT_CONFIG = {
    "orchestrator": {"tool_budget": 30, "permission_ceiling": "read"},
    "conversational": {"tool_budget": 20, "permission_ceiling": "read"},
    "repository_intelligence": {"tool_budget": 25, "permission_ceiling": "read"},
    "code_understanding": {"tool_budget": 25, "permission_ceiling": "read"},
    "relationship_intelligence": {"tool_budget": 25, "permission_ceiling": "read"},
    "data_flow_intelligence": {"tool_budget": 25, "permission_ceiling": "read"},
    "software_engineering": {"tool_budget": 20, "permission_ceiling": "write"},
    "testing_verification": {"tool_budget": 25, "permission_ceiling": "execute"},
    "visualization_spatial": {"tool_budget": 20, "permission_ceiling": "read"},
    "architecture_design": {"tool_budget": 20, "permission_ceiling": "read"},
    # fix_pipeline agents; patch_agent reads several files before it edits
    "patch_agent": {"tool_budget": 40, "permission_ceiling": "write"},
    "patch_repair_agent": {"tool_budget": 20, "permission_ceiling": "write"},
    "verifier_agent": {"tool_budget": 12, "permission_ceiling": "execute"},
}


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


def initialize_agents() -> None:
    """
    Explicitly initialize and register all agents.
    
    This function:
    - Imports all agent factories through a controlled initialization
    - Instantiates each agent exactly once per application lifecycle
    - Registers every agent under a unique identifier
    - Fails loudly if a required agent cannot load (raises ImportError)
    - Verifies that all expected agents are registered
    - Initializes AGENT_CONFIG with tool budgets and permission ceilings
    
    Raises:
        ImportError: If any required agent cannot be loaded
        RuntimeError: If not all expected agents are registered
    """
    logger.info("Initializing JARVIS agents...")
    
    # Import and register each agent
    try:
        from .repository_intelligence import repository_intelligence_agent
        register_agent("repository_intelligence", repository_intelligence_agent)
        logger.info("✓ Registered repository_intelligence")
    except ImportError as e:
        logger.error(f"✗ Failed to import repository_intelligence: {e}")
        raise ImportError(f"Failed to load agent repository_intelligence: {e}")
    
    try:
        from .code_understanding import code_understanding_agent
        register_agent("code_understanding", code_understanding_agent)
        logger.info("✓ Registered code_understanding")
    except ImportError as e:
        logger.error(f"✗ Failed to import code_understanding: {e}")
        raise ImportError(f"Failed to load agent code_understanding: {e}")
    
    try:
        from .relationship_intelligence import relationship_intelligence_agent
        register_agent("relationship_intelligence", relationship_intelligence_agent)
        logger.info("✓ Registered relationship_intelligence")
    except ImportError as e:
        logger.error(f"✗ Failed to import relationship_intelligence: {e}")
        raise ImportError(f"Failed to load agent relationship_intelligence: {e}")
    
    try:
        from .data_flow import data_flow_intelligence_agent
        register_agent("data_flow_intelligence", data_flow_intelligence_agent)
        logger.info("✓ Registered data_flow_intelligence")
    except ImportError as e:
        logger.error(f"✗ Failed to import data_flow_intelligence: {e}")
        raise ImportError(f"Failed to load agent data_flow_intelligence: {e}")
    
    try:
        from .software_engineering import software_engineering_agent
        register_agent("software_engineering", software_engineering_agent)
        logger.info("✓ Registered software_engineering")
    except ImportError as e:
        logger.error(f"✗ Failed to import software_engineering: {e}")
        raise ImportError(f"Failed to load agent software_engineering: {e}")
    
    try:
        from .testing_verification import testing_verification_agent
        register_agent("testing_verification", testing_verification_agent)
        logger.info("✓ Registered testing_verification")
    except ImportError as e:
        logger.error(f"✗ Failed to import testing_verification: {e}")
        raise ImportError(f"Failed to load agent testing_verification: {e}")
    
    try:
        from .visualization import visualization_agent
        register_agent("visualization_spatial", visualization_agent)
        logger.info("✓ Registered visualization_spatial")
    except ImportError as e:
        logger.error(f"✗ Failed to import visualization_spatial: {e}")
        raise ImportError(f"Failed to load agent visualization_spatial: {e}")
    
    try:
        from .conversational import conversational_agent
        register_agent("conversational", conversational_agent)
        logger.info("✓ Registered conversational")
    except ImportError as e:
        logger.error(f"✗ Failed to import conversational: {e}")
        raise ImportError(f"Failed to load agent conversational: {e}")
    
    try:
        from .orchestrator import orchestrator_agent
        register_agent("orchestrator", orchestrator_agent)
        logger.info("✓ Registered orchestrator")
    except ImportError as e:
        logger.error(f"✗ Failed to import orchestrator: {e}")
        raise ImportError(f"Failed to load agent orchestrator: {e}")

    try:
        from .architecture_design import architecture_design_agent
        register_agent("architecture_design", architecture_design_agent)
        logger.info("✓ Registered architecture_design")
    except ImportError as e:
        logger.error(f"✗ Failed to import architecture_design: {e}")
        raise ImportError(f"Failed to load agent architecture_design: {e}")
    
    # Initialize AGENT_CONFIG with default configurations
    for agent_name, config in DEFAULT_AGENT_CONFIG.items():
        AGENT_CONFIG[agent_name] = config.copy()
    
    # Verify all expected agents are registered
    registered_agents = set(AGENTS.keys())
    expected_set = set(EXPECTED_AGENTS)
    
    missing_agents = expected_set - registered_agents
    if missing_agents:
        logger.error(f"Missing agents: {missing_agents}")
        raise RuntimeError(f"Not all expected agents registered. Missing: {missing_agents}")
    
    extra_agents = registered_agents - expected_set
    if extra_agents:
        logger.warning(f"Extra agents registered (not in expected list): {extra_agents}")
    
    logger.info(f"✓ Successfully initialized {len(AGENTS)} agents")
    return len(AGENTS)
