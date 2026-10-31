# Environment Setup for Test Spec Conversion

## Problem
The JARVIS tools depend on `google.adk` (Agent Development Kit) which is not installed in the current environment. This prevents the tools from running, which is required for:
- Running existing test specs
- Converting placeholder specs to real expected answers
- Capturing tool outputs for test validation

## Required Dependencies

### Core Dependencies
```bash
# Python 3.8+
python3 --version

# PyYAML for test spec parsing
pip install pyyaml

# pytest for Python test execution
pip install pytest
```

### Google ADK SDK
The tools import from `google.adk`:
- `google.adk.tools.ToolContext`
- `google.adk.agents.LlmAgent`
- `google.adk.agents.LoopAgent`
- `google.adk.agents.context.Context`

**Installation:**
```bash
# Method 1: If ADK is available via pip
pip install google-adk

# Method 2: If ADK is internal/private
# Contact your infrastructure team for installation instructions
# May require:
# - Internal pip repository
# - Service account authentication
# - Specific version requirements
```

### Additional Tool Dependencies
Some tools may require additional dependencies:
- Language parsers (tree-sitter, etc.)
- Git integration
- Docker/Kubernetes (for infrastructure tools)
- Database drivers (for database tools)

## Current Workaround: Mock Implementation

A temporary mock implementation has been added to `test_orchestrator.py` to allow runner testing without the full SDK. However, this only fixes the runner - actual tool execution still requires the real SDK.

## Options for Proceeding

### Option 1: Install Google ADK SDK (Recommended)
If you have access to the SDK:
1. Install it following the official instructions
2. Run Phase 2 (spec conversion script)
3. Run Phase 3 (core tools pilot)
4. Proceed with bulk conversion

### Option 2: Expand Mock Implementation
If SDK is unavailable:
1. Expand mocks in `test_orchestrator.py` to cover all google.adk imports
2. Create stub implementations of tools that return mock data
3. Use stub data to generate test specs
4. Update specs with real data when SDK becomes available

**Pros:** Can proceed without SDK
**Cons:** Specs will have mock data, not real expected answers

### Option 3: Focus on Runner-Only Changes
If SDK is unavailable long-term:
1. Document that runner is fixed (Phase 1 complete)
2. Provide conversion script for when SDK is available
3. Create manual conversion guide
4. Defer bulk conversion until environment is ready

**Pros:** Immediate value from runner fixes
**Cons:** Doesn't solve the core problem (placeholder specs)

## Verification Steps

Once SDK is installed, verify with:

```bash
cd /Users/adarsh/Documents/vr-agent/jarvis-tests/test-runner

# Test runner with core tools
python3 test_all_core_tools.py

# Expected: All 14 core tools pass
```

## CI/CD Integration

For automated testing:

```yaml
# .github/workflows/test-runner.yml
name: Test Runner
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: |
          pip install pyyaml pytest
          pip install google-adk  # Or your internal package
      - name: Run test runner
        run: |
          cd jarvis-tests/test-runner
          python3 test_all_core_tools.py
```

## Current Status

**Phase 1 (Runner Fixes):** ✅ COMPLETE
- All runner bugs fixed
- Fixture isolation working
- Must_not handling fixed
- Custom validation fields added

**Phase 2-10 (Spec Conversion):** ⏸️ BLOCKED
- Waiting for Google ADK SDK installation
- Conversion script framework ready
- Ready to proceed once environment is set up

## Next Steps

1. **Choose Option:** Decide which option to pursue (SDK install, expand mocks, or defer)
2. **Environment Setup:** Implement chosen option
3. **Verification:** Run test_all_core_tools.py to verify
4. **Proceed:** Continue with Phase 2 once environment is ready

## Contact

If you need help with:
- **SDK Installation:** Contact your infrastructure/devops team
- **Mock Expansion:** Can expand mocks as needed (Option 2)
- **Manual Conversion:** Can provide detailed guide (Option 3)
