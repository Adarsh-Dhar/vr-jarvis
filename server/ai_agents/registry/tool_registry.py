"""Tool registry for managing tool specifications and contracts."""
import inspect
import typing
from typing import List, Dict, Any, Optional
from ..contracts.tool import ToolSpec
from ..agents.toolsets import TOOL_LEVELS, TOOLSETS

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover - jsonschema is optional
    _HAS_JSONSCHEMA = False


def _py_type_to_schema(ann) -> Dict[str, Any]:
    """Map a resolved Python type hint to a JSON-schema fragment."""
    if ann is inspect.Parameter.empty or ann is None:
        return {}
    origin = typing.get_origin(ann)
    args = typing.get_args(ann)

    # Optional[X] / Union[X, None] / X | None
    if origin is typing.Union or str(origin) == 'types.UnionType':
        non_null = [a for a in args if a is not type(None)]
        if len(non_null) == 1 and len(non_null) != len(args):
            inner = _py_type_to_schema(non_null[0])
            inner.setdefault('type', inner.get('type', 'string'))
            return {'anyOf': [inner, {'type': 'null'}]}
        return {'anyOf': [_py_type_to_schema(a) for a in args] or [{}]}

    if origin in (list, typing.List, tuple, typing.Tuple, set, typing.Set, frozenset):
        item = _py_type_to_schema(args[0]) if args else {}
        schema = {'type': 'array'}
        if item:
            schema['items'] = item
        return schema

    if origin in (dict, typing.Dict):
        schema = {'type': 'object'}
        if len(args) == 2:
            schema['additionalProperties'] = _py_type_to_schema(args[1])
        return schema

    if origin is typing.Literal:
        return {'enum': list(args)}

    # Bare/generic types
    simple = {str: 'string', int: 'integer', float: 'number', bool: 'boolean',
              list: 'array', dict: 'object', type(None): 'null'}.get(ann)
    if simple:
        return {'type': simple}
    if ann is bytes:
        return {'type': 'string'}
    return {}  # unknown annotation: accept anything rather than guess wrong


def _resolve_hints(fn) -> Dict[str, Any]:
    try:
        return typing.get_type_hints(fn)
    except Exception:
        return {}


def _input_schema(fn):
    """JSON schema for a tool's arguments, built from resolved type hints."""
    props, required = {}, []
    hints = _resolve_hints(fn)
    for name, p in inspect.signature(fn).parameters.items():
        if name == 'tool_context' or p.kind in (inspect.Parameter.VAR_KEYWORD,):
            continue
        ann = hints.get(name, p.annotation)
        props[name] = _py_type_to_schema(ann)
        if p.default is inspect.Parameter.empty and p.kind not in (
                inspect.Parameter.VAR_POSITIONAL,):
            required.append(name)
    return {'type': 'object', 'properties': props, 'required': required,
            'additionalProperties': True}


def _output_schema(fn):
    """Best-effort output schema from the return annotation; falls back to a
    generic object schema since most tools return status dicts."""
    try:
        hints = typing.get_type_hints(fn)
        ret = hints.get('return', inspect.Signature.empty)
    except Exception:
        ret = inspect.Signature.empty
    if ret is inspect.Signature.empty or ret is None:
        return {'type': 'object'}
    schema = _py_type_to_schema(ret)
    if ret in (dict, Dict) or typing.get_origin(ret) in (dict, Dict) or schema == {}:
        return {'type': 'object',
                'properties': {'status': {'type': 'string'}},
                'required': []}
    return schema or {'type': 'object'}


def _owner_agents() -> Dict[str, List[str]]:
    owners: Dict[str, List[str]] = {}
    for agent, names in TOOLSETS.items():
        for n in names:
            owners.setdefault(n, []).append(agent)
    return owners


# Output schemas for important tool families (merged over return-annotation
# inference). Kept deliberately permissive: they describe the envelope, not
# every field, so legitimate richer results still validate.
_FAMILY_OUTPUT_SCHEMAS = {
    'run_tests': {'type': 'object', 'properties': {'status': {'type': 'string'}}},
    'run_typecheck': {'type': 'object', 'properties': {'typecheck': {'type': 'string'}}},
    'run_unit_tests': {'type': 'object', 'properties': {'status': {'type': 'string'}}},
    'run_integration_tests': {'type': 'object', 'properties': {'status': {'type': 'string'}}},
    'run_regression_tests': {'type': 'object', 'properties': {'status': {'type': 'string'}}},
    'generate_implementation_plan': {'type': 'object', 'properties': {'tasks': {'type': 'array'}}},
    'get_findings': {'type': 'array'},
}


