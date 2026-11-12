"""
Test that all toolsets resolve to valid tools.
"""
import pytest
from ai_agents.agents.toolsets import TOOLSETS, TOOL_LEVELS, get_toolset, validate_toolsets


def test_every_toolset_resolves():
    """Test that every toolset name can be resolved to actual tools."""
    validate_toolsets()
    for name in TOOLSETS:
        assert get_toolset(name) is not None, f"Toolset {name} did not resolve"


def test_all_exported_tools_have_permission_levels():
    """Test that every tool exported from the tools module has a permission level in TOOL_LEVELS."""
    import inspect
    from ai_agents import tools as tools_module

    # Get all exported tools
    exported_tools = set(
        name for name, obj in inspect.getmembers(tools_module)
        if callable(obj) and not name.startswith('_')
    )

    # Check each exported tool has a permission level
    missing_levels = []
    for tool_name in exported_tools:
        if tool_name not in TOOL_LEVELS:
            missing_levels.append(tool_name)

    if missing_levels:
        pytest.fail(
            f"The following {len(missing_levels)} exported tools are missing from TOOL_LEVELS: "
            f"{sorted(missing_levels)}. Add them to TOOL_LEVELS in toolsets.py with appropriate "
            f"permission levels ('read', 'execute', or 'write')."
        )


def _agent_instructions():
    """Every agent instruction in the system, keyed by agent name.

    Specialist agents expose INSTRUCTION; fix-pipeline agents expose .instruction
    on the LlmAgent instance. For agents without a TOOLSETS entry the allowed
    tool names come from the agent's own tool list."""
    from ai_agents.agents import (data_flow, testing_verification,
                                  code_understanding, relationship_intelligence,
                                  repository_intelligence, architecture_design,
                                  implementation_planning, conversational,
                                  visualization, navigator)
    from ai_agents.agents.fix import (patch_agent, verifier, code_reviewer,
                                      patch_repair, make_patch_review_repair,
                                      make_review_verifier)
    from ai_agents.agents.navigator import make_navigator
    navigator_agent_tools = make_navigator().tools
    from ai_agents.agents.critic import TEMPLATE as CRITIC_TEMPLATE
    from ai_agents.agent import ROOT_INSTRUCTION
    from ai_agents.agents.scene_director import INSTRUCTION as SCENE_INSTRUCTION, RESULT_INSTRUCTION

    instructions = {
        'data_flow_intelligence': data_flow.INSTRUCTION,
        'testing_verification': testing_verification.INSTRUCTION,
        'code_understanding': code_understanding.INSTRUCTION,
        'relationship_intelligence': relationship_intelligence.INSTRUCTION,
        'repository_intelligence': repository_intelligence.INSTRUCTION,
        'architecture_design': architecture_design.INSTRUCTION,
        'implementation_planning': implementation_planning.INSTRUCTION,
        'conversational': conversational.INSTRUCTION,
        'visualization_spatial': visualization.INSTRUCTION,
        'navigator': navigator.INSTRUCTION,
        'patch_agent': patch_agent.instruction,
        'verifier_agent': verifier.instruction,
        'code_reviewer': code_reviewer.instruction,
        'patch_repair_agent': patch_repair.instruction,
        'patch_review_repair_agent': make_patch_review_repair().instruction,
        'review_verifier_agent': make_review_verifier().instruction,
        'jarvis_orchestrator': ROOT_INSTRUCTION,
        'critic': CRITIC_TEMPLATE,
        'scene_director': SCENE_INSTRUCTION,
        'result_scene_director': RESULT_INSTRUCTION,
    }

    # Agents not in TOOLSETS: derive the allowed names from their tool lists.
    allowed_override = {
        'patch_agent': {getattr(t, '__name__', '') for t in patch_agent.tools},
        'verifier_agent': {getattr(t, '__name__', '') for t in verifier.tools},
        'code_reviewer': {getattr(t, '__name__', '') for t in code_reviewer.tools},
        'patch_repair_agent': {getattr(t, '__name__', '') for t in patch_repair.tools},
        'patch_review_repair_agent': {getattr(t, '__name__', '') for t in make_patch_review_repair().tools},
        'review_verifier_agent': ({getattr(t, '__name__', '') for t in make_review_verifier().tools}
                                  | {'exit_loop'}),  # named only to forbid it
        'navigator': {getattr(t, '__name__', '') for t in navigator_agent_tools},
        'critic': {'verify_citations', 'get_node'},
        'scene_director': {'highlight_vr_path', 'dim_unrelated', 'focus_camera',
                           'open_code_panel', 'set_edge_style', 'show_ghost_diff',
                           'show_test_badges', 'set_mode', 'get_worktree_diff'},
        'result_scene_director': {'highlight_vr_path', 'dim_unrelated', 'focus_camera',
                                  'open_code_panel', 'set_edge_style', 'show_ghost_diff',
                                  'show_test_badges', 'set_mode', 'get_worktree_diff'},
        'jarvis_orchestrator': {'request_approval', 'exit_loop',
                                'start_runtime_trace', 'stop_runtime_trace',
                                'get_runtime_trace'},  # named to delegate, not called
    }
    return instructions, allowed_override


