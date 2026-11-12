#!/usr/bin/env python3
"""One-off audit: list tool parameters that look like paths but have no
PATH_POLICIES entry. Run from server/: python scripts/audit_path_policies.py"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_agents.registry.tool_registry import get_tool_registry
from ai_agents.registry.semantic_validators import PATH_POLICIES

PATHISH = re.compile(r'path|file|dir|repo|worktree|command', re.I)

reg = get_tool_registry()
missing = {}
for spec in reg.list():
    schema = spec.input_schema or {}
    props = schema.get('properties') or {}
    params = PATH_POLICIES.get(spec.name) or {}
    for pname in props:
        if PATHISH.search(pname) and pname not in params:
            missing.setdefault(spec.name, []).append(pname)

for tool, params in sorted(missing.items()):
    print('%s: %s' % (tool, ', '.join(params)))
print('\n%d tool(s) with path-like params missing from PATH_POLICIES'
      % len(missing))
