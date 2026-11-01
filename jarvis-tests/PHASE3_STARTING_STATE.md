# Phase 3 Starting State Analysis

**Date:** 2026-11-01  
**Purpose:** Document actual current state before Phase 3 Wave A begins

## Current Test Suite State

### Total Test Count
- 5,752 YAML test files
- 14 manually written core tool tests (tests/core-tools/)
- 524 "real-input" tests (tests/real-input/)
- 5,208 template/spec-level tests with placeholders

### Critical Finding: "Real-Input" Tests Are Not Actually Verified

The 524 tests in `tests/real-input/` are **NOT verified** according to the plan's definition:

**Example: REL-find_indirect_callers-T01.yaml**
```yaml
input:
  function_id: placeholder      # ❌ Not a real input
  tool_context: placeholder      # ❌ Not a real input
expected:
  status: ok                    # ❌ Not exact expected result
```

**Plan Requirements for Verified Tool:**
1. ✅ Real inputs from fixture (NOT `placeholder`)
2. ✅ Exact expected results (NOT just `status: ok`)
3. ✅ Pass against real tool
4. ✅ Fail against do-nothing stub
5. ✅ Fail against at least two mutants
6. ✅ Run on temporary copy of fixture
7. ✅ Cover required test types
8. ✅ Document known limitations

**Current State:**
- ❌ 1,011 `placeholder` values in real-input tests
- ❌ Most have only `status: ok` expected
- ❌ No stub failure verification
- ❌ No mutant testing
- ❌ No temp copy isolation
- ❌ No documented limitations

### Actually Verified Tools

**From scoreboard:**
- Current verified tools: 6 (based on plan baseline)
- Current score: 13.5%
- Layers 1-2 tool correctness: 0.5 of 30 points

**From tool_completion_status.json:**
- 23 tools tracked
- 6 Validated (26.1%)
- 17 Untested (73.9%)

**Gap:** The plan says 531 tools need verification. Current verified count is ~6.

### The "92 Failing Content Specs"

Based on the plan description:
- "Of 112 active content specs, 8 pass, 92 fail and 12 error"
- "Nobody has yet sorted tool bugs from bad expectations"

**Need to:** Run the actual tests to identify which 92 specs are failing and triage them.

## Phase 3 Week 1 Tasks - Revised

### Task 1: Identify the 92 Failing Content Specs
**Action:** Run the test suite and identify failing specs
**Command:** Need to determine how to run the test suite
**Output:** List of 92 failing specs with their errors

### Task 2: Triage Failing Specs
**For each failing spec:**
- Determine if it's a tool bug or bad expectation
- Document the decision
- Fix the right side (tool or test)

### Task 3: Write First Verified Tool as Reference
**Target:** `find_callers` (mentioned in plan as reference)
**Actions:**
1. Create spec with real input (actual function name from fixture)
2. Create exact expected result (actual callers with file/line numbers)
3. Run against real tool - should pass
4. Run against do-nothing stub - should fail
5. Run against mutants - should fail
6. Use temp copy isolation
7. Document limitations
8. Mark as verified

### Task 4: Fix Known Broken References
**Tools mentioned in plan:**
- `repository_tools`
- `search_symbols`
- `index_repository`
**Action:** Investigate and fix the reference issues

## Immediate Blocker

**Unknown:** How to run the actual test suite against the real JARVIS tools?

The test specs exist, but:
- Where are the actual tool implementations?
- How do we run the test orchestrator against them?
- Is there a way to run tests locally without the full JARVIS server?

**Need to:**
1. Locate the actual tool implementations
2. Understand the test execution path
3. Determine if we can run tests in isolation

## Next Steps

**Option A: Focus on Test Specification First**
- Write verified test specs following the plan's requirements
- Don't run them yet (defer actual execution until tool access is clarified)
- Create archetype generators
- This produces value even without tool access

**Option B: Focus on Tool Execution Path**
- Investigate where tools are implemented
- Set up test execution environment
- Run actual tests to identify the 92 failing specs
- This requires understanding the JARVIS architecture

**Recommendation:** Start with Option A (test specification) while investigating Option B in parallel. This allows progress on the 531-tool verification work without being blocked on tool access.

## Revised Phase 3 Strategy

**Phase 3A: Test Specification (can start now)**
1. Create archetype generators for each tool category
2. Write verified spec format (real inputs, exact expected outputs)
3. Create per-tool manifest format
4. Generate specs for Wave A tools (127 tools)
5. Document limitations for each tool

**Phase 3B: Test Execution (requires tool access)**
1. Investigate tool implementation location
2. Set up test execution environment
3. Run tests against real tools
4. Run against do-nothing stub
5. Run mutation testing
6. Triage 92 failing specs
7. Fix tool bugs or bad expectations

**Phase 3C: Integration (requires CI integration)**
1. Wire Phase 2 components into CI
2. Run scoreboard on every build
3. Enforce release gate
4. Track verified tool count

## Conclusion

Phase 3 cannot proceed in the traditional "run tests, fix failures" manner without:
1. Understanding how to execute tests against actual JARVIS tools
2. Access to the tool implementations
3. A working test execution environment

However, Phase 3 **can** proceed with test specification work:
- Write verified test specs following plan requirements
- Create archetype generators
- Define per-tool manifests
- This is valuable work that can be done independently

**Decision:** Pursue test specification work (Phase 3A) while investigating tool execution path (Phase 3B) in parallel.