def test_instructions_only_name_available_tools():
    from ai_agents.agents.toolsets import validate_instruction_tools, TOOL_LEVELS
    import re

    instructions, allowed_override = _agent_instructions()

    # Patch validate_instruction_tools' lookup: agents without a TOOLSETS entry
    # use their explicit allowed set; TOOLSETS agents use their curated list.
    errors = []
    for agent, text in instructions.items():
        if agent in allowed_override:
            allowed = allowed_override[agent]
        else:
            allowed = set(TOOLSETS.get(agent, []))
        for name in sorted(TOOL_LEVELS):
            pattern = r'(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])' % re.escape(name)
            if re.search(pattern, text) and name not in allowed:
                errors.append('%s: instruction mentions %s but its toolset lacks it' % (agent, name))
    assert errors == []


def test_review_loop_reviews_final_patch():
    """Regression: the review loop must end only when the reviewer approves the
    FINAL patch. Order is repair -> verifier -> reviewer, and the reviewer owns
    exit_loop; the verifier must not be able to end the loop on test success."""
    import ai_agents.agent as ag
    from ai_agents.agents.fix import code_reviewer, make_review_verifier, make_patch_review_repair

    fix = next(s for s in ag.root_agent.sub_agents if s.name == 'fix_pipeline')
    review = next(s for s in fix.sub_agents if s.name == 'review_loop')
    names = [getattr(s, 'name', '') for s in review.sub_agents]
    assert names == ['patch_review_repair_agent', 'review_verifier_agent',
                     'review_verify_gate', 'code_reviewer']
    # The gate re-runs repair+verify until recorded verification passes;
    # it sits between the verifier and the reviewer and never owns exit_loop.
    gate = review.sub_agents[2]
    assert [getattr(s, 'name', '') for s in gate.sub_agents] == [
        'gate_patch_repair_agent', 'gate_review_verifier_agent']

    # The review verifier must NOT hold exit_loop — passing tests cannot end
    # the loop before the modified patch is reviewed again.
    verifier_tools = {getattr(t, '__name__', '') for t in make_review_verifier().tools}
    assert 'exit_loop' not in verifier_tools
    assert {'run_tests', 'run_typecheck'} <= verifier_tools

    # The reviewer owns loop exit.
    reviewer_tools = {getattr(t, '__name__', '') for t in code_reviewer.tools}
    assert 'exit_loop' in reviewer_tools

    # The repair agent gets the review findings, not just test failures.
    repair = make_patch_review_repair()
    assert 'code_review' in repair.instruction
    assert 'acceptance' in repair.instruction


