"""Tool registry for managing tool specifications."""
import inspect
from typing import List, Dict
from ..contracts.tool import ToolSpec
from ..agents.toolsets import TOOL_LEVELS


def _input_schema(fn):
    props, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        if name == 'tool_context':
            continue
        ann = p.annotation
        props[name] = {'type': {str: 'string', int: 'integer', float: 'number', bool: 'boolean',
                                list: 'array', dict: 'object'}.get(ann, 'string')}
        if p.default is inspect.Parameter.empty:
            required.append(name)
    return {'type': 'object', 'properties': props, 'required': required}


class ToolRegistry:
    """Registry for managing JARVIS tools."""
    
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
        self._load_tools()
    
    def _load_tools(self):
        """Load tools from toolsets."""
        for tool_name, level in TOOL_LEVELS.items():
            # Determine group from tool name (heuristic)
            if 'git' in tool_name:
                group = 'git'
            elif 'graph' in tool_name or 'call' in tool_name or 'callee' in tool_name or 'caller' in tool_name:
                group = 'graph'
            elif 'test' in tool_name:
                group = 'test'
            elif 'flow' in tool_name:
                group = 'flow'
            elif 'architecture' in tool_name:
                group = 'architecture'
            elif 'spatial' in tool_name or 'visualize' in tool_name:
                group = 'visualization'
            elif 'repository' in tool_name or 'repo' in tool_name:
                group = 'repository'
            else:
                group = 'general'
            
            from .. import tools as tools_module
            fn = getattr(tools_module, tool_name, None)
            self._tools[tool_name] = ToolSpec(
                name=tool_name,
                group=group,
                level=level,
                owner_agents=[],
                input_schema=_input_schema(fn) if callable(fn) else None,
                output_schema={'status': 'string'}
            )
    
    def get(self, tool_name: str) -> ToolSpec:
        """Get a tool by name."""
        return self._tools.get(tool_name)
    
    def list(self, group: str = None) -> List[ToolSpec]:
        """List all tools, optionally filtered by group."""
        tools = list(self._tools.values())
        if group:
            tools = [t for t in tools if t.group == group]
        return tools
    
    def by_level(self, level: str) -> List[ToolSpec]:
        """List tools by permission level."""
        return [t for t in self._tools.values() if t.level == level]


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return ToolRegistry()
