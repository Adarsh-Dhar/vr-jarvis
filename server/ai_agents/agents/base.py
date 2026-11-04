"""
Agent Base Factory
Factory function to build LlmAgent instances from specifications.
"""

from typing import List, Callable, Dict, Any, Optional
from google.adk.agents import LlmAgent
from ..config import MODEL
from ..callbacks import log_agent_start, permission_guard, evidence_collector


class AgentSpec:
    """Specification for building an LLM agent."""

    def __init__(
        self,
        name: str,
        instruction_template: str,
        toolset: List[Callable],
        output_key: str,
        tool_budget: int = 20,
        permission_ceiling: str = "read",
        model: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.name = name
        self.instruction_template = instruction_template
        self.toolset = toolset
        self.output_key = output_key
        self.tool_budget = tool_budget
        self.permission_ceiling = permission_ceiling
        self.model = model or MODEL
        self.description = description or f"{name} specialist agent"


def make_specialist(spec: AgentSpec) -> LlmAgent:
    """
    Build an LlmAgent from a specification.

    Args:
        spec: AgentSpec with fields:
            - name: str
            - instruction_template: str (with {context} placeholders)
            - toolset: List[Callable]
            - output_key: str (state key for result)
            - tool_budget: int (max tool calls per turn)
            - permission_ceiling: str (read | execute | write)
            - model: str (optional, defaults to config.MODEL)
            - description: str (optional)

    Returns:
        LlmAgent instance
    """
    # Resolve tools from toolsets if using string names
    from .toolsets import get_toolset
    resolved_tools = []
    for tool in spec.toolset:
        if isinstance(tool, str):
            # Resolve string name to callable
            try:
                tool_callable = get_toolset(spec.name)
                # Find the specific tool in the resolved set
                for t in tool_callable:
                    if t.__name__ == tool:
                        resolved_tools.append(t)
                        break
                else:
                    raise ValueError(f"Tool {tool} not found in {spec.name} toolset")
            except Exception as e:
                raise ValueError(f"Failed to resolve tool {tool}: {e}")
        else:
            # Already a callable
            resolved_tools.append(tool)

    # Build the agent
    agent = LlmAgent(
        name=spec.name,
        model=spec.model,
        description=spec.description,
        instruction=spec.instruction_template,
        tools=resolved_tools,
        output_key=spec.output_key,
        before_agent_callback=log_agent_start,
        before_tool_callback=permission_guard,
        after_tool_callback=evidence_collector,
    )

    # Store permission ceiling and tool budget in registry for callbacks
    # (Can't set attributes on Pydantic models directly)
    from .registry import AGENT_CONFIG
    AGENT_CONFIG[spec.name] = {
        "permission_ceiling": spec.permission_ceiling,
        "tool_budget": spec.tool_budget,
    }

    return agent


def create_agent_spec(
    name: str,
    instruction: str,
    tools: List,
    output_key: str,
    **kwargs
) -> AgentSpec:
    """
    Convenience function to create an AgentSpec.

    Args:
        name: Agent name
        instruction: Instruction template
        tools: List of tool names or callables
        output_key: State key for output
        **kwargs: Additional AgentSpec fields

    Returns:
        AgentSpec instance
    """
    return AgentSpec(
        name=name,
        instruction_template=instruction,
        toolset=tools,
        output_key=output_key,
        **kwargs
    )
