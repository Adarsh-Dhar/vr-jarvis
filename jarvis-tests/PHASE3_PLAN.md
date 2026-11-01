# Phase 3: Tool Correctness, Waves A to E

**Status:** ⏳ NOT STARTED  
**Date:** 2026-11-01  
**Score Impact:** +29.5 points (to 51.9%)  
**Estimated Effort:** XL (2 to 4 months, 2 to 3 engineers)

## Overview

Phase 3 is the long pole of the test plan. It verifies 531 tools across 5 waves, requiring real inputs, exact expected outputs, stub failure, mutant failure, temporary fixture isolation, and documented limitations for each tool.

## Wave Breakdown

### Wave A: Codebase Intelligence (127 tools, ~7.1 points)
**Modules:**
- `repository_tools` (11)
- `repository_intelligence_tools` (18)
- `navigation_tools` (10)
- `code_understanding_tools` (16)
- `analysis_tools` (15)
- `language_adapters` (20)
- `graph_tools` (11)
- `git_tools` (7)
- `git_history_toolkit` (3)
- `memory_tools` (3)
- `exec_tools` (3)
- `scene_tools` (8)
- `control_tools` (2)

**Oracles:**
- Python `ast` for symbols and calls
- `git` CLI for history
- `radon` for complexity
- `vulture` or `pyflakes` for dead code
- `tree-sitter` as second parser for differential checks

**Priority Tasks:**
1. Triage the 92 failing content specs into tool bugs vs bad expectations
2. Write first full set for `find_callers` using the hand-made alpha/beta/gamma/delta example
3. Fix known `repository_tools`, `search_symbols`, and `index_repository` references
4. Start with the 6 already verified plus the 40 tools that have content specs

### Wave B: Relationships and Knowledge (88 tools, ~5.0 points)
**Modules:**
- `relationship_intelligence_tools` (17)
- `data_flow_intelligence_tools` (19)
- `documentation_toolkit` (18)
- `conversational_tools` (16)
- `orchestrator_tools` (18)

**Oracles:**
- Hand-built call and data-flow manifests
- `pyan` or `ast` walkers
- Precision/recall thresholds (precision 1.0 on direct edges, recall ≥ 0.95)

**Key Requirements:**
- Unresolvable edges (callbacks, dynamic dispatch) must be returned as explicit uncertain relationships
- Nothing should be fabricated
- Orchestrator and conversational tools tested with scripted inputs, not LLM

### Wave C: Spatial and VR (72 tools, ~4.1 points)
**Modules:**
- `visualization_spatial_tools` (35)
- `vr_specific_tools` (37)

**Oracles:**
- Contract-test against JSON consumed by Unity client
- Exact command content (node ids, edge styles, depth, scope)
- Schema validity and state round trips
- Unity side is out of scope

### Wave D: Engineering, Runtime, Quality (131 tools, ~7.4 points)
**Modules:**
- `software_engineering_tools` (47)
- `testing_verification_tools` (20)
- `security_quality_tools` (26)
- `debugging_intelligence_tools` (18)
- `runtime_intelligence_tools` (20)

**Oracles:**
- Modify tools: verify diff on disk, idempotency, rollback, destructive approval
- Testing tools: run real `pytest` on fixture with known pass/fail/coverage
- Security tools: use security-challenge repo with known secrets/vulnerabilities
- Runtime tools: run runtime-heavy fixture in sandboxed subprocess with recorded trace

**Critical:**
- 67 current specs that delete or overwrite shared fixtures must be rewritten to use temp copies
- Secrets must never be echoed into results

### Wave E: Infrastructure and Integrations (113 tools, ~6.4 points)
**Modules:**
- `infrastructure_services` (49)
- `external_integrations_toolkit` (36)
- `api_database_toolkit` (28)

**Oracles:**
- API/database: SQLite and small web app fixture, schema and SQL engine query plan
- Integrations (GitHub, Docker, Kubernetes, CI, monitoring): contract-test against recorded responses and local fakes, never live accounts
- Infrastructure services: integration tests against real local instance

