"""Tool registry for managing tool specifications and contracts."""
import collections.abc as _cabc
import enum
import inspect
import pathlib
import types
import typing
from typing import List, Dict, Any, Optional
from ..contracts.tool import ToolSpec, Constraint
from ..agents.toolsets import (TOOL_LEVELS, TOOLSETS, MVP_TOOL_NAMES,
                               MVP_TOOL_OWNERS)
from .output_schemas import (OUTPUT_SCHEMAS, UNRESTRICTED_PARAMS, CORE_TOOLS,
                             assert_data_tool_schemas)

import jsonschema
from jsonschema import Draft202012Validator, validators
_HAS_JSONSCHEMA = True


def _tuple_ok(checker, inst):
    return isinstance(inst, (list, tuple))


if _HAS_JSONSCHEMA:
    _Validator = validators.extend(
        Draft202012Validator,
        type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
            'array', _tuple_ok))
else:  # pragma: no cover
    _Validator = None

_UNRESOLVED = {'x-unresolved': True}


def _union_schema(args):
    """Shared union handling for typing.Union and X | Y."""
    non_null = [a for a in args if a is not type(None)]
    members = [_py_type_to_schema(a) for a in non_null]
    # A member that maps to {} accepts anything, so the whole union does.
    if any(not m for m in members):
        return {}
    # An unresolved member makes the whole union unresolved.
    if any(m.get('x-unresolved') for m in members):
        return dict(_UNRESOLVED)
    if len(non_null) != len(args):
        members.append({'type': 'null'})
    return members[0] if len(members) == 1 else {'anyOf': members}


def _py_type_to_schema(ann) -> Dict[str, Any]:
    """Map a resolved Python type hint to a JSON-schema fragment.

    Returns {} only for intentionally unrestricted annotations (Any, object).
    Anything we cannot map returns {'x-unresolved': True} so registration can
    reject it instead of silently accepting every value."""
    if ann is inspect.Parameter.empty or ann is None:
        return {}
    if ann is typing.Any or ann is object:
        return {}

    # Annotated[X, Constraint...] -> schema of X merged with each constraint
    if typing.get_origin(ann) is typing.Annotated:
        base, *meta = typing.get_args(ann)
        schema = dict(_py_type_to_schema(base))
        for m in meta:
            if isinstance(m, Constraint):
                schema.update(m.schema)
        return schema

    origin = typing.get_origin(ann)
    args = typing.get_args(ann)

    # Optional[X] / Union[X, None] / X | None
    if origin is typing.Union or origin is types.UnionType:
        return _union_schema(args)

    if origin in (list, typing.List, tuple, typing.Tuple, set, typing.Set,
                  frozenset, typing.FrozenSet):
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

    # collections.abc generics: Mapping -> object, Sequence/Iterable/Set -> array
    if origin in (_cabc.Mapping, _cabc.MutableMapping, typing.Mapping):
        return {'type': 'object'}
    if origin in (_cabc.Sequence, _cabc.MutableSequence, _cabc.Iterable,
                  _cabc.Set, _cabc.MutableSet, typing.Sequence,
                  typing.Iterable, typing.Set):
        return {'type': 'array'}

    if origin is typing.Literal:
        return {'enum': list(args)}

    # Bare/generic types
    simple = {str: 'string', int: 'integer', float: 'number', bool: 'boolean',
              list: 'array', dict: 'object', type(None): 'null'}.get(ann)
    if simple:
        return {'type': simple}
    if ann is bytes:
        return {'type': 'string'}
    if ann is pathlib.Path or (inspect.isclass(ann)
                               and issubclass(ann, pathlib.PurePath)):
        return {'type': 'string'}

    # TypedDict -> object with properties. Checked before inspect.isclass
    # because TypedDict is not a real class on all supported versions.
    if getattr(ann, '__required_keys__', None) is not None \
            or getattr(ann, '__optional_keys__', None) is not None \
            or (hasattr(ann, '__annotations__')
                and hasattr(ann, '__total__')):
        props = {}
        hints = getattr(ann, '__annotations__', {})
        for k, v in hints.items():
            props[k] = _py_type_to_schema(v)
        schema = {'type': 'object', 'properties': props}
        required = [k for k in getattr(ann, '__required_keys__', ())]
        if required:
            schema['required'] = list(required)
        return schema

    if inspect.isclass(ann):
        try:
            if issubclass(ann, enum.Enum):
                return {'enum': [m.value for m in ann]}
            if issubclass(ann, _cabc.Mapping):
                return {'type': 'object'}
            if issubclass(ann, (_cabc.Sequence, _cabc.Set, _cabc.Iterable)) \
                    and not issubclass(ann, (str, bytes, bytearray)):
                return {'type': 'array'}
        except TypeError:
            pass

    return dict(_UNRESOLVED)


