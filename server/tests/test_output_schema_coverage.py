"""MVP tool-contract coverage: every tool used by the active MVP agents
must have an explicit output schema, a permission level and a non-empty
owner. Non-MVP tools are not registered at all."""
from ai_agents.agents.toolsets import TOOL_LEVELS, MVP_TOOL_NAMES, \
    MVP_TOOL_OWNERS
from ai_agents.registry import tool_registry as tr
from ai_agents.registry.output_schemas import OUTPUT_SCHEMAS


def _explicit_schema_names():
    return set(OUTPUT_SCHEMAS) | set(tr._FAMILY_OUTPUT_SCHEMAS)


def test_mvp_manifest_is_nonempty_and_consistent():
    assert MVP_TOOL_NAMES
    # Every MVP tool has a level and at least one owner agent.
    for name in MVP_TOOL_NAMES:
        assert name in TOOL_LEVELS, name
        assert MVP_TOOL_OWNERS.get(name), name


def test_every_mvp_tool_has_explicit_output_schema():
    missing = [n for n in sorted(MVP_TOOL_NAMES)
               if n not in OUTPUT_SCHEMAS]
    assert not missing, (
        'MVP tools lack an explicit OUTPUT_SCHEMAS entry: %s' % missing)


def test_every_mvp_tool_has_permission_and_owner():
    for name in sorted(MVP_TOOL_NAMES):
        assert name in TOOL_LEVELS, name
        assert MVP_TOOL_OWNERS.get(name), name


def test_registry_registers_exactly_the_mvp_set():
    reg = tr.get_tool_registry()
    registered = {t.name for t in reg.list()}
    assert registered == MVP_TOOL_NAMES, (
        'registry set differs from MVP manifest: extra=%s missing=%s'
        % (sorted(registered - MVP_TOOL_NAMES),
           sorted(MVP_TOOL_NAMES - registered)))


def test_registry_fails_closed_for_mvp_tool_without_schema(monkeypatch):
    """An MVP tool missing from OUTPUT_SCHEMAS must fail registration."""
    import ai_agents.registry.output_schemas as os_mod
    saved = dict(os_mod.OUTPUT_SCHEMAS)
    victim = sorted(MVP_TOOL_NAMES)[0]
    os_mod.OUTPUT_SCHEMAS.pop(victim, None)
    tr._REGISTRY = None
    try:
        try:
            tr.ToolRegistry()
            raise AssertionError('registration should have failed')
        except ValueError as exc:
            assert victim in str(exc)
    finally:
        os_mod.OUTPUT_SCHEMAS.clear()
        os_mod.OUTPUT_SCHEMAS.update(saved)
        tr._REGISTRY = None
