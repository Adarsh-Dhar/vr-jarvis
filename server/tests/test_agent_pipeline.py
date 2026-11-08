from ai_agents.agent import phase2_pipeline


def _agent_names(agent):
    yield agent.name
    for sub_agent in getattr(agent, 'sub_agents', []) or []:
        yield from _agent_names(sub_agent)


def test_phase2_pipeline_does_not_run_orchestrator():
    """The phase-2 slice should go straight to specialists; the orchestrator's
    invoke_* tools are placeholders and can loop until /ask times out."""
    assert 'orchestrator' not in set(_agent_names(phase2_pipeline))