def _resolve_hints(fn) -> Dict[str, Any]:
    try:
        # include_extras keeps Annotated[..., Constraint] metadata visible;
        # without it every constraint branch below is dead code.
        return typing.get_type_hints(fn, include_extras=True)
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
    var_kw = next((p for p in inspect.signature(fn).parameters.values()
                   if p.kind is inspect.Parameter.VAR_KEYWORD), None)
    has_var_kw = var_kw is not None
    schema = {'type': 'object', 'properties': props, 'required': required}
    if has_var_kw:
        # **kwargs: T annotates additionalProperties; untyped kwargs stay
        # unrestricted here and are policed at registration for MVP tools.
        kw_ann = hints.get(var_kw.name, var_kw.annotation)
        kw_schema = _py_type_to_schema(kw_ann) \
            if kw_ann is not inspect.Parameter.empty else {}
        schema['additionalProperties'] = kw_schema if kw_schema else True
        schema['x-var-keyword'] = var_kw.name
    else:
        schema['additionalProperties'] = False
    return schema


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
        # Data tools must carry data-bearing schemas; a violation stops the
        # server at startup rather than surfacing mid-run.
        assert_data_tool_schemas()

    @staticmethod
    def _checked_output_schema(tool_name, fn):
        """Resolve the output schema for a tool and validate the schema itself
        at registration time, so a malformed schema fails at startup rather
        than mid-run. Explicit schemas in output_schemas.py win over the
        family table and the return-annotation fallback."""
        schema = OUTPUT_SCHEMAS.get(tool_name)
        if schema is None:
            if tool_name in MVP_TOOL_NAMES or tool_name in CORE_TOOLS:
                raise ValueError(
                    'MVP tool %s has no explicit OUTPUT_SCHEMAS entry'
                    % tool_name)
            schema = (_FAMILY_OUTPUT_SCHEMAS.get(tool_name)
                      or (_output_schema(fn) if callable(fn)
                          else {'type': 'object'}))
        if _HAS_JSONSCHEMA:
            jsonschema.Draft202012Validator.check_schema(schema)
        return schema

    @staticmethod
    def _check_input_schema(tool_name, fn):
        """Build the input schema, validate the schema itself, and reject
        parameters whose annotation could not be resolved (x-unresolved)
        unless explicitly allowlisted in UNRESTRICTED_PARAMS."""
        schema = _input_schema(fn) if callable(fn) else None
        if schema is None:
            return None
        if _HAS_JSONSCHEMA:
            _Validator.check_schema(schema)
        # **kwargs typing: an untyped VAR_KEYWORD on an MVP tool is rejected
        # unless explicitly allowlisted in UNRESTRICTED_PARAMS.
        var_kw = schema.get('x-var-keyword')
        if var_kw is not None:
            kw_schema = schema.get('additionalProperties')
            typed = isinstance(kw_schema, dict) and kw_schema \
                and not kw_schema.get('x-unresolved')
            if not typed and (tool_name, var_kw) not in UNRESTRICTED_PARAMS:
                raise ValueError(
                    'tool %s has untyped **%s; annotate it or add it to '
                    'UNRESTRICTED_PARAMS' % (tool_name, var_kw))
        for pname, pschema in (schema.get('properties') or {}).items():
            if isinstance(pschema, dict) and not pschema \
                    and (tool_name, pname) not in UNRESTRICTED_PARAMS:
                raise ValueError(
                    'tool %s parameter %r has an unrestricted schema {}; '
                    'annotate it or add it to UNRESTRICTED_PARAMS'
                    % (tool_name, pname))
            if isinstance(pschema, dict) and pschema.get('x-unresolved'):
                if (tool_name, pname) not in UNRESTRICTED_PARAMS:
                    raise ValueError(
                        'tool %s parameter %r has an annotation that cannot '
                        'be mapped to a JSON schema; fix the annotation or '
                        'add it to UNRESTRICTED_PARAMS' % (tool_name, pname))
        return schema

    def _load_tools(self):
        """Load the active MVP tools (the union of the agent toolsets)."""
        from .. import tools as tools_module
        for tool_name in sorted(MVP_TOOL_NAMES):
            level = TOOL_LEVELS.get(tool_name)
            if level is None:
                raise ValueError(
                    'MVP tool %s missing from TOOL_LEVELS' % tool_name)
            owners = self._owners.get(tool_name) or []
            if not owners:
                raise ValueError(
                    'MVP tool %s has empty ownership metadata' % tool_name)
            fn = getattr(tools_module, tool_name, None)
            if fn is None or not callable(fn):
                raise ValueError(
                    'tool %s listed in TOOL_LEVELS is not exported' % tool_name)
            self._tools[tool_name] = ToolSpec(
                name=tool_name,
                group=_group_for(tool_name),
                level=level,
                owner_agents=list(owners),
                input_schema=self._check_input_schema(tool_name, fn),
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
        """Full JSON Schema (Draft 2020-12) validation of a value against a
        schema fragment. Returns error strings. The 'array' type checker is
        extended to accept tuples as well as lists."""
        if not isinstance(schema, dict) or not schema:
            return []
        if not _HAS_JSONSCHEMA or _Validator is None:
            return ['%s: input validator unavailable' % path]
        errors = []
        for e in _Validator(schema).iter_errors(value):
            loc = ('.' + '.'.join(map(str, e.absolute_path))) \
                if e.absolute_path else ''
            errors.append('%s%s: %s' % (path, loc, e.message))
        return errors

    @staticmethod
    def _allows_null(pschema, tool_name=None, param=None):
        """True when the parameter schema admits an explicit null."""
        if not isinstance(pschema, dict):
            return True
        if pschema.get('x-unresolved'):
            return False
        if not pschema:
            # Intentionally unrestricted (Any/object or allowlisted).
            return True
        if pschema.get('type') == 'null':
            return True
        for key in ('anyOf', 'oneOf'):
            branches = pschema.get(key)
            if branches and any(
                    isinstance(b, dict) and b.get('type') == 'null'
                    for b in branches):
                return True
        return False

    def validate_arguments(self, tool_name: str, args: Dict[str, Any]) -> List[str]:
        """Validate call arguments against the tool's input schema.
        Returns a list of error strings; empty means valid."""
        spec = self._tools.get(tool_name)
        if spec is None:
            return ['tool %s is not registered' % tool_name]
        if spec.input_schema is None:
            return ['tool %s has no input schema' % tool_name]
        schema = spec.input_schema
        props = schema.get('properties', {})
        errors = []
        args = args or {}
        for req in schema.get('required', []):
            if req not in args:
                errors.append('missing required argument: %s' % req)
        for key, value in args.items():
            if key == 'tool_context':
                continue
            pschema = props.get(key)
            if pschema is None:
                if schema.get('additionalProperties') is False:
                    errors.append('unexpected argument: %s' % key)
                continue
            if value is None:
                if not self._allows_null(pschema, tool_name, key):
                    errors.append('argument %s must not be null' % key)
                continue
            if not pschema:
                if (tool_name, key) not in UNRESTRICTED_PARAMS:
                    errors.append(
                        'argument %s has no type constraint and is not '
                        'allowlisted in UNRESTRICTED_PARAMS' % key)
                continue  # {} means declared but untyped: any value accepted
            errors.extend(self._type_errors(value, pschema, 'argument %s' % key))
        from .semantic_validators import semantic_errors
        errors.extend(semantic_errors(tool_name, args))
        return errors

    def validate_result(self, tool_name: str, result: Any) -> List[str]:
        """Validate a tool result against its output schema.
        Returns a list of error strings; empty means valid."""
        spec = self._tools.get(tool_name)
        if spec is None:
            return ['tool %s is not registered' % tool_name]
        if spec.output_schema is None:
            return ['tool %s has no output schema' % tool_name]
        if not _HAS_JSONSCHEMA:
            return ['output validator unavailable: jsonschema is not installed']
        try:
            jsonschema.validate(result, spec.output_schema)
            from .semantic_validators import semantic_result_errors
            return semantic_result_errors(tool_name, result)
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
