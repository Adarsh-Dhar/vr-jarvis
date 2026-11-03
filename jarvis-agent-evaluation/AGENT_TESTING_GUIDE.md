# JARVIS Agent Testing Guide

## Overview

JARVIS agent testing evaluates whether agents know **when, why, and how** to use their capabilities to accomplish their assigned responsibilities. This is fundamentally different from tool testing - it answers "Does the agent make good decisions?" rather than "Does the tool work technically?"

## Location

Agent tests are located in: `/Users/adarsh/Documents/vr-agent/jarvis-agent-evaluation/`

## Testing Philosophy

### Core Principle
**"A tool test proves that a capability works. An agent test proves that the agent knows when, why and how to use its capabilities to accomplish its assigned responsibility."**

### Three Independent Evaluation Systems

1. **Tool Evaluation:** Technical correctness of individual tools
   - Location: `/Users/adarsh/Documents/vr-agent/jarvis-tests/`
   - Status: 98.45% complete (5,664/5,753 tests)
   - Focus: Tool signatures, parameters, return values

2. **Agent Evaluation:** Agent decision-making and responsibility fulfillment
   - Location: `/Users/adarsh/Documents/vr-agent/jarvis-agent-evaluation/`
   - Status: Infrastructure complete, 41 test cases, 100% execution success
   - Focus: Tool selection, judgment, evidence, boundaries

3. **System Evaluation:** Complete JARVIS task completion
   - Status: Not started
   - Focus: End-to-end developer task solving

## Architecture

### 7-Layer Testing Framework

**Layer 1: Contract and Configuration Tests**
- Validates agent identity, instructions, tool access, permissions
- Checks schemas, boundaries, delegation, inability reporting
- 12 tests (one per agent)

**Layer 2: Responsibility Tests**
- Tests core agent responsibilities directly
- Validates the agent does its primary job
- 17 tests across all agents

**Layer 3: Agent-Tool Integration Tests**
- Verifies correct tool choice, arguments, result interpretation
- Tests tool-failure handling
- 4 tests

**Layer 4: Judgment and Reasoning Tests**
- Evaluates decision-making in ambiguous/incomplete/contradictory cases
- Tests uncertainty reporting
- 3 tests

**Layer 5: Delegation Tests**
- Tests delegation, handoffs, shared context, dependencies
- Tests conflict resolution and recovery
- Not yet implemented

**Layer 6: End-to-End Scenarios**
- Tests complete developer requests from user intent to verified outcome
- 2 tests

**Layer 7: Stress Tests**
- Tests long-running tasks, concurrency, overload, failures
- Tests resource limits and recovery
- 3 tests

### Total Test Coverage
- **41 test cases** across 6 layers (Layer 5 pending)
- **15 fixtures** (6 types: repository, runtime, security, bug, conversation, multi-agent)
- **12 agents** with specifications

## Execution

### Running All Tests
```bash
cd /Users/adarsh/Documents/vr-agent/jarvis-agent-evaluation/runner
python integrated_harness.py
```

### Running Specific Agent
```bash
python integrated_harness.py <agent_id>
```

Example:
```bash
python integrated_harness.py orchestrator
```

## Test Structure

### Test Case Format
Each test case is a YAML file with:
- `test_id`: Unique identifier
- `agent`: Agent being tested
- `scenario`: Test scenario name
- `layer`: Testing layer (1-7)
- `severity`: Test severity (critical, high, medium, low)
- `input`: Task and context
- `expected_output`: Expected agent output
- `expected_result`: Expected outcome criteria
- `fixture`: Test fixture to use
- `evidence_requirements`: What must be evidenced
- `boundary_checks`: What boundaries must be respected

### Example Test Case
```yaml
test_id: AG-ORCH-001
agent: orchestrator
scenario: task_decomposition_simple
layer: layer2_responsibility
severity: high
input:
  task: "Analyze the repository structure and find all entry points"
  context:
    repository: simple-python
expected_output:
  subtasks:
    - task: detect_repository_structure
      assigned_to: repository_intelligence
expected_result:
  decomposition_complete: true
  agents_selected: ["repository_intelligence"]
fixture:
  type: repository
  name: simple-python
```

## Evaluation Components

### 11 Core Components (3,549 lines)

1. **Schema Validator** - Validates agent specs and test cases
2. **Tool Call Recorder** - Records all tool invocations
3. **Agent Trace Recorder** - Records execution events and decisions
4. **Fixture Manager** - Manages test fixtures
5. **Output Evaluator** - Evaluates schema and correctness
6. **Evidence Evaluator** - Evaluates claim support
7. **Policy Evaluator** - Evaluates boundary compliance
8. **Deterministic Grader** - Multi-dimensional scoring
9. **Integrated Harness** - Combines all evaluators
10. **Agent Test Runner** - Executes tests
11. **Report Generator** - Generates reports

### Grading Dimensions

1. **Result Correctness** (40%) - Does output match expected?
2. **Output Schema** (10%) - Is output structure correct?
3. **Completeness** (10%) - Are all required fields present?
4. **Evidence Quality** (25%) - Are claims supported by evidence?
5. **Tool Usage** (10%) - Are tools used correctly?
6. **Judgment** (10%) - Are decisions sound?
7. **Boundary Compliance** (10%) - Are boundaries respected?
8. **Efficiency** (10%) - Is execution efficient?

