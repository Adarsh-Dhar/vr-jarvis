"""Tool registry for managing tool specifications and contracts."""
import inspect
import types
import typing
from typing import List, Dict, Any, Optional
from ..contracts.tool import ToolSpec
from ..agents.toolsets import TOOL_LEVELS, TOOLSETS
from .output_schemas import OUTPUT_SCHEMAS

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
    if origin is typing.Union or origin is types.UnionType:
        non_null = [a for a in args if a is not type(None)]
        members = [_py_type_to_schema(a) for a in non_null]
        # A member that maps to {} accepts anything, so the whole union does.
        if any(not m for m in members):
            return {}
        if len(non_null) != len(args):
            members.append({'type': 'null'})
        return members[0] if len(members) == 1 else {'anyOf': members}

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
    has_var_kw = any(p.kind is inspect.Parameter.VAR_KEYWORD
                     for p in inspect.signature(fn).parameters.values())
    return {'type': 'object', 'properties': props, 'required': required,
            'additionalProperties': has_var_kw}


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

    @staticmethod
    def _checked_output_schema(tool_name, fn):
        """Resolve the output schema for a tool and validate the schema itself
        at registration time, so a malformed schema fails at startup rather
        than mid-run. Explicit schemas in output_schemas.py win over the
        family table and the return-annotation fallback."""
        schema = (OUTPUT_SCHEMAS.get(tool_name)
                  or _FAMILY_OUTPUT_SCHEMAS.get(tool_name)
                  or (_output_schema(fn) if callable(fn) else {'type': 'object'}))
        if _HAS_JSONSCHEMA:
            jsonschema.Draft202012Validator.check_schema(schema)
        return schema

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
                output_schema=self._checked_output_schema(tool_name, fn),
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
    @staticmethod
    def _type_errors(value, schema, path):
        """Recursive JSON-schema subset check. Returns error strings.

        Handles type (incl. union lists), enum, anyOf/oneOf, nested
        properties/additionalProperties and array items — the shapes the
        registry actually emits from type hints."""
        if not isinstance(schema, dict) or not schema:
            return []
        errors = []

        expected = schema.get('type')
        type_map = {'string': str, 'integer': int, 'number': (int, float),
                    'boolean': bool, 'array': (list, tuple), 'object': dict,
                    'null': type(None)}
        if expected:
            types = expected if isinstance(expected, list) else [expected]
            ok = False
            for t in types:
                py = type_map.get(t)
                if py is None:
                    continue
                # bool is a subclass of int; keep 'integer' honest.
                if t == 'integer' and isinstance(value, bool):
                    continue
                if isinstance(value, py):
                    ok = True
                    break
            if not ok:
                errors.append('%s must be %s, got %s' % (path, '/'.join(types), type(value).__name__))
                return errors  # deeper checks are meaningless on a type miss

        if 'enum' in schema and value not in schema['enum']:
            errors.append('%s must be one of %r' % (path, schema['enum']))

        for key in ('anyOf', 'oneOf'):
            branches = schema.get(key)
            if branches:
                branch_errors = [ToolRegistry._type_errors(value, b, path) for b in branches]
                if not any(not e for e in branch_errors):
                    errors.append('%s does not match any allowed %s' % (path, key))
                return errors

        if isinstance(value, dict):
            props = schema.get('properties') or {}
            for req in schema.get('required', []):
                if req not in value or value[req] is None:
                    errors.append('%s.%s is required' % (path, req))
            addl = schema.get('additionalProperties')
            for k, v in value.items():
                if k in props:
                    errors.extend(ToolRegistry._type_errors(v, props[k], '%s.%s' % (path, k)))
                elif isinstance(addl, dict):
                    errors.extend(ToolRegistry._type_errors(v, addl, '%s.%s' % (path, k)))
        elif isinstance(value, (list, tuple)):
            items = schema.get('items')
            if isinstance(items, dict):
                for i, item in enumerate(value):
                    errors.extend(ToolRegistry._type_errors(item, items, '%s[%d]' % (path, i)))
        return errors

    def validate_arguments(self, tool_name: str, args: Dict[str, Any]) -> List[str]:
        """Validate call arguments against the tool's input schema.
        Returns a list of error strings; empty means valid."""
        spec = self._tools.get(tool_name)
        if spec is None or spec.input_schema is None:
            return []
        schema = spec.input_schema
        props = schema.get('properties', {})
        errors = []
        for req in schema.get('required', []):
            if req not in (args or {}) or args[req] is None:
                errors.append('missing required argument: %s' % req)
        for key, value in (args or {}).items():
            if key == 'tool_context' or value is None:
                continue
            pschema = props.get(key)
            if pschema is None:
                if schema.get('additionalProperties') is False:
                    errors.append('unexpected argument: %s' % key)
                continue
            if not pschema:
                continue  # {} means declared but untyped: any value accepted
            errors.extend(self._type_errors(value, pschema, 'argument %s' % key))
        return errors

    def validate_result(self, tool_name: str, result: Any) -> List[str]:
        """Validate a tool result against its output schema.
        Returns a list of error strings; empty means valid."""
        spec = self._tools.get(tool_name)
        if spec is None or spec.output_schema is None:
            return []
        if not _HAS_JSONSCHEMA:
            return ['output validator unavailable: jsonschema is not installed']
        try:
            jsonschema.validate(result, spec.output_schema)
            return []
        except jsonschema.ValidationError as exc:
            return ['result failed output schema: %s' % exc.message]
        except jsonschema.SchemaError as exc:
            return ['invalid output schema for %s: %s' % (tool_name, exc.message)]
        except Exception as exc:
            return ['output validation error for %s: %s' % (tool_name, exc)]


_REGISTRY = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance (created once)."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ToolRegistry()
    return _REGISTRY
