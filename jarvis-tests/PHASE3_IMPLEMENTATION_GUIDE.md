# Phase 3 Implementation Guide

**Status:** Infrastructure Complete, Execution Pending  
**Date:** 2026-11-01  
**Scope:** 531 tools across 5 waves (+29.5 points)

## Overview

Phase 3 is the largest phase of the test plan, requiring verification of 531 tools. This guide provides the infrastructure and methodology to complete this work systematically.

## Infrastructure Created

### 1. Verified Spec Generator
**File:** `test-runner/verified_spec_generator.py`

Generates verified test specs that meet plan requirements:
- Real inputs from fixtures (never placeholder)
- Exact expected results (not just status: ok)
- Will fail against do-nothing stub
- Will fail against mutants
- Uses temp copy isolation
- Documents limitations

**Archetypes Supported:**
- `read_search` - Files, symbols, graph queries
- `analysis` - Call graphs, data flow, complexity
- `modify` - File edits, git, patches
- `execute` - Builds, tests, processes
- `integration` - GitHub, Docker, Kubernetes

### 2. Batch Verified Generator
**File:** `test-runner/batch_verified_generator.py`

Batch generates specs from configuration files. Includes auto-generation of T02, T04, T08, T12 variants (these need no tool-specific expected results).

### 3. Tool Manifest Format
**Directory:** `test-runner/manifests/`

Each tool needs a manifest file with:
- Tool name and archetype
- Fixture to use
- Input parameters
- Expected exact output
- Must-not conditions
- Performance targets
- Known limitations
- Required test types

**Example:** `manifests/find_callers.yaml` (created)
**Example:** `manifests/extract_symbols.yaml` (created)

### 4. Verified Test Specs
**Directory:** `tests/verified/`

Organized by archetype:
- `read_search/` - Read and search tools
- `analysis/` - Analysis tools
- `modify/` - Modify tools
- `execute/` - Execute tools
- `integration/` - Integration tools

**Reference Spec Created:** `FIND_CALLERS-T01.yaml`

## Wave A: Codebase Intelligence (127 tools)

### Module Breakdown

#### Repository Tools (11 tools)
- list_files, read_file, read_file_range, search_files
- get_file_info, get_repository_tree, index_repository
- update_index, get_index_status, remove_from_index, clear_index

#### Repository Intelligence Tools (18 tools)
- extract_symbols, parse_source_code, extract_ast
- get_file_structure, get_imports, get_exports
- analyze_dependencies, get_file_complexity, detect_duplicates
- get_code_metrics, analyze_naming_conventions, detect_dead_code
- get_function_signatures, get_class_hierarchy, get_module_structure
- find_unused_imports, find_circular_imports

#### Navigation Tools (10 tools)
- navigate_to_definition, navigate_to_references
- find_symbol_at_position, get_symbol_info, search_symbols
- find_definition, find_references, go_to_definition
- peek_definition, symbol_search

#### Code Understanding Tools (16 tools) - PRIORITY
- find_callers, find_callees, get_call_graph
- trace_execution, analyze_data_flow, get_control_flow
- find_function_uses, get_function_context, explain_function
- summarize_code, detect_patterns, find_similar_functions
- get_code_quality_score, identify_smells, suggest_refactoring
- generate_documentation

#### Analysis Tools (15 tools)
- analyze_function, analyze_class, analyze_module
- compute_complexity, compute_maintainability_index
- detect_code_smells, calculate_metrics, generate_report
- analyze_test_coverage, find_bottlenecks, analyze_performance
- detect_security_issues, check_best_practices, generate_recommendations

#### Language Adapters (20 tools)
- Python adapter, TypeScript adapter, Java adapter
- C++ adapter, Rust adapter, Go adapter
- JavaScript adapter, Ruby adapter, PHP adapter
- Swift adapter, Kotlin adapter, C# adapter
- Scala adapter, Dart adapter, Lua adapter, etc.

#### Graph Tools (11 tools)
- create_graph, query_graph, traverse_graph
- get_graph_stats, find_shortest_path, find_connected_components
- compute_centrality, detect_communities, visualize_graph
- export_graph, import_graph

#### Git Tools (7 tools)
- git_status, git_diff, git_log, git_blame
- git_show, git_branch, git_commit

#### Git History Toolkit (3 tools)
- analyze_git_history, find_commit_patterns, trace_file_history

#### Memory Tools (3 tools)
- get_memory_usage, analyze_memory_patterns, detect_memory_leaks

#### Exec Tools (3 tools)
- execute_command, run_process, monitor_process

#### Scene Tools (8 tools)
- create_scene, add_node, add_edge, remove_node
- remove_edge, update_node, update_edge, clear_scene

#### Control Tools (2 tools)
- start_agent, stop_agent

## Methodology for Completing Wave A

