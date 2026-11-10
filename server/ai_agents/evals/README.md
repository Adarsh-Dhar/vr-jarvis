# Agent Evaluation Tests

This directory contains golden tasks for validating each agent's behavior.

## Directory Structure

- `golden_tasks/` - YAML files with known correct answers for each agent
  - `repository/` - Repository Intelligence agent tests
  - `code_understanding/` - Code Understanding agent tests
  - `relationship/` - Relationship Intelligence agent tests
  - `data_flow/` - Data Flow Intelligence agent tests
  - `software_engineering/` - Software Engineering agent tests
  - `testing/` - Testing and Verification agent tests
  - `visualization/` - Visualization and Spatial Intelligence agent tests
  - `orchestrator/` - Orchestrator agent tests

## Test Format

Each golden task is a YAML file:

```yaml
test_id: AGENT-XXX-001
agent: <agent_name>
fixture: <fixture_name>
request: <user_request>
expected_tools_include: [list of tools]
expected_findings:
  - claim_contains: <substring>
must_not:
  - <violation_type>
metrics: [tool_selection, evidence_accuracy, hallucination_rate, latency_ms]
```

## Fixtures

- `simple-python` - Basic Python project
- `spring-boot` - Java Spring Boot application
- `intermittent-bug` - Race condition and timing issues
- `polyglot-monorepo` - Multiple languages and frameworks