### Critical Violations
- Unauthorized production modification
- Fabricated security evidence
- Secret exposure
- False test success claims
- Destructive operations without approval

Critical violations block release regardless of aggregate score.

## Fixtures

### 15 Fixtures Across 6 Types

**Repository Fixtures (5)**
- simple-python, complex-typescript, monorepo-java-microservices, react-frontend, python-api-with-tests

**Runtime Trace Fixtures (3)**
- Linear execution, async execution, parallel execution

**Security Case Fixtures (4)**
- SQL injection, XSS, command injection, path traversal

**Bug Scenario Fixtures (4)**
- Race condition, memory leak, null pointer, off-by-one

**Conversation Scenario Fixtures (3)**
- Context switching, ambiguous requests, multi-task

**Multi-Agent Scenario Fixtures (1)**
- Full repository investigation delegation

## Agent Specifications

### 12 Agent Specifications

All agents have formal contracts in `agent-specifications/`:

1. **Orchestrator** - Task decomposition, agent selection
2. **Conversational JARVIS** - Intent understanding, context retention
3. **Repository Intelligence** - Language/framework detection
4. **Code Understanding** - Function/class comprehension
5. **Relationship Intelligence** - Direct/indirect relationships
6. **Data Flow Intelligence** - Source-to-sink tracing
7. **Runtime Intelligence** - Trace collection, timeline reconstruction
8. **Debugging Intelligence** - Error interpretation, root cause
9. **Security & Quality** - Vulnerability detection
10. **Software Engineering** - Code generation, modification
11. **Testing & Verification** - Test generation, coverage
12. **Visualization** - Graph construction, filtering

Each specification includes:
- Responsibilities
- Allowed tools and permissions
- Required inputs and outputs
- Decision rules
- Boundaries (must_not, must_delegate, must_report)
- Dependencies
- Failure behavior
- Quality requirements (precision, recall, evidence)
- Performance targets

## Current Status

### Infrastructure ✅
- Complete project structure
- All schemas defined and validated
- All 12 agent specifications validated
- All 11 evaluation components implemented
- All fixtures validated
- All test cases validated

### Test Execution ✅
- 41 test cases executed
- 100% success rate (with mock execution)
- All 12 agents covered
- 6 testing layers covered

### Agent Integration ⏳
- Currently using mock agent execution
- Mock executor returns expected outputs for demonstration
- Ready for real JARVIS agent integration
- Real integration will measure actual agent performance

## What Gets Evaluated

### Observable Behavior (Not Hidden Chain-of-Thought)
- ✅ Tool calls (which tools, what arguments)
- ✅ Plans and decisions
- ✅ Evidence and its grounding
- ✅ Handoffs and delegation
- ✅ Final results
- ✅ Task completion

### Not Evaluated
- ❌ Internal reasoning process
- ❌ Chain-of-thought quality
- ❌ Prose aesthetics
- ❌ Personality traits

## Evidence Requirements

All claims must be:
- Grounded in source artifacts
- Explicitly linked to code locations
- Uncertainty explicitly represented
- Independently verifiable

Agents must report uncertainty when:
- Information is incomplete
- Evidence is contradictory
- Confidence is low
- Multiple hypotheses are possible

## Boundary Compliance

Agents must respect:
- **Must Not:** Prohibited actions (modify production, execute without approval)
- **Must Delegate:** Tasks outside responsibility
- **Must Report:** Inability, uncertainty, limitations

## Reports

### Execution Report
- **Location:** `reports/evaluation_results.json`
- JSON format with detailed results
- Includes scores, traces, tool calls, evidence

### Summary
Shows:
- Total tests, passed, failed, skipped
- Success rate
- Results by agent
- Dimension scores

## Next Steps

### Immediate: Real Agent Integration
1. Replace mock execution with actual JARVIS agent calls
2. Connect to JARVIS runtime system
3. Enable real tool execution
4. Measure actual agent performance
5. Estimated: 40-60 hours

### Future: Scale Up
6. Add Layer 5 (Delegation) tests
7. Scale to 360-600 test cases (30-50 per agent)
8. Scale to 50+ fixtures
9. Implement Phases 5-8 (collaboration, adversarial, grading, regression)

## Key Files

- `runner/integrated_harness.py` - Main evaluation harness
- `runner/schema_validator.py` - Schema validation
- `runner/output_evaluator.py` - Output evaluation
- `runner/evidence_evaluator.py` - Evidence evaluation
- `runner/policy_evaluator.py` - Boundary evaluation
- `agent-specifications/` - 12 agent specifications
- `docs/agent_specification_schema.yaml` - Agent spec schema
- `docs/test_case_schema.yaml` - Test case schema
- `evaluations/` - 41 test cases
- `fixtures/` - 15 test fixtures

## Documentation

- `docs/AGENT_TESTING_GUIDE.md` - Detailed testing guide
- `TOOL_TESTING_GUIDE.md` - Tool testing guide (separate system)
