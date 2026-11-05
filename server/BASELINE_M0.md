# Milestone M0 Baseline Recording

**Date:** 2026-11-06
**Purpose:** Record current state before implementing JARVIS Skills Architecture and Six-Stage Call Graph

## Test Results

**Total tests:** 66
**Passed:** 65
**Failed:** 1
**Warnings:** 75

**Failed test:**
- `tests/test_llm.py::test_pacing_spaces_simultaneous_calls` - Timing assertion failure (not related to our changes)

**Note:** The failing test is unrelated to the call graph or skills architecture work. It's a timing test for LLM rate limiting.

## Code Metrics

### Tools
- **Total tool files:** 31 modules in `server/ai_agents/tools/`
- **tools/__init__.py:** 733 lines
- **Estimated public functions:** ~530 (from plan)
- **Total lines in tools:** 23,539 (from `wc -l`)

### Permission Levels (from toolsets.py)
Current code uses these permission levels:
- `read` - for read-only operations
- `execute` - for sandbox-only operations (runtime, debugging, testing)
- `write` - for worktree-only operations (software engineering)
- `analyze` - mentioned in plan, need to verify actual usage

**Note:** Plan specifies manifest permissions use `repository.read`, `graph.write` format, but code uses `read`, `analyze`, `execute`, `modify`. Need to create mapping table in M1.

### Key Files
- `repository.py`: 578 lines (mixes repo listing, indexing, call resolution, graph storage)
- `tree_sitter_parser.py`: 309 lines (extracts calls with only name/line/type)
- `codegraph.py`: 257 lines (reads graph.json, provides callers/callees/children/deps)
- `agents/registry.py`: 272 lines (agent registry)
- `agents/toolsets.py`: 994 lines (static TOOLSETS map, permission ceilings)

### Agent Structure
- **Total agents:** 12 (orchestrator, conversational, repository_intelligence, code_understanding, relationship_intelligence, data_flow_intelligence, runtime_intelligence, debugging_intelligence, security_quality, software_engineering, testing_verification, visualization_spatial)
- **Flat structure:** 25 files in `agents/` directory

## Graph Schema

**Current schema version:** 1 (implicit, not explicitly versioned in graph.json)

**Sample graph.json structure:**
```json
{
  "nodes": [
    {
      "id": "auth.validateSession",
      "name": "validateSession",
      "kind": "function",
      "file": "src/auth/session.ts",
      "start": 12,
      "end": 48,
      "cluster": "auth",
      "complexity": 7,
      "churn": 14
    }
  ],
  "edges": [
    {
      "src": "api.deleteAccount",
      "dst": "auth.validateSession",
      "type": "calls",
      "kind": "confirmed"
    }
  ],
  "tests": [...],
  "coverage": {...}
}
```

**ID format:** Dotted notation (e.g., `auth.validateSession`, `api.deleteAccount`)
**Edge fields:** `src`, `dst`, `type`, `kind`, `file`, `line`
**Resolution status:** `kind` field uses `confirmed`, `likely`, `unresolved`

## Known Defects to Fix

1. **Calls matched by name only** - No receiver information, aliases lost
2. **Imports reduced to last segment** - Module aliases not tracked
3. **First candidate picked** - Labeled `likely` or `unresolved` arbitrarily
4. **Method IDs collide** - Same name in different classes collide
5. **Repeated calls drift** - Same call site can resolve to different targets
6. **visualize_call_graph broken** - Neither traverses nor emits properly

## Performance Baseline

**Index time:** Not measured yet - will measure in M3 with sample repos
**Test runtime:** 128.12s for 66 tests

## Dependencies

**requirements.txt:**
- google-adk
- fastapi
- uvicorn[standard]
- pydantic
- pytest
- pytest-cov
- coverage
- pyyaml (already present)
- httpx
- tree-sitter
- tree-sitter-typescript
- tree-sitter-python
- tree-sitter-go
- tree-sitter-rust
- tree-sitter-java
- tree-sitter-c-sharp
- tree-sitter-cpp

**Need to add:** jsonschema (for manifest validation)

## Project Structure

```
server/
├── ai_agents/
│   ├── agents/          (25 files, flat structure)
│   ├── tools/           (31 modules, ~530 functions)
│   ├── repository.py    (578 lines - mixed responsibilities)
│   ├── tree_sitter_parser.py (309 lines)
│   ├── codegraph.py     (257 lines)
│   ├── callbacks.py
│   ├── config.py
│   ├── llm.py
│   ├── state.py
│   ├── data/            (graph.json, index/, etc.)
│   ├── evals/           (golden_tasks, runner.py)
│   └── tests/           (18 test files)
├── jarvis_server.py
└── tests/               (18 test files, 66 total tests)
```

**Missing:**
- No `skills/` directory
- No `intelligence/` directory
- No `contracts/` directory
- No `registry/` directory (separate from agents/registry.py)

## Next Steps

Proceed to Milestone M2: Extract Intelligence Layer with shims