def _group_for(tool_name: str) -> str:
    if 'git' in tool_name or 'worktree' in tool_name or 'patch' in tool_name:
        return 'git'
    if 'graph' in tool_name or 'call' in tool_name or 'callee' in tool_name or 'caller' in tool_name:
        return 'graph'
    if 'test' in tool_name or 'coverage' in tool_name or 'lint' in tool_name or 'typecheck' in tool_name:
        return 'test'
    if 'flow' in tool_name:
        return 'flow'
    if 'architecture' in tool_name or 'component' in tool_name or 'relationship' in tool_name \
            or 'requirement' in tool_name or 'plan' in tool_name:
        return 'architecture'
    if 'spatial' in tool_name or 'visualize' in tool_name or 'vr_' in tool_name \
            or 'panel' in tool_name or 'graph_' in tool_name and 'build' not in tool_name:
        return 'visualization'
    if 'repository' in tool_name or 'repo' in tool_name or 'file' in tool_name \
            or 'symbol' in tool_name or 'commit' in tool_name:
        return 'repository'
    return 'general'


class ToolRegistry:
    """Registry for managing JARVIS tools."""

    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
        self._owners = _owner_agents()
        self._load_tools()

    def _load_tools(self):
        """Load tools from toolsets."""
        from .. import tools as tools_module
        for tool_name, level in TOOL_LEVELS.items():
            fn = getattr(tools_module, tool_name, None)
            self._tools[tool_name] = ToolSpec(
                name=tool_name,
                group=_group_for(tool_name),
                level=level,
                owner_agents=list(self._owners.get(tool_name, [])),
                input_schema=_input_schema(fn) if callable(fn) else None,
                output_schema=(_FAMILY_OUTPUT_SCHEMAS.get(tool_name)
                               or (_output_schema(fn) if callable(fn) else {'type': 'object'})),
            )

    def get(self, tool_name: str) -> Optional[ToolSpec]:
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

    # ------------------------------------------------------------------
    # Runtime contract validation
    # ------------------------------------------------------------------
    def validate_arguments(self, tool_name: str, args: Dict[str, Any]) -> List[str]:
        """Validate call arguments against the tool's input schema.
        Returns a list of error strings; empty means valid."""
        spec = self._tools.get(tool_name)
        if spec is None or spec.input_schema is None:
            return []
        errors = []
        schema = spec.input_schema
        props = schema.get('properties', {})
        for req in schema.get('required', []):
            if req not in args or args[req] is None:
                errors.append('missing required argument: %s' % req)
        for key, value in (args or {}).items():
            if key == 'tool_context' or value is None:
                continue
            pschema = props.get(key)
            if not pschema:
                continue  # additionalProperties allowed
            expected = pschema.get('type')
            if expected == 'string' and not isinstance(value, str):
                errors.append('argument %s must be a string, got %s' % (key, type(value).__name__))
            elif expected == 'integer' and not isinstance(value, int):
                errors.append('argument %s must be an integer, got %s' % (key, type(value).__name__))
            elif expected == 'number' and not isinstance(value, (int, float)):
                errors.append('argument %s must be a number, got %s' % (key, type(value).__name__))
            elif expected == 'boolean' and not isinstance(value, bool):
                errors.append('argument %s must be a boolean, got %s' % (key, type(value).__name__))
            elif expected == 'array' and not isinstance(value, (list, tuple)):
                errors.append('argument %s must be an array, got %s' % (key, type(value).__name__))
            elif expected == 'object' and not isinstance(value, dict):
                errors.append('argument %s must be an object, got %s' % (key, type(value).__name__))
        return errors

    def validate_result(self, tool_name: str, result: Any) -> List[str]:
        """Validate a tool result against its output schema.
        Returns a list of error strings; empty means valid."""
        spec = self._tools.get(tool_name)
        if spec is None or spec.output_schema is None:
            return []
        if not _HAS_JSONSCHEMA:
            # Fallback: check the declared top-level type only.
            expected = spec.output_schema.get('type')
            if expected == 'object' and not isinstance(result, dict):
                return ['result must be an object, got %s' % type(result).__name__]
            if expected == 'array' and not isinstance(result, (list, tuple)):
                return ['result must be an array, got %s' % type(result).__name__]
            if expected == 'string' and not isinstance(result, str):
                return ['result must be a string, got %s' % type(result).__name__]
            return []
        try:
            jsonschema.validate(result, spec.output_schema)
            return []
        except jsonschema.ValidationError as exc:
            return ['result failed output schema: %s' % exc.message]
        except Exception:
            return []


_REGISTRY = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance (created once)."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ToolRegistry()
    return _REGISTRY
