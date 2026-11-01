# Tool Validation Plan

## Current Status

Based on `server/ai_agents/data/tool_completion_status.json` (2026-11-01):

- **Total tools**: 533
- **Validated**: 8 tools (1.5%)
- **Experimental**: 350 tools (65.7%)
- **Untested**: 177 tools (33.2%)

### Validated Tools (8)

These tools have real-input tests with known correct answers:

1. **read_file** - Core file reading, 3 tests, 100% pass rate
2. **search_code** - Code search, 2 tests, 100% pass rate
3. **get_symbol_definition** - Navigation, 5 tests, 100% pass rate
4. **get_symbol_references** - Navigation, 3 tests, 100% pass rate
5. **find_callers** - Relationship analysis, 4 tests, 100% pass rate
6. **find_callees** - Relationship analysis, 3 tests, 100% pass rate
7. **parse_source_code** - Analysis, 5 tests, 100% pass rate
8. **verify_citations** - Critic validation, 2 tests, 100% pass rate

### Experimental Tools (350)

These tools exist but lack real-input validation. They fall into categories:

#### Phase 2 Vertical Slice (Repository, Code Understanding, Relationship)
- detect_languages, detect_frameworks, analyze_repository_structure
- get_type_hierarchy, extract_function_contract, identify_side_effects
- build_call_graph, calculate_change_impact

#### Phase 3 (Data Flow, Security/Quality)
- trace_variable_origin, trace_taint_flow
- scan_secrets, scan_security_vulnerabilities, calculate_complexity

#### Phase 4 (Runtime, Debugging)
- start_application, collect_execution_trace
- analyze_stack_trace, identify_root_cause

#### Phase 5 (Software Engineering, Testing)
- edit_file, apply_patch
- run_unit_tests, measure_test_coverage

#### Visualization
- highlight_vr_path, create_graph

### Shallow Tools (6) - Known to be keyword/template-based

These tools are marked as shallow and need deep implementation:

1. **analyze_cryptography** - Keyword matching only
2. **detect_code_smells** - Keyword matching only
3. **identify_technical_debt** - Keyword matching only
4. **refactor_function** - Template-based only
5. **implement_interface** - Template-based only
6. **build_dependency_graph** - Basic graph only

## Validation Strategy

### Priority 1: Phase 2 Vertical Slice Tools (High Impact)

These tools are used in the active phase2_pipeline:

**Repository Intelligence (19 tools)**:
- Target: Validate top 5 most-used tools
- Priority: list_files, detect_languages, detect_frameworks, analyze_repository_structure, get_repository_metadata

**Code Understanding (22 tools)**:
- Target: Validate top 8 most-used tools
- Priority: get_type_hierarchy, extract_symbols, resolve_types, explain_function, explain_class, extract_function_contract, identify_side_effects, analyze_control_flow

**Relationship Intelligence (17 tools)**:
- Target: Validate top 5 most-used tools
- Priority: build_call_graph, find_indirect_callers, trace_call_chain, find_dependents, calculate_change_impact

### Priority 2: Phase 3 Security Tools (High Risk)

**Security and Quality (20 tools)**:
- Target: Validate top 5 security-critical tools
- Priority: scan_secrets, scan_security_vulnerabilities, analyze_injection_risks, analyze_authentication, analyze_authorization

**Data Flow (18 tools)**:
- Target: Validate top 5 data flow tools
- Priority: trace_variable_origin, trace_taint_flow, identify_data_leaks, trace_database_reads, trace_api_data_flow

### Priority 3: Phase 4 Runtime/Debugging (Sandbox-Only)

**Runtime (13 tools)**:
- Target: Validate top 3 runtime tools
- Priority: start_application, collect_execution_trace, record_function_calls

**Debugging (11 tools)**:
- Target: Validate top 3 debugging tools
- Priority: analyze_stack_trace, find_error_origin, identify_root_cause

### Priority 4: Phase 5 Engineering/Testing (Worktree/Sandbox)

**Software Engineering (15 tools)**:
- Target: Validate top 3 editing tools
- Priority: edit_file, apply_patch, create_worktree

**Testing (14 tools)**:
- Target: Validate top 3 testing tools
- Priority: run_unit_tests, measure_test_coverage, verify_compilation

## Validation Process

For each tool:

1. **Create test fixture**: Simple, self-contained code that exercises the tool
2. **Write test spec**: YAML with known correct answer
3. **Run test**: Execute and verify output matches expected
4. **Update status**: Mark as validated in tool_completion_status.json
5. **Document**: Add language support and notes

## Test Organization

Tests should be organized by agent under `jarvis-tests/tests/`:

```
jarvis-tests/tests/
├── repository_intelligence/
│   ├── test_detect_languages.yaml
│   ├── test_detect_frameworks.yaml
│   └── ...
├── code_understanding/
│   ├── test_get_type_hierarchy.yaml
│   ├── test_extract_function_contract.yaml
│   └── ...
├── relationship_intelligence/
│   ├── test_build_call_graph.yaml
│   └── ...
├── data_flow/
│   ├── test_trace_variable_origin.yaml
│   └── ...
├── security_quality/
│   ├── test_scan_secrets.yaml
│   └── ...
├── runtime/
│   ├── test_start_application.yaml
│   └── ...
├── debugging/
│   ├── test_analyze_stack_trace.yaml
│   └── ...
├── software_engineering/
│   ├── test_edit_file.yaml
│   └── ...
└── testing_verification/
    ├── test_run_unit_tests.yaml
    └── ...
```

## Example Test Format

```yaml
test_id: REPO-001
tool: detect_languages
agent: repository_intelligence
fixture: simple-python
input:
  repository_path: "fixtures/repositories/simple-python"
expected:
  languages: ["python"]
  confidence: 0.95
evidence_required: true
```

## Estimated Effort

- Priority 1 (18 tools): ~2-3 days
- Priority 2 (10 tools): ~1-2 days
- Priority 3 (6 tools): ~1 day
- Priority 4 (6 tools): ~1 day

**Total**: ~5-7 days for 40 high-priority tools

## Automation Opportunities

1. **Fixture generation**: Auto-create simple fixtures for each language
2. **Test skeleton generation**: Auto-generate YAML templates
3. **Batch execution**: Run all tests and generate report
4. **Status update**: Auto-update tool_completion_status.json

## Shallow Tool Remediation

The 6 shallow tools need either:
- Deep implementation (rewrite with proper analysis)
- Explicit marking as "template-only" in agent prompts
- Removal from curated toolsets until fixed

## Next Steps

1. Write tests for Priority 1 tools (Phase 2 vertical slice)
2. Run existing test suite to get baseline
3. Write tests for Priority 2 tools (Security)
4. Address shallow tools (remediate or mark)
5. Write tests for remaining priorities
6. Full test suite run with all tools
