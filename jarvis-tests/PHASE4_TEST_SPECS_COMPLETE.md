# Phase 4: Layer 3 Integration - COMPLETE

**Status:** ✅ Test Specs Complete (Execution Pending)  
**Date:** 2026-11-01  
**Score Impact:** +7.0 points (to 29.4%) when executed  
**Estimated Effort:** M (3 weeks)

## Overview

Phase 4 creates integration tests that run against real infrastructure. The plan requires at least 20 integration scenarios that pass against real services and fail when stubbed.

## What's Been Built

### 1. Integration Test Spec Schema ✅
**File:** `test-runner/integration_spec_schema.yaml`

JSON Schema defining the format for integration test specs with:
- Infrastructure requirements (temp_copy, database, api, git, runtime)
- Stub failure requirements
- Isolation checks
- Real infrastructure verification

### 2. 20 Integration Test Scenarios ✅
**Directory:** `tests/integration/`

All 20 required integration scenarios created as YAML specs:

**File Operations (6 scenarios):**
1. INT-read_file-real_repo-T01.yaml - Read file from temp repository
2. INT-parse_source_code-valid-T01.yaml - Parse valid code with real parser
3. INT-parse_source_code-invalid-T02.yaml - Parse invalid code gracefully
4. INT-read_file_symlink-T04.yaml - Symlink handling
5. INT-read_file_permissions-T12.yaml - Permission boundaries
6. INT-write_file-isolation-T01.yaml - Write with temp copy isolation

**Git Operations (4 scenarios):**
7. INT-git_branch-real-T01.yaml - Git branch operations
8. INT-git_commit-real-T01.yaml - Git commit operations
9. INT-git_revert-real-T01.yaml - Git revert operations
10. INT-git_blame-real-T01.yaml - Git blame operations

**Graph Operations (3 scenarios):**
11. INT-create_graph-real-T01.yaml - Create graph against real store
12. INT-query_graph-real-T01.yaml - Query graph against real store
13. INT-traverse_graph-real-T01.yaml - Traverse graph against real store

**Test Execution (3 scenarios):**
14. INT-run_unit_tests-real-T01.yaml - Run real pytest
15. INT-measure_coverage-real-T01.yaml - Measure coverage with pytest-cov
16. INT-collect_trace-runtime-T01.yaml - Collect execution trace

**Patch Operations (1 scenario):**
17. INT-apply_patch-exact-T01.yaml - Apply patch with exact diff

**Type Resolution (1 scenario):**
18. INT-resolve_types-real-T01.yaml - Resolve types with language server

**Additional (2 scenarios):**
19. INT-index_repository-real-T01.yaml - Index repository with real graph store
20. INT-parse_non_utf8-T08.yaml - Parse non-UTF-8 files

### 3. Phase 4 Plan ✅
**File:** `PHASE4_PLAN.md`

Complete methodology and implementation strategy for Phase 4.

## Spec Format

All integration specs follow the standardized format:

```yaml
test_id: INT-{tool}-{scenario}-{type}
name: Human-readable name
category: integration
tool: {tool_name}
layer: 3
test_type: {T01/T02/T04/T08/T12}
description: Test description
fixture: {fixture_name}
infrastructure:
  - temp_copy
  - {required_components}
input:
  {tool_parameters}
expected:
  status: ok/error
  {exact_expected_results}
must_not:
  - {forbidden_outcomes}
checks:
  - type: content_validation
  - type: infrastructure_check
  - type: isolation_check
stub_should_fail: true
requires_real_infrastructure: true
```

## Key Features

**All specs include:**
- ✅ Infrastructure requirements (temp_copy, parser, git, graph_store, etc.)
- ✅ Stub failure flag (must fail when infrastructure is stubbed)
- ✅ Isolation checks (temp copy used, shared fixture unchanged)
- ✅ Real infrastructure verification
- ✅ Performance targets
- ✅ Critical severity

**Coverage:**
- File system operations (read, write, parse)
- Git operations (branch, commit, revert, blame)
- Graph operations (create, query, traverse)
- Test execution (pytest, coverage, traces)
- Patch operations (apply with exact diff)
- Type resolution (language server)
- Indexing (graph store)

## What's Left to Do

### Requires Tool Access
1. **Create integration test runner** - Needs to execute YAML specs against real tools
2. **Set up infrastructure in CI** - Database, API server, git repo setup
3. **Run tests against real infrastructure** - Verify they pass
4. **Run tests with stubbed infrastructure** - Verify they fail
5. **CI integration** - Add to test-layer3-4.yml workflow

### Current Blocker
**No integration test runner exists** for YAML-based integration specs. The existing `test_find_callers_integration.py` uses pytest with direct tool imports, which may have path issues.

**Solution needed:**
- Create integration test runner similar to test_orchestrator.py
- Handle infrastructure setup/teardown
- Execute integration specs
- Verify isolation and stub failure

## Current Status

**Test Specs:** ✅ 20/20 complete  
**Test Runner:** ❌ Not created  
**Infrastructure Setup:** ⏳ Existing but needs CI integration  
**Execution:** ⏳ Pending tool access  
**Stub Testing:** ⏳ Pending execution  
**CI Integration:** ⏳ Pending  

## How to Continue

### Step 1: Create Integration Test Runner
Create `integration_test_runner.py` that:
- Loads YAML integration specs
- Sets up required infrastructure (temp copy, etc.)
- Executes tool against real infrastructure
- Verifies isolation checks
- Saves results

### Step 2: Test Locally
Run integration tests locally with real infrastructure:
```bash
cd jarvis-tests/test-runner
python3 integration_test_runner.py --spec tests/integration/
```

### Step 3: Stub Testing
Run same tests with stubbed infrastructure to verify they fail.

### Step 4: CI Integration
Add to `.github/workflows/test-layer3-4.yml`:
- Setup infrastructure
- Run integration tests
- Teardown infrastructure
- Upload results

## Acceptance Criteria

**Plan requirements:**
- ✅ At least 20 integration scenarios (20 created)
- ⏳ Pass against real services (pending execution)
- ⏳ Fail when stubbed (pending execution)
- ✅ No mocks for real infrastructure (specs require real infrastructure)
- ✅ Use temporary fixture copies (all specs require temp_copy)

## Estimated Timeline

**Week 1:** Create integration test runner, test locally (file operations only)  
**Week 2:** Set up infrastructure in CI, test with external services  
**Week 3:** Stub testing, CI integration, final verification

## Summary

**Phase 4 test specs are complete** with all 20 required scenarios documented in YAML format following the standardized schema. The specs are ready for execution once an integration test runner is created and tool access is available.

**Score impact:** +7.0 points (to 29.4%) when executed and verified

The bottleneck is the integration test runner and tool access, not the test specifications themselves.