def _minimal_valid_args(tool, reg):
    """Fill required parameters from the registry input schema with type-correct
    placeholder values."""
    spec = reg.get(_tool_callable_name(tool))
    schema = (spec.input_schema if spec else None) or {}
    args = {}
    for pname in schema.get('required', []):
        pschema = (schema.get('properties') or {}).get(pname) or {}
        t = pschema.get('type')
        if t == 'array' or (isinstance(t, list) and 'array' in t):
            args[pname] = ['script.py'] if pname == 'command' else []
        elif t == 'integer' or (isinstance(t, list) and 'integer' in t):
            args[pname] = 1
        elif t == 'number' or (isinstance(t, list) and 'number' in t):
            args[pname] = 1.0
        elif t == 'boolean' or (isinstance(t, list) and 'boolean' in t):
            args[pname] = True
        elif t == 'object' or (isinstance(t, list) and 'object' in t):
            args[pname] = {}
        elif pschema.get('enum'):
            args[pname] = pschema['enum'][0]
        else:
            args[pname] = 'x'
    return args


def _tool_callable_name(t):
    return getattr(t, 'name', None) or getattr(t, '__name__', str(t))


class _FakeTool:
    def __init__(self, name):
        self.name = name


class FakeToolContext:
    def __init__(self, agent_name, state=None):
        self.agent_name = agent_name
        self.state = state if state is not None else {}


def test_every_bound_tool_is_registered():
    from ai_agents.agents.validate_toolsets import validate_agent_bindings
    assert validate_agent_bindings() == []


def test_permission_guard_accepts_every_bound_tool():
    from ai_agents.agents.validate_toolsets import (collect_active_agents,
                                                     _tool_name)
    from ai_agents.callbacks import permission_guard
    from ai_agents.registry.tool_registry import get_tool_registry
    from ai_agents import config
    from ai_agents.tools._common import repo_root
    reg = get_tool_registry()
    old_wt = getattr(config, 'ACTIVE_WORKTREE', None)
    config.ACTIVE_WORKTREE = str(repo_root())
    try:
        for aname, agent in collect_active_agents().items():
            for t in agent.tools:
                name = _tool_name(t)
                ctx = FakeToolContext(agent_name=aname,
                                      state={'worktree': '/tmp/wt'})
                res = permission_guard(_FakeTool(name),
                                       _minimal_valid_args(t, reg), ctx)
                assert not (res and res.get('validation') == 'input_schema'), \
                    (aname, name, res)
                assert not (res and 'not registered' in str(res)), \
                    (aname, name, res)
    finally:
        config.ACTIVE_WORKTREE = old_wt


def test_tool_registry_contracts():
    """Tool registry: resolved schemas, owners and runtime validation."""
    from ai_agents.registry.tool_registry import get_tool_registry
    reg = get_tool_registry()

    spec = reg.get('run_tests')
    assert spec is not None
    assert spec.owner_agents, 'run_tests should have owner agents from TOOLSETS'
    assert spec.input_schema and 'test_files' in spec.input_schema['properties']

    # Optional/List/Dict annotations resolve to real schema types.
    spec2 = reg.get('discover_tests')
    props = spec2.input_schema['properties']
    assert props['test_framework'].get('type') == 'string'

    # Argument validation: missing required arg and wrong type are errors.
    errors = reg.validate_arguments('run_tests', {'test_files': 'not-a-list'})
    assert any('array' in e for e in errors)
    errors = reg.validate_arguments('get_findings', {})
    assert errors == []  # tool_context-only tool: nothing required

    # Output validation: a non-dict result for a dict tool fails.
    bad = reg.validate_result('run_tests', 'a string, not a dict')
    assert bad
    good = reg.validate_result('run_tests',
                               {'status': 'passed', 'passed': ['t1'],
                                'failed': [], 'skipped': [],
                                'checks_not_run': []})
    assert good == []
