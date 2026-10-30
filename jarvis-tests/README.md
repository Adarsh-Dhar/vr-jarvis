# JARVIS Testing Infrastructure

Comprehensive testing system for the JARVIS AI software engineering platform.

## Overview

This testing infrastructure implements a seven-layer testing pyramid as specified:

1. **Layer 1 - Unit Tests**: Individual tool functions, schemas, and validation
2. **Layer 2 - Tool Correctness**: Correct outputs, edge cases, and error handling
3. **Layer 3 - Integration Tests**: Tools work with real services and data
4. **Layer 4 - Agent Capability Tests**: Whether each agent fulfills its responsibility
5. **Layer 5 - Multi-Agent Coordination**: Delegation, concurrency, and shared context
6. **Layer 6 - End-to-End Tests**: Real developer tasks from request to result
7. **Layer 7 - Stress Tests**: Full system under realistic, complicated, and stressful conditions

## Directory Structure

```
jarvis-tests/
├── test-config/               # Configuration files
│   ├── environments.yaml      # Test environment definitions
│   ├── supported-languages.yaml  # Language support matrix
│   ├── supported-frameworks.yaml  # Framework support matrix
│   └── resource-limits.yaml   # Resource limits per test type
├── fixtures/                  # Test fixtures and repositories
│   ├── repositories/          # Controlled test repositories
│   │   ├── simple-python/     # Basic Python repository
│   │   └── ground-truth.yaml  # Expected answers
│   ├── runtime-traces/        # Sample execution traces
│   ├── database-fixtures/    # Test database schemas
│   ├── api-fixtures/         # Test API definitions
│   └── corrupted-inputs/     # Malformed test inputs
├── tests/                     # Test implementations
│   ├── unit/                  # Layer 1-2 tests
│   │   ├── repository/        # Repository tool tests
│   │   ├── parsing/           # Parser tool tests
│   │   ├── symbols/           # Symbol resolution tests
│   │   ├── relationships/     # Relationship analysis tests
│   │   ├── data-flow/         # Data flow tests
│   │   ├── runtime/           # Runtime intelligence tests
│   │   ├── visualization/     # Visualization tests
│   │   └── security/          # Security tool tests
│   ├── integration/           # Layer 3 tests
│   ├── agent-capabilities/     # Layer 4 tests
│   ├── multi-agent/           # Layer 5 tests
│   ├── end-to-end/            # Layer 6 tests
│   ├── stress/                # Layer 7 tests
│   ├── load/                  # Load testing
│   ├── chaos/                 # Chaos engineering
│   ├── security/              # Security testing
│   └── regression/           # Regression testing
├── benchmarks/                # Performance benchmarks
│   ├── indexing/              # Repository indexing benchmarks
│   ├── graph-queries/         # Graph query benchmarks
│   ├── agent-latency/         # Agent response time benchmarks
│   ├── memory/                # Memory usage benchmarks
│   ├── concurrency/           # Concurrency benchmarks
│   └── runtime-overhead/      # Runtime instrumentation overhead
├── expected-results/           # Ground truth for comparison
│   ├── symbols/               # Expected symbol resolution results
│   ├── call-graphs/           # Expected call graph results
│   ├── data-flows/            # Expected data flow results
│   ├── control-flows/          # Expected control flow results
│   └── agent-outputs/         # Expected agent responses
├── test-reports/              # Generated test reports
└── test-runner/               # Test orchestration system
    ├── test_registry.py       # Test definition registry
    ├── test_orchestrator.py   # Test execution coordinator
    ├── test_fixture_manager.py # Fixture management
    ├── ground_truth_engine.py  # Result comparison engine
    ├── report_generator.py     # Report generation
    └── main.py                # CLI entry point
```

## Running Tests

### Run all tests:
```bash
cd jarvis-tests/test-runner
python main.py
```

### Run specific category:
```bash
python main.py --category unit
python main.py --category integration
python main.py --category stress
```

### Run specific tool tests:
```bash
python main.py --tool find_callers
python main.py --tool parse_source_code
```

### Run by severity:
```bash
python main.py --severity critical
python main.py --severity high
```

### Run specific layer:
```bash
python main.py --layer 1  # Unit tests
python main.py --layer 4  # Agent capability tests
python main.py --layer 7  # Stress tests
```

### List all available tests:
```bash
python main.py --list
```

### Generate reports:
```bash
python main.py --report json    # JSON report
python main.py --report html    # HTML report
python main.py --report both     # Both formats
```

## Test Categories

### Unit Tests (Layer 1-2)
- Repository tools (read_file, list_files, search_code)
- Parsing tools (parse_source_code, extract_ast, extract_symbols)
- Navigation tools (get_symbol_definition, get_call_hierarchy)
- Analysis tools (analyze_control_flow, analyze_data_flow)
- Relationship tools (find_callers, find_callees)
- Runtime tools (collect_execution_trace, record_function_calls)
- Visualization tools (create_graph, calculate_graph_layout)
- Security tools (scan_secrets, scan_vulnerabilities)

### Integration Tests (Layer 3)
- Tools working with real repositories
- Parser integration with actual languages
- Real database operations
- Real test execution
- Real patch application

### Agent Capability Tests (Layer 4)
- Code Understanding Agent
- Relationship Intelligence Agent
- Runtime Intelligence Agent
- Debugging Intelligence Agent
- Security & Quality Agent
- Software Engineering Agent
- Testing & Verification Agent
- Visualization & Spatial Intelligence Agent

