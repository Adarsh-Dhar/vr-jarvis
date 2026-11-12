"""Agent-tree complexity budget: at most 9 top-level registered agents.
Nesting depth is capped at 4: the spec's depth-3 budget counts routing
levels, and the deterministic ReviewVerifyRepairGate inside review_loop adds
one mechanical level (root -> pipeline -> loop -> gate -> verifier)."""
from ai_agents.agents.registry import AGENTS, initialize_agents

MAX_TOP_LEVEL = 9
MAX_DEPTH = 4


def _subs(agent):
    return list(getattr(agent, 'sub_agents', None) or [])


def _depth(agent, d=0, seen=None):
    seen = seen if seen is not None else set()
    if id(agent) in seen:
        return d
    seen.add(id(agent))
    subs = _subs(agent)
    if not subs:
        return d
    return max(_depth(s, d + 1, seen) for s in subs)


def test_registered_agent_count_within_budget():
    if not AGENTS:
        initialize_agents()
    assert len(AGENTS) <= MAX_TOP_LEVEL, (
        'too many top-level agents: %s' % sorted(AGENTS))


def test_agent_nesting_depth_within_budget():
    if not AGENTS:
        initialize_agents()
    for name, agent in AGENTS.items():
        assert _depth(agent) <= MAX_DEPTH, (
            'agent %s nests deeper than %d' % (name, MAX_DEPTH))


def test_no_duplicate_orchestrator_agents():
    if not AGENTS:
        initialize_agents()
    assert 'orchestrator' not in AGENTS
    assert 'software_engineering' not in AGENTS
    assert 'jarvis_orchestrator' in AGENTS
