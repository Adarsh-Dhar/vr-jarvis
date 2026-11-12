"""Tool-contract enforcement tests (C10)."""
import pytest

from ai_agents.registry.tool_registry import get_tool_registry
from ai_agents.registry.output_schemas import (
    OUTPUT_SCHEMAS, CORE_TOOLS, UNRESTRICTED_PARAMS)
from ai_agents.agents.toolsets import TOOL_LEVELS


@pytest.fixture(scope='module')
def registry():
    return get_tool_registry()


def test_every_core_tool_has_explicit_schema():
    missing = [t for t in CORE_TOOLS if t not in OUTPUT_SCHEMAS]
    assert not missing, 'core tools without explicit schema: %s' % missing


def test_unregistered_tool_rejected(registry):
    assert registry.validate_arguments('no_such_tool', {})
    assert registry.validate_result('no_such_tool', {})


def _bad_args(fn):
    """Generate schema-violating argument sets for a core tool."""
    import inspect, typing
    schema = registry_schema(fn)
    return schema


def registry_schema(name):
    return get_tool_registry().get(name).input_schema


@pytest.mark.parametrize('tool', sorted(CORE_TOOLS))
def test_core_tool_rejects_bad_arguments(registry, tool):
    spec = registry.get(tool)
    if spec is None or spec.input_schema is None:
        pytest.skip('no input schema')
    schema = spec.input_schema
    props = schema.get('properties', {})
    required = schema.get('required', [])
    # missing required field
    if required:
        errs = registry.validate_arguments(tool, {})
        assert errs, 'missing required %s accepted for %s' % (required, tool)
    # wrong type on first typed property
    for pname, ps in props.items():
        if isinstance(ps, dict) and ps.get('type') == 'integer':
            errs = registry.validate_arguments(tool, {pname: 'not-an-int'})
            assert errs, 'wrong type accepted for %s.%s' % (tool, pname)
            break
    # undeclared extra argument
    errs = registry.validate_arguments(
        tool, {'__definitely_not_a_param__': 1})
    assert errs or schema.get('additionalProperties') is not False \
        or not props, 'extra arg accepted for %s' % tool
    # violated constraint (minimum) when present
    for pname, ps in props.items():
        if isinstance(ps, dict) and 'minimum' in ps:
            errs = registry.validate_arguments(tool, {pname: -999999})
            assert errs, 'constraint violated accepted for %s.%s' % (tool, pname)
            break


@pytest.mark.parametrize('tool', sorted(CORE_TOOLS))
def test_core_tool_rejects_bad_results(registry, tool):
    spec = registry.get(tool)
    if spec is None or spec.output_schema is None:
        pytest.skip('no output schema')
    # missing status
    assert registry.validate_result(tool, {})
    # error envelope always valid with error key, invalid without
    assert not registry.validate_result(tool, {'status': 'error', 'error': 'x'})
    assert registry.validate_result(tool, {'status': 'error'})


def test_read_file_range_semantic_rules(registry):
    repo_file = 'README.md'
    # a path outside the repository is rejected by the semantic rules
    errs = registry.validate_arguments(
        'read_file_range',
        {'file_path': '/etc/passwd', 'start_line': 1, 'end_line': 2})
    assert errs
    errs = registry.validate_arguments(
        'read_file_range',
        {'file_path': repo_file, 'start_line': 5, 'end_line': 2})
    assert any('start_line' in e for e in errs)


def test_unrestricted_params_are_real_and_reasoned():
    from ai_agents import tools as tools_module
    for (tool, param), reason in UNRESTRICTED_PARAMS.items():
        assert tool in TOOL_LEVELS, tool
        fn = getattr(tools_module, tool, None)
        assert fn is not None
        import inspect
        assert param in inspect.signature(fn).parameters, (tool, param)
        assert reason and reason.strip(), (tool, param)