**Critical:**
- Test timeouts, service-down behavior
- No credential appears in any output
- Optional live smoke tests off by default

## How to Do 531 Tools Without 531 Hand-Written Files

**Approach:** Write one generator per archetype (section 5 of plan) that reads a small per-tool manifest and emits specs.

**Manifest Format:**
```yaml
tool: find_callers
fixture: simple-python
input:
  target: main
expected:
  callers:
    - name: helper
      file: main.py
      line: 5
    - name: dependency_injection_example
      file: main.py
      line: 15
must_not:
  - include_placeholder_symbols
```

**Generator Tasks:**
- Emit T01 (happy path) from human-written expected result
- Auto-generate T02 (invalid input), T04 (empty result), T08 (malformed), T12 (security) variants
- These variants need no tool-specific answer

## Per-Wave Acceptance Criteria

For each wave to be complete:
1. ✅ Every tool in the wave is verified (section 2 definitions)
2. ✅ Stub gate shows zero passing specs for those tools
3. ✅ Mutation kill rate for the wave is at least 80%

## Verified Tool Definition (from plan)

A tool is verified when ALL of these hold:
1. Its specs use real inputs taken from a fixture, never `placeholder`
2. Its expected result is exact: a set, an ordered list or specific values with file and line numbers, not just `status: ok`
3. It passes against the real tool
4. It fails against a do-nothing stub that returns `{"status": "ok"}`
5. It fails against at least two mutants of the real tool (return empty, return None, off-by-one, drop a field)
6. It runs on a temporary copy of the fixture, so it never changes shared files
7. It covers the test types that apply to it (section 5)
8. Its known limits are written down

## Required Test Types Per Tool Archetype

**Read and search (files, symbols, graph queries):**
T01 happy, T02 invalid input, T04 empty result, T05 boundary, T08 malformed, T12 path escape and security, T13 performance

**Analysis (call graphs, data flow, complexity):**
T01, T02, T04, T05, T07 complex input, T08, T13, plus unresolved cases returned as explicit uncertain results

**Modify (file edits, git, patches):**
T01, T02, T08, T12 permission and destructive guard, T14 reversible, T15 recovery after interruption

**Execute (builds, tests, processes):**
T01, T02, T09 dependency failure, T10 timeout, T11 concurrency, T12 sandbox

**Scene and visualization (commands for the VR layer):**
T01, T02, T03 output schema, T04, T08

**Integration adapters (GitHub, Docker, Kubernetes):**
T01 against recorded responses, T02, T09 service down, T10 timeout, T12 no credential leaks

## Starting Point

**Already have:**
- 6 verified tools
- 40 tools with real-input content specs
- 92 failing content specs (need triage)
- 67 specs that modify shared fixtures (need temp copy rewrite)

**Week 1 Priority:**
1. Triage the 92 failing content specs: decide tool bug vs bad expectation
2. Fix the right side of each
3. Write full `find_callers` spec set as reference
4. Fix `repository_tools`, `search_symbols`, `index_repository` references

## Estimated Timeline

- Wave A: 3-4 weeks (easiest and most foundational)
- Wave B: 2-3 weeks
- Wave C: 2-3 weeks
- Wave D: 3-4 weeks (complex due to modify tools)
- Wave E: 3-4 weeks (infrastructure setup)

**Total:** 13-18 weeks with 2-3 engineers

## Dependencies

Phase 3 requires:
- ✅ Phase 0 foundation (complete)
- ✅ Phase 1 fixtures and ground truth (complete)
- ✅ Phase 2 platform components (built, CI integration pending)

Phase 3 can start now with platform components available locally, even if CI integration is pending.

## Notes

- This is the bulk of the work (29.5 of 86.5 remaining points)
- Archetype generators plus hand-written ground truth are the strategy
- Add engineers here first when scaling up
- Each wave builds on the previous: codebase intelligence → relationships → spatial → engineering → infrastructure