### Step 1: Create Manifests for Priority Tools
Start with the 16 Code Understanding tools (most foundational):

1. **find_callers** ✅ Manifest created
2. **find_callees** - Create manifest
3. **get_call_graph** - Create manifest
4. **trace_execution** - Create manifest
5. **analyze_data_flow** - Create manifest
6. **get_control_flow** - Create manifest
7. **find_function_uses** - Create manifest
8. **find_function_context** - Create manifest
9. **explain_function** - Create manifest
10. **summarize_code** - Create manifest
11. **detect_patterns** - Create manifest
12. **find_similar_functions** - Create manifest
13. **get_code_quality_score** - Create manifest
14. **identify_smells** - Create manifest
15. **suggest_refactoring** - Create manifest
16. **generate_documentation** - Create manifest

**How to create a manifest:**
1. Analyze the tool's actual behavior
2. Test against simple-python fixture
3. Record exact output
4. Document limitations
5. Save as `manifests/{tool_name}.yaml`

### Step 2: Generate Specs for Priority Tools
For each manifest, run:
```bash
cd jarvis-tests/test-runner
python3 verified_spec_generator.py \
  --tool {tool_name} \
  --archetype analysis \
  --fixture simple-python \
  --manifest manifests/{tool_name}.yaml
```

### Step 3: Generate Variants
Use the batch generator to auto-generate T02, T04, T08, T12 variants:
```bash
python3 batch_verified_generator.py \
  --config batch_config_wave_a.yaml
```

### Step 4: Test Against Real Tools
**This requires access to the actual JARVIS tool implementations.**

For each spec:
1. Run against real tool - should pass
2. Run against do-nothing stub - should fail
3. Run against mutants - should fail
4. Verify temp copy isolation
5. Record results

### Step 5: Triage Failures
For each failing spec:
- Determine if it's a tool bug or bad expectation
- Fix the right side
- Re-test

### Step 6: Achieve 80% Mutation Kill Rate
Run mutation testing:
```bash
python3 mutation_tester.py --tool {tool_name}
```
Ensure at least 80% of mutants are killed.

### Step 7: Mark as Verified
Update `tool_completion_status.json`:
```bash
python3 generate_tool_completion.py
```

## Repeat for Remaining Tools

After completing the 16 priority tools, repeat for:
- Repository Tools (11)
- Repository Intelligence Tools (18)
- Navigation Tools (10)
- Analysis Tools (15)
- Language Adapters (20)
- Graph Tools (11)
- Git Tools (7)
- Git History Toolkit (3)
- Memory Tools (3)
- Exec Tools (3)
- Scene Tools (8)
- Control Tools (2)

## Wave Completion Criteria

Wave A is complete when:
1. ✅ All 127 tools have verified specs
2. ✅ All specs pass against real tools
3. ✅ All specs fail against do-nothing stub
4. ✅ All specs fail against 80%+ of mutants
5. ✅ All specs use temp copy isolation
6. ✅ All limitations are documented
7. ✅ Stub gate shows zero passing specs for these tools

## Estimated Timeline

**Per tool:** 30-60 minutes (manifest creation + testing + mutation)
**Priority 16 tools:** 8-16 hours (1-2 days)
**Remaining 111 tools:** 55-111 hours (1-2 weeks)
**Total Wave A:** 2-3 weeks with 1 engineer

**Parallelizable:** Multiple engineers can work on different tool groups simultaneously.

## Dependencies

**Required:**
- Access to actual JARVIS tool implementations
- Test execution environment
- Mutation testing infrastructure

**Optional (for now):**
- CI integration (Phase 2 components)
- Live tool access (can use recorded responses for integration tools)

## Next Steps

1. **Immediate:** Create manifests for the remaining 15 priority Code Understanding tools
2. **Short-term:** Generate specs for all 16 priority tools
3. **Medium-term:** Complete all 127 tools in Wave A
4. **Long-term:** Repeat for Waves B-E

## Success Metrics

- Verified tools: 0 → 127
- Scoreboard impact: +7.1 points
- Mutation kill rate: ≥80% per tool
- Stub gate: zero passing specs for verified tools

## Risks and Mitigations

**Risk:** No access to actual tool implementations
**Mitigation:** Create specs based on tool documentation and expected behavior; defer actual testing until tool access is available

**Risk:** 531 tools is too many to do manually
**Mitigation:** Use archetype generators; automate manifest creation where possible; focus on priority tools first

**Risk:** Mutation testing may be slow
**Mitigation:** Run mutation testing in parallel; use selective mutation strategies

## Conclusion

The infrastructure for Phase 3 is complete. The remaining work is:
1. Create manifests for 531 tools
2. Generate verified specs
3. Test against real tools
4. Achieve 80% mutation kill rate

This is a significant effort (estimated 2-4 months with 2-3 engineers) but the infrastructure and methodology are now in place to execute it systematically.
