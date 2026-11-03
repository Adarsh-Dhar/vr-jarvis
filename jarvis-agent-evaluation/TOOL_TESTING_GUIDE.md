# JARVIS Tool Testing Guide

## Overview

JARVIS tool testing validates the technical correctness of individual tools and capabilities. This is separate from agent testing - it answers "Does this capability work technically?" rather than "Does the agent know when/why/how to use it?"

## Location

Tool tests are located in: `/Users/adarsh/Documents/vr-agent/jarvis-tests/`

## Test Structure

### Test Runner
- **Main batch runner:** `test-runner/batch_execute_tests.py`
- Executes tests in batches with signature-driven adapters
- Handles tool parameters and expected results

### Test Definitions
- Tests are defined in YAML/JSON format
- Each test specifies:
  - Tool name
  - Required parameters
  - Expected output
  - Expected status (ok, not_found, error, etc.)

### Current Status
- **Total tests:** 5,753
- **Passed:** 5,664
- **Failed:** 89
- **Success Rate:** 98.45%

## Execution

### Running All Tests
```bash
cd /Users/adarsh/Documents/vr-agent/jarvis-tests/test-runner
python batch_execute_tests.py
```

### Running Specific Tests
The batch runner can execute subsets of tests based on:
- Tool categories
- Test phases
- Specific tool names

## Test Categories

### Signature-Driven Execution
- Tests use a signature-driven adapter approach
- Maps test inputs to tool parameters automatically
- Handles missing required parameters gracefully

### Expected Status Repair
- Script: `test-runner/fix_all_mismatches_including_errors.py`
- Automatically fixes expected status mismatches
- Corrects 868 mismatches in previous runs

### Current Issues
- 89 remaining failures include:
  - Expected status mismatches
  - Missing test-file identifiers
  - One parsing/runtime error (PHASE2-CORE-008)

## Reports

### Execution Report
- **Location:** `jarvis-tests/TEST_EXECUTION_REPORT.md`
- Contains detailed results of test runs
- Tracks progress and remaining issues

### Batch Report
- **Location:** `jarvis-tests/test-reports/batch_execution.json`
- JSON format with detailed test results
- Used for automated analysis

## Tool Testing Philosophy

### What It Tests
- ✅ Tool signature correctness
- ✅ Parameter handling
- ✅ Return value structure
- ✅ Error handling
- ✅ Edge cases

### What It Does NOT Test
- ❌ Agent decision-making
- ❌ When to use a tool
- ❌ Why to use a tool
- ❌ Tool selection quality
- ❌ Agent responsibility fulfillment

## Relationship to Agent Testing

Tool testing and agent testing are **independent evaluation systems**:

1. **Tool Testing:** Technical correctness of capabilities
   - Can a tool execute correctly?
   - Does it return expected results?
   - Status: 98.45% complete

2. **Agent Testing:** Agent decision-making and responsibility
   - Does the agent know when to use tools?
   - Does it use them correctly?
   - Does it fulfill its responsibility?
   - Status: Infrastructure complete, ready for agent integration

3. **System Testing:** Complete task completion
   - Does JARVIS solve real developer tasks?
   - Status: Not started

## Key Files

- `test-runner/batch_execute_tests.py` - Main test runner
- `test-runner/fix_all_mismatches_including_errors.py` - Status repair script
- `TEST_EXECUTION_REPORT.md` - Detailed execution report
- `test-reports/batch_execution.json` - JSON test results

## Next Steps for Tool Testing

1. Resolve remaining 89 failures
2. Investigate PHASE2-CORE-008 parsing error
3. Fix the 4 IDs not found by mismatch fixer
4. Distinguish genuine defects from fixture issues
5. Achieve 100% completion

## Notes

- Tool testing uses placeholder execution for tools that require external services
- Some tests may fail due to missing runtime dependencies
- The focus is on signature and structure, not external integration