### Multi-Agent Coordination Tests (Layer 5)
- Task decomposition and delegation
- Parallel execution
- Sequential execution with dependencies
- Context sharing
- Conflict resolution
- Failure handling
- Duplicate prevention

### End-to-End Tests (Layer 6)
- Understand repository scenario
- Investigate function scenario
- Trace API request scenario
- Investigate bug scenario
- Investigate performance scenario
- Analyze security scenario
- Change function scenario
- Investigate regression scenario
- Explore complex system scenario
- Explain execution scenario

### Stress Tests (Layer 7)
- Repository scale (small to multi-million-line)
- Graph complexity (dense and sparse graphs)
- Concurrent agents
- Runtime volume (large traces, logs)
- Failure injection (database outages, crashes)
- Long-running tasks
- Resource limits (CPU, RAM, disk, network)
- Edge cases (circular dependencies, malformed files)

## Test Format

### YAML Test Format
```yaml
test_id: REL-CALL-001
name: Direct function caller discovery
category: relationship_intelligence
tool: find_callers
description: Verify that the tool identifies all direct callers

fixture:
  repository: simple-python
  target_symbol: target

input:
  depth: 1

expected:
  status: ok
  callers:
    - alpha
    - beta

must_not:
  - gamma
  - delta

checks:
  - correct_callers
  - correct_source_locations
  - valid_response_schema

performance:
  max_duration_ms: 2000

severity: critical
```

### Python Test Format
Python tests use pytest with the following test categories for each tool:
- T01: Happy path
- T02: Input validation
- T03: Output validation
- T04: Empty input
- T05: Boundary conditions
- T06: Large input
- T07: Complex input
- T08: Malformed input
- T09: Dependency failure
- T10: Timeout
- T11: Concurrency
- T12: Security
- T13: Performance
- T14: Regression
- T15: Recovery

## Performance Targets

| Capability | Initial Target |
|-------------|----------------|
| Simple symbol lookup | P95 under 100 ms |
| Indexed code search | P95 under 300 ms |
| Direct call graph query | P95 under 500 ms |
| Small repository indexing | Under 30 seconds |
| Incremental indexing | Under 5 seconds |
| Basic agent response | P95 under 5 seconds |
| Complex investigation | P95 under 60 seconds |
| Graph interaction update | P95 under 100 ms |
| Agent failure recovery | Under 10 seconds |

## Metrics Tracked

1. **Tool correctness**: Percentage of outputs that are correct
2. **Tool completeness**: Percentage of expected results discovered
3. **Precision**: How many reported results are actually correct
4. **Recall**: How many actual results were discovered
5. **Schema validity**: Percentage of outputs matching their contract
6. **Agent task success**: Percentage of assigned tasks completed correctly
7. **Agent tool selection**: Whether the right tools were selected
8. **Evidence accuracy**: Whether claims are supported by real evidence
9. **Hallucination rate**: Unsupported claims presented as facts
10. **Investigation completeness**: Whether all required steps were completed
11. **Latency**: Time taken to produce results
12. **Throughput**: Tasks handled per unit of time
13. **Resource consumption**: CPU, RAM, GPU, storage, network usage
14. **Failure recovery**: Ability to recover after failures
15. **Regression rate**: Previously working capabilities that became broken

## Test Repositories

### simple-python
Basic Python repository with:
- Direct and indirect function calls
- Recursive functions
- Cross-package imports
- Class methods
- Ground truth manifest

### Additional repositories to be added:
- complex-typescript (React/Next.js)
- spring-boot (Java framework)
- rust-project (Rust language)
- cpp-project (C++/Unreal)
- polyglot-monorepo (Multiple languages)
- distributed-system (Microservices)

## Tool Completion Checklist

Each tool must pass:
- [ ] Tool input schema validated
- [ ] Output schema validated
- [ ] Happy-path tests passed
- [ ] Boundary tests passed
- [ ] Error-handling tests passed
- [ ] Integration tests passed
- [ ] Security and permission tests passed
- [ ] Performance targets met
- [ ] Concurrency behavior verified
- [ ] Regression tests passed
- [ ] Evidence and provenance verified
- [ ] Documentation and limitations recorded

## Test Status Levels

- **Untested**: No meaningful test coverage
- **Experimental**: Basic functionality works
- **Validated**: Correctness and integration established
- **Stress-tested**: Load, concurrency, and failure behavior evaluated
- **Production-ready**: All required release criteria passed

## Important Tests

### Critical Tests (Must Pass)
- All tool precision/recall tests
- Multi-agent conflict resolution
- Evidence verification
- Security permission enforcement
- Failure recovery

### High Priority Tests
- Agent tool selection
- Context sharing
- Cross-package relationships
- Error handling
- Performance targets

## Failure Injection Scenarios

The system is tested against:
- Graph database unavailable
- Language parser crashes
- Agent stops responding
- Invalid agent response
- Corrupted graph data
- Runtime trace incomplete
- Repository changes during analysis
- VR connection drops
- Terminal command hangs
- Disk fills up
- Two agents edit same file
- Malicious repository instructions

## Continuous Testing Philosophy

Every capability must have:
- A known input
- An objectively verifiable expected result
- A measurable performance target
- A defined failure behavior

Testing is a continuous process:
1. Test every individual tool
2. Test each agent's ability to use those tools
3. Test agent-to-agent collaboration
4. Test realistic developer investigations
5. Stress-test the entire platform
6. Compare every run against previous results
7. Block releases when critical requirements fail
