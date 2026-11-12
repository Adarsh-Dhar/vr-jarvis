"""One-off audit of tool signatures for the strict contract checks.

Lists, for every tool in TOOL_LEVELS:
  * parameters whose default is None but whose resolved annotation is not
    Optional/nullable (these would start failing the null check), and
  * parameters whose annotation cannot be mapped to a JSON schema
    (x-unresolved), which must be fixed or allowlisted.

Run from the server/ directory:  python3 ../scripts/audit_tool_signatures.py
"""
import inspect
import sys
import typing
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent / 'server'
sys.path.insert(0, str(SERVER))

from ai_agents.agents.toolsets import TOOL_LEVELS  # noqa: E402
from ai_agents import tools as tools_module  # noqa: E402
from ai_agents.registry import tool_registry as tr  # noqa: E402


def _nullable(ann):
    if ann is None or ann is type(None):
        return True
    origin = typing.get_origin(ann)
    if origin in (typing.Union, __import__('types').UnionType):
        return any(a is type(None) for a in typing.get_args(ann))
    return False


def main():
    none_default = []
    unresolved = []
    for name in sorted(TOOL_LEVELS):
        fn = getattr(tools_module, name, None)
        if not callable(fn):
            print('MISSING TOOL FUNCTION: %s' % name)
            continue
        try:
            hints = typing.get_type_hints(fn)
        except Exception:
            hints = {}
        for pname, p in inspect.signature(fn).parameters.items():
            if pname in ('tool_context', 'self', 'cls'):
                continue
            ann = hints.get(pname, p.annotation)
            if p.default is None and not _nullable(ann) \
                    and ann is not inspect.Parameter.empty:
                none_default.append((name, pname, ann))
            schema = tr._py_type_to_schema(ann) if ann is not inspect.Parameter.empty else {}
            if schema.get('x-unresolved'):
                unresolved.append((name, pname, ann))
    print('== default None but non-Optional annotation ==')
    for row in none_default:
        print('  %s.%s : %r' % row)
    print('== unresolved annotations ==')
    for row in unresolved:
        print('  %s.%s : %r' % row)
    print('%d non-Optional None defaults, %d unresolved' %
          (len(none_default), len(unresolved)))


if __name__ == '__main__':
    main()
