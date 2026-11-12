"""Print the registered and nested agent tree with depth and sub-agent counts.

Run from server/:  python3 ../scripts/agent_tree.py
"""
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent / 'server'
sys.path.insert(0, str(SERVER))


def _name(agent):
    return getattr(agent, 'name', type(agent).__name__)


def _subs(agent):
    return list(getattr(agent, 'sub_agents', None) or [])


def walk(agent, depth=0, seen=None):
    seen = seen if seen is not None else set()
    aid = id(agent)
    dup = ' (shared)' if aid in seen else ''
    seen.add(aid)
    subs = _subs(agent)
    print('%s%s  depth=%d sub_agents=%d%s' % ('  ' * depth, _name(agent),
                                              depth, len(subs), dup))
    for s in subs:
        walk(s, depth + 1, seen)


def main():
    from ai_agents.agents.registry import AGENTS, initialize_agents
    if not AGENTS:
        initialize_agents()
    print('== registered agents ==')
    max_depth = 0
    for name in sorted(AGENTS):
        agent = AGENTS[name]
        subs = _subs(agent)
        print('%s  sub_agents=%d' % (name, len(subs)))
        for s in subs:
            walk(s, 1)
    # measure depth
    def depth(a, d=0, seen=None):
        seen = seen if seen is not None else set()
        if id(a) in seen:
            return d
        seen.add(id(a))
        subs = _subs(a)
        return max([d] + [depth(s, d + 1, seen) for s in subs]) if subs else d
    for name in AGENTS:
        max_depth = max(max_depth, depth(AGENTS[name]))
    print('max nesting depth (incl. root):', max_depth)


if __name__ == '__main__':
    main()
