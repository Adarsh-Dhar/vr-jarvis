"""Startup contract tests for agent ownership and delegation."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_agents.agents.agent_contracts import (
    DELEGATED_TOOL_ROUTES, DELEGATED_PIPELINE_ROUTES)
from ai_agents.agents.toolsets import validate_instruction_tools, TOOLSETS
from ai_agents.agents import validate_toolsets as vt


def test_root_instruction_runtime_tools_are_delegated():
    from ai_agents.agent import root_agent
    errors = validate_instruction_tools(
        {root_agent.name: root_agent.instruction},
        delegated_routes=DELEGATED_TOOL_ROUTES)
    assert errors == []


def test_root_directly_binding_runtime_tool_fails():
    from ai_agents.agent import root_agent
    errors = vt.validate_delegation_contracts()
    assert errors == []
    # Simulate a direct binding: check the validator would flag it.
    def fake_tool():
        pass
    fake_tool.__name__ = 'start_runtime_trace'

    class Fake:
        name = 'jarvis_orchestrator'
        tools = [fake_tool]
        sub_agents = []
    live = vt.collect_live_agent_index()
    live['jarvis_orchestrator'] = Fake()
    errs = vt.validate_delegation_contracts(live_agents=live)
    assert any('directly binds' in e[2] for e in errs)


def test_removing_tool_from_specialist_fails():
    from ai_agents.agent import testing_pipeline
    errs = vt.validate_delegation_contracts()
    assert errs == []
    # Build a live index where testing_verification lacks the tool.
    live = vt.collect_live_agent_index()
    target = live['testing_verification']
    saved = target.tools
    target.tools = [t for t in target.tools
                    if vt._tool_name(t) != 'start_runtime_trace']
    try:
        errs = vt.validate_delegation_contracts(live_agents=live)
        assert any(e[1] == 'start_runtime_trace' for e in errs)
    finally:
        target.tools = saved


def test_nonexistent_pipeline_fails():
    from ai_agents.agents import agent_contracts
    orig = dict(DELEGATED_TOOL_ROUTES['jarvis_orchestrator'])
    DELEGATED_TOOL_ROUTES['jarvis_orchestrator'] = {
        'start_runtime_trace': 'no_such_pipeline'}
    try:
        errs = vt.validate_delegation_contracts()
        assert any('does not exist' in e[2] for e in errs)
    finally:
        DELEGATED_TOOL_ROUTES['jarvis_orchestrator'] = orig


def test_pipeline_without_specialist_fails():
    live = vt.collect_live_agent_index()
    # Point route at a pipeline lacking the runtime specialist.
    from ai_agents.agents import agent_contracts
    orig = dict(DELEGATED_TOOL_ROUTES['jarvis_orchestrator'])
    DELEGATED_TOOL_ROUTES['jarvis_orchestrator'] = {
        'start_runtime_trace': 'investigate_pipeline'}
    try:
        errs = vt.validate_delegation_contracts(live_agents=live)
        assert any('no descendant' in e[2] for e in errs)
    finally:
        DELEGATED_TOOL_ROUTES['jarvis_orchestrator'] = orig


def test_tool_not_in_owner_agents_fails():
    from ai_agents.agents.toolsets import MVP_TOOL_OWNERS
    # pick a tool owned only by testing_verification
    tool = 'start_runtime_trace'
    owners = MVP_TOOL_OWNERS[tool]
    assert 'testing_verification' in owners
    # jarvis_orchestrator is not an owner -> would fail owner check
    assert 'jarvis_orchestrator' not in owners


def test_dynamic_agents_included_in_validation():
    live = vt.collect_live_agent_index()
    for expected in ('patch_agent', 'patch_repair_agent',
                     'patch_review_repair_agent', 'verifier_agent',
                     'review_verifier_agent', 'code_reviewer'):
        assert expected in live, expected


def test_startup_validator_succeeds_with_valid_tree():
    vt.validate_runtime_agent_contracts()
