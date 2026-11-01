# Phase 4: Layer 3 Integration

**Status:** ⏳ PLANNING  
**Date:** 2026-11-01  
**Score Impact:** +7.0 points (to 29.4%)  
**Estimated Effort:** M (3 weeks)

## Overview

Phase 4 creates integration tests that run against real infrastructure (databases, APIs, git, parsers, test runners). The plan requires at least 20 integration scenarios that pass against real services and fail when stubbed.

## Current State

### Existing Integration Tests
**File:** `tests/integration/test_find_callers_integration.py`

Contains pytest-based integration tests for:
- find_callers with real repository
- build_call_graph integration
- run_unit_tests integration
- apply_patch integration

**Issue:** Tests import from `server/ai_agents/tools/` which may not be accessible or may have import path issues.

### Integration Infrastructure
**Directory:** `fixtures/integration-test-infrastructure/`

Contains:
- `apis/` - Flask REST API server
- `databases/` - SQLite test database
- `git-repos/` - Git repository with complex history
- `runtime/` - Synchronous and async Python applications
- `setup.sh` - Setup script for infrastructure

## Plan Requirements

### 12 Integration Scenarios (from plan)
1. read_file against real temporary repository (including symlinks and permissions)
2. parse_source_code with installed parser on valid, invalid, non-UTF-8 files
3. resolve_types with real compiler or language server on typed fixture
4. run_unit_tests that actually runs pytest with known pass/fail/skip counts
5. collect_execution_trace on runtime-heavy fixture vs recorded trace
6. create_graph and graph queries against real store
7. apply_patch changing exactly intended file and lines, nothing else
8. Git operations on real repository: branch, commit, revert, blame, history
9. Additional scenarios to reach 20 total

### Acceptance Criteria
- At least 20 integration scenarios pass against real services
- All integration tests fail when services are stubbed
- No mocks for anything listed as real infrastructure
- Tests use temporary fixture copies (never modify shared fixtures)

## Implementation Strategy

### Step 1: Fix Integration Test Runner
**Issue:** Current tests import from server tools with hardcoded paths

**Solution:**
1. Create integration test runner that doesn't require server import
2. Use YAML-based integration specs (like other tests)
3. Make infrastructure setup part of test execution
4. Handle import path issues gracefully

### Step 2: Create Integration Test Specs
**Format:** YAML specs for integration tests

```yaml
test_id: INT-read_file-real_repo-T01
name: Read file from real temporary repository
category: integration
tool: read_file
layer: 3
test_type: T01
description: Integration test - read file from real temp repository with symlinks
fixture: simple-python
infrastructure:
  - temp_copy
  - symlinks
  - permissions
input:
  file_path: main.py
expected:
  status: ok
  content_contains:
    - "def alpha():"
  file_not_modified: true
checks:
  - type: content_validation
  - type: isolation_check
    used_temp_copy: true
```

### Step 3: Implement Integration Test Scenarios

**Priority 1: Core File Operations (5 scenarios)**
1. read_file with temp copy, symlinks, permissions
2. read_file_range with real file boundaries
3. parse_source_code with real parser (valid, invalid, non-UTF-8)
4. write_file with temp copy isolation
5. delete_file with permission checks

**Priority 2: Git Operations (4 scenarios)**
6. git_branch on real repository
7. git_commit on real repository
8. git_revert on real repository
9. git_blame on real repository

**Priority 3: Graph Operations (3 scenarios)**
10. create_graph against real store
11. query_graph against real store
12. traverse_graph against real store

**Priority 4: Test Execution (3 scenarios)**
13. run_unit_tests with real pytest
14. measure_test_coverage with real pytest-cov
15. collect_execution_trace on runtime fixture

**Priority 5: Patch Operations (2 scenarios)**
16. apply_patch with exact diff
17. apply_patch rollback verification

**Priority 6: Type Resolution (2 scenarios)**
18. resolve_types with real language server
19. resolve_types on typed fixture

**Priority 7: Additional (1 scenario)**
20. Index repository with real incremental indexing

### Step 4: Infrastructure Setup
Ensure all infrastructure is properly set up:
```bash
cd fixtures/integration-test-infrastructure
./setup.sh
```

Components:
- SQLite database with sample data
- Flask API server with OpenAPI spec
- Git repository with complex history
- Runtime applications (sync and async)

### Step 5: Stub Testing
For each integration test:
1. Run against real infrastructure - should pass
2. Run with stubbed infrastructure - should fail
3. Verify isolation (temp copy used)
4. Verify no modification of shared fixtures

### Step 6: CI Integration
Add to `test-layer3-4.yml` workflow:
- Run integration tests
- Set up infrastructure
- Start services (API, database)
- Run tests
- Teardown infrastructure
- Upload results

## Implementation Timeline

**Week 1:**
- Fix integration test runner
- Create YAML spec format for integration tests
- Implement Priority 1 scenarios (5)

**Week 2:**
- Implement Priority 2-5 scenarios (11)
- Set up infrastructure in CI
- Test against real services

**Week 3:**
- Implement Priority 6-7 scenarios (4)
- Stub testing for all scenarios
- CI integration
- Final verification

## Blockers and Risks

**Blocker:** Access to actual tool implementations
- Current tests import from server/ai_agents/tools/
- May not be accessible in test environment
- Need to determine if tools can be imported or if we need to mock them

**Risk:** Infrastructure setup in CI
- Requires database, API server, git repo
- May need special CI runners
- Setup/teardown complexity

**Mitigation:**
- Start with file system operations (no external dependencies)
- Use Docker for infrastructure if needed
- Gradually add external services

## Next Steps

**Immediate:**
1. Create integration test spec format (YAML)
2. Implement Priority 1 scenarios (file operations - no external deps)
3. Test with simple-python fixture

**Short-term:**
4. Set up infrastructure components
5. Implement Priority 2-5 scenarios
6. Test against real services

**Medium-term:**
7. Implement Priority 6-7 scenarios
8. Stub testing
9. CI integration

## Success Metrics

- Integration scenarios: 0 → 20
- All pass against real services
- All fail when stubbed
- Scoreboard impact: +7.0 points

## Conclusion

Phase 4 can start with file system operations that don't require external infrastructure. More complex scenarios (database, API, git) can be added incrementally as infrastructure is set up.

The key is creating YAML-based integration specs that follow the same format as other tests, making them consistent and maintainable.
