# JARVIS Comprehensive Testing Suite

## Overview
This is a comprehensive 7-layer testing framework for the JARVIS AI software engineering platform, designed to validate 534 tools across unit, integration, agent capability, multi-agent coordination, end-to-end investigations, and system stress testing.

## Quick Start

### Running Tests
```bash
cd jarvis-tests/test-runner
python3 test_all_tools.py
```

### Checking Test Coverage
```bash
cd jarvis-tests/test-runner
python3 test_registry_check.py
```

### Viewing the Dashboard
```bash
cd jarvis-tests/test-runner
python3 test_dashboard.py
# Open the displayed HTML file in your browser
```

### Validating Ground Truth
```bash
cd jarvis-tests/test-runner
python3 ground_truth_validator.py simple-python
```

## Test Structure

### 7 Testing Layers

**Layer 1: Unit Tests (T01-T09)**
- Happy path, input validation, output validation
- Empty input, boundary conditions, large input
- Complex input, malformed input, dependency failure
- 3,096 tests across 344 tools

**Layer 2: Edge Cases (T10-T15)**
- Timeout, concurrency, security, performance
- Regression, recovery
- 2,064 tests across 344 tools

**Layer 3: Integration Tests**
- Real infrastructure (databases, APIs, Git repositories)
- 12 integration tests

**Layer 4: Agent Capabilities**
- Tests for 12 JARVIS agents
- 5 agent capability tests

**Layer 5: Multi-Agent Coordination**
- Agent delegation, parallel execution, context sharing
- 4 multi-agent scenarios

**Layer 6: End-to-End Investigations**
- Real developer scenarios (understand repo, investigate function, trace API)
- 3 end-to-end tests

**Layer 7: Stress Tests**
- Repository scale, concurrent agents, failure injection
- Resource limits, long-running tasks, runtime volume
- 9 stress tests

## Test Coverage

### Tools by Priority
- **Priority 1**: 67 tools (Analysis, Data Flow, Relationship, Repository Intelligence, Code Understanding) - 100% covered
- **Priority 2**: 52 tools (API/Database, Documentation, Git) - 100% covered
- **Priority 3**: 106 tools (Infrastructure, External Integrations, Language Adapters) - 100% covered
- **Priority 4**: 119 tools (Software Engineering, Testing, Visualization, VR, etc.) - Representative subset covered

### Total Tests: 5,208
- Layer 1: 3,096
- Layer 2: 2,064
- Layer 3: 12
- Layer 4: 5
- Layer 5: 4
- Layer 6: 3
- Layer 7: 9

## Fixture Repositories

### simple-python
Basic Python repository with:
- Complex call graphs (direct and indirect callers)
- Recursion
- Classes and methods
- Cross-package imports
- Ground truth manifest

### complex-typescript
TypeScript repository with:
- Generics and type parameters
- Union types
- Interfaces and classes
- Complex type aliases
- Ground truth manifest

### spring-boot
Java Spring Boot application with:
- REST API endpoints
- JPA database integration
- MVC architecture
- Ground truth manifest

## Integration Test Infrastructure

### Database
- SQLite test database with users, posts, comments tables
- Pre-populated test data

### API
- Flask REST API server (port 5001)
- OpenAPI 3.0 specification
- CRUD endpoints

### Git
- Test repository with multiple branches
- Complex commit history

### Runtime
- Synchronous Python application
- Async Python application with worker pool

## CI/CD Integration

### GitHub Workflows

**test-layer1-2.yml**: Runs on every PR and push
- Validates ground truth
- Runs Layer 1-2 tests
- Generates reports
- Detects regressions
- Comments PR with results

**test-layer3-4.yml**: Runs daily at midnight
- Sets up integration infrastructure
- Starts API server
- Runs Layer 3-4 tests
- Generates reports

**test-layer5-6.yml**: Runs weekly on Sunday
- Runs Layer 5-6 tests (multi-agent, end-to-end)
- Generates reports

**test-layer7.yml**: Runs on tag push (pre-release)
- Runs Layer 7 stress tests
- Release gate check (95% success rate threshold)

**update-dashboard.yml**: Runs every 5 minutes
- Updates test dashboard
- Deploys to GitHub Pages

## Reports

### Test Reports
- JSON reports with detailed results
- HTML reports with visualization
- Stored in `test-reports/`

### Regression Detection
- Compares current run with historical results
- Detects new failures
- Identifies success rate drops
- Tracks performance regressions

### Dashboard
- Web-based HTML dashboard
- Real-time test status
- Historical trends
- Coverage metrics
- Auto-updated every 5 minutes

## File Structure

```
jarvis-tests/
├── .github/workflows/          # CI/CD workflows
├── test-runner/               # Test execution infrastructure
│   ├── test_spec_generator.py
│   ├── test_registry.py
│   ├── test_orchestrator.py
│   ├── test_fixture_manager.py
│   ├── ground_truth_validator.py
│   ├── report_generator.py
│   ├── regression_detector.py
│   ├── test_dashboard.py
│   └── generate_*.py
├── fixtures/                   # Test fixtures
│   ├── repositories/           # Code repositories
│   └── integration-test-infrastructure/
├── test-reports/               # Test results
│   ├── dashboard/
│   └── history/
└── tests/                      # Test specifications
    ├── layer1/
    ├── layer2/
    ├── layer3/
    ├── layer4/
    ├── layer5/
    ├── layer6/
    └── layer7/
```

## Success Metrics

### Coverage
- **Tool Coverage**: 64.4% (344 of 534 tools)
- **Layer Coverage**: 100% (all 7 layers implemented)
- **Test Type Coverage**: 100% (all T01-T15 + agent + integration + stress tests)

### Quality Targets
- **Tool Correctness**: ≥95%
- **Tool Completeness**: ≥90%
- **Precision**: ≥95% (graph tools)
- **Recall**: ≥90% (graph tools)
- **Success Rate**: ≥95% (release gate)

### Performance Targets
- Simple symbol lookup: P95 under 100ms
- Indexed code search: P95 under 300ms
- Direct call graph query: P95 under 500ms
- Small repository indexing: Under 30 seconds
- Basic agent response: P95 under 5 seconds

## Maintenance

### Adding New Tool Tests
1. Add tool to appropriate priority list in `generate_*.py`
2. Run the generator script
3. Validate ground truth if needed
4. Commit changes

### Adding New Fixtures
1. Create repository in `fixtures/repositories/`
2. Add ground-truth.yaml
3. Validate with `ground_truth_validator.py`
4. Update fixture manager if needed

### Updating CI/CD
- Modify workflows in `.github/workflows/`
- Adjust schedules as needed
- Update release gate thresholds

## Documentation

- [Implementation Progress](IMPLEMENTATION_PROGRESS.md) - Detailed implementation status
- [Setup Guide](fixtures/integration-test-infrastructure/SETUP_GUIDE.md) - Integration infrastructure setup
- [Plan](/Users/adarsh/.devin/plans/plan-fc785e10b523e89a.md) - Original 18-week plan

## License

This testing framework is part of the JARVIS project.
