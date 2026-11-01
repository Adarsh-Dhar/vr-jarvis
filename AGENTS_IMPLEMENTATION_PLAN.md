# JARVIS Agents Implementation Plan

**Build 24 to Production**
**Status: Planning Phase**

---

## Executive Summary

This plan transforms the existing 533 tools in `server/ai_agents/tools/` into 12 working LLM agents plus the existing Evidence Critic. The current state is:

- **533 tools** exported from `ai_agents` (552 public functions, 551 with `tool_context`, 541 wrapped in `@safe`)
- **6 LLM agents** wired in 4 pipelines under one router: `investigator`, `critic`, `impact` (4 parts), `fix` (3 parts), `briefing`, `scene_director`
- **~20-30 tools** actually used by these agents (from older toolkits: `graph_tools`, `repository_tools`, `navigation_tools`, `analysis_tools`, `scene_tools`)
- **New per-agent toolkits** exist but are not wired to any agent
- **17 duplicate tool names** between `visualization_spatial_tools.py` and `vr_specific_tools.py`
- **No agent evaluations** (`ai_agents/evals/` is empty)
- **Test suite broken** on build 22 (5,308 of 5,402 runs errored; 5,684 of 5,738 specs use placeholder inputs)

The plan builds agents in 7 phases, with exit gates after each phase where specific tests must pass before proceeding.

---

## Design Decisions

### D1: Twelve Agents, Not Thirty-Eight
The 38 responsibilities in the inventory are capabilities, not agents. Deterministic tools handle:
- Parsing, symbol resolution, call graphs, profiling
- File system operations
- Git operations
- Build/test execution

Agents decide **which tool to call** and **interpret the result**.

### D2: One Delegation Mechanism - ADK `AgentTool`
- **Orchestrator** calls each specialist as an `AgentTool` and gets structured results
- Enables parallel execution and result merging
- Keep existing 4 pipelines as fast paths for demo flows (`investigate`, `impact`, `fix`, `briefing`)
- Rebuild them from new agents later
- **Retire** simulated helpers in `orchestrator_tools.py` (`delegate_task`, `run_agents_parallel`, `start_agent`, `send_message_to_agent`) or convert to thin wrappers over real agent registry

### D3: Curated Toolsets
- Each agent gets **8-22 tools** (176 unique tools total)
- Too many tools in one prompt degrades tool choice and increases cost
- Startup check verifies every listed tool exists and no agent holds a tool above its permission ceiling

### D4: One Findings Contract
Every specialist records findings in the same shape:
```python
{
  "agent": "relationship",
  "claim": "deleteAccount is called only from DELETE /account/:id",
  "status": "confirmed",  # confirmed | inferred | unresolved
  "confidence": 0.95,
  "evidence": [
    {
      "file": "routes/account.ts",
      "start": 12,
      "end": 15,
      "node_id": "route.delete",
      "tool": "find_callers"
    }
  ],
  "unknowns": ["callers through dynamic dispatch"]
}
```

Only findings verified by the critic reach the VR scene or spoken answer.

### D5: Permission Tiers and Independence
- **Read/analyze tools**: run automatically
- **Execute tools**: run only in sandbox worktree
- **Software Engineering agent**: only agent that can change files, only in worktree
- **Testing and Verification agent**: can run but cannot edit
- **Committing**: only through server's `/approve` endpoint after 2-second pinch hold
- **Separation of concerns**: agent that makes change is never the one that judges it

### D6: Validation Gate
A tool is added to an agent's toolset **only after**:
- It has a real-input test with known correct answer
- Until then: marked experimental, agent prompt says output is unverified

### D7: Deterministic Facts, AI Interpretation
Prompts require agents to:
- Report a fact **only when a tool returned it**
- Say what is inferred
- Say what is unknown
- Tools that cannot resolve return `unresolved`, never a guess

---

## Phase 0: Tool Trustworthiness (Before Any Agent)

**Goal**: Make the 533 tools trustworthy before building agents on top.

### 0.1 Resolve Duplicate Tool Names
**Problem**: 17 tool names defined twice in `visualization_spatial_tools.py` and `vr_specific_tools.py`

**Action**:
- `visualization_spatial_tools.py` keeps canonical version
- `vr_specific_tools.py` delegates to canonical or renames to avoid conflict
- Examples: `select_code_element`, `request_visualization`, `pin_investigation`

**Verification**: `python -c 'import ai_agents'` succeeds without name collision warnings

### 0.2 Fix Test Runner
**Current Issues** (from build 22):
- Runner passes `tool_context` twice
- Does not accept string entries in `must_not`
- Counts specs with `placeholder` input as 'pass' instead of 'not validated'

**Actions**:
1. Fix double `tool_context` parameter passing
2. Support string entries in `must_not` field
3. Mark specs with `placeholder` input as `status: not_validated`
4. Run suite and record real pass/fail counts per tool

**Exit Gate**: Test suite runs and reports accurate pass/fail counts

### 0.3 Add Import Check
**Problem**: Earlier builds broke `import ai_agents` when tools were renamed but agents still imported old names

**Action**: Add CI check:
```bash
python -c 'import ai_agents'
```

### 0.4 Validate Toolsets
Create `server/ai_agents/agents/toolsets.py` with curated tool mappings:
```python
TOOLSETS = {
  "orchestrator": [list of tools],
  "conversational": [list of tools],
  # ... for all 12 agents
}
```

Add validation test that:
- Every tool name in `toolsets.py` exists in `tools/__init__.py`
- No duplicate tool names within an agent
- No tool exceeds agent's permission ceiling

**Exit Gate**: Validation test passes

### 0.5 Populate Tool Completion Status
Run test suite and generate `tool_completion_status.json`:
```json
{
  "get_symbol_definition": {
    "status": "validated",
    "language_support": ["python", "typescript", "java"],
    "last_validated": "2026-11-01",
    "test_count": 5,
    "pass_rate": 1.0
  },
  "analyze_cryptography": {
    "status": "experimental",
    "language_support": ["python"],
    "issues": ["shallow keyword matching detected"],
    "last_validated": null
  }
}
```

### 0.6 Deepen Shallow Tools
Six tools flagged as shallow keyword matching in earlier audits:
- `analyze_cryptography`
- `detect_code_smells`
- `identify_technical_debt`
- `refactor_function`
- `implement_interface`
- `build_dependency_graph`

**Action**: Either deepen implementation or mark as experimental with clear warnings

### 0.7 Fix Server Path
**Problem**: `uvicorn server.jarvis_server:app` needs to start from repo root because server imports `ai_agents` as top-level package

**Action**: Ensure `server/` is on Python path when starting server

**Exit Gate for Phase 0**:
- ✅ `import ai_agents` succeeds
- ✅ Test suite runs with accurate counts
- ✅ 176 curated tools each have at least one real-input test with known answer
- ✅ `tool_completion_status.json` populated
- ✅ No duplicate tool names
- ✅ Server starts from repo root

---

## Phase 1: Agent Framework

**Goal**: Build shared foundation for all agents.

### 1.1 Create `server/ai_agents/agents/base.py`
Factory function `make_specialist(spec)` that builds `LlmAgent` from spec:

```python
def make_specialist(spec: AgentSpec) -> LlmAgent:
    """
    Builds an LlmAgent from a specification.

    Args:
        spec: AgentSpec with fields:
            - name: str
            - instruction_template: str (with {context} placeholders)
            - toolset: List[Callable]
            - output_key: str (state key for result)
            - tool_budget: int (max tool calls per turn)
            - permission_ceiling: str (read | execute | write)
            - model: str (optional, defaults to config.MODEL)

    Returns:
        LlmAgent instance
    """
```

### 1.2 Create `server/ai_agents/agents/toolsets.py`
Define curated toolsets for all 12 agents (see Section 4 for exact tool lists).

Add validation at import time:
```python
def _validate_toolsets():
    for agent_name, tools in TOOLSETS.items():
        # Check all tools exist
        # Check no duplicates
        # Check permission ceiling
```

### 1.3 Create `server/ai_agents/agents/findings.py`
Findings schema and `record_finding` tool:

```python
from pydantic import BaseModel

class Evidence(BaseModel):
    file: str
    start: int
    end: int
    node_id: str
    tool: str

class Finding(BaseModel):
    agent: str
    claim: str
    status: Literal["confirmed", "inferred", "unresolved"]
    confidence: float
    evidence: List[Evidence]
    unknowns: List[str]

def record_finding(
    agent: str,
    claim: str,
    status: str,
    confidence: float,
    evidence: List[Dict],
    unknowns: List[str],
    tool_context: ToolContext
) -> str:
    """Records a finding to state['findings'] list"""
```

### 1.4 Create `server/ai_agents/agents/registry.py`
Single dictionary of all agents:

```python
from google.adk.agents import Agent

AGENTS: Dict[str, Agent] = {}

def register_agent(name: str, agent: Agent):
    AGENTS[name] = agent

def get_agent(name: str) -> Agent:
    return AGENTS[name]

def list_agents() -> List[str]:
    return list(AGENTS.keys())

def get_agent_status(name: str) -> Dict:
    """Return agent status for server endpoints"""
```

### 1.5 Extend `callbacks.py`
Add:
- `after_tool_callback`: copies evidence from tool result into state
- `before_tool_callback`: applies permission tier of calling agent
- Per-tool timeout
- Error normalization

```python
def after_tool_callback(callback_context, tool_result):
    """Copy evidence from tool result into state['evidence']"""
    state = callback_context.state
    if tool_result.get('evidence'):
        state['evidence'].extend(tool_result['evidence'])

def before_tool_callback(tool, args, tool_context):
    """Apply permission tier of calling agent"""
    agent_name = tool_context.state.get('calling_agent')
    permission = AGENT_PERMISSIONS.get(agent_name, 'read')
    tool_permission = TOOL_PERMISSIONS.get(tool.name, 'read')

    if tool_permission > permission:
        return {
            'status': 'blocked',
            'reason': f'Tool {tool.name} requires {tool_permission} permission, agent has {permission}'
        }
    return None
```

### 1.6 Update State Keys
Extend `state.py` with new keys:
```python
KEYS = [
    # ... existing keys ...
    'plan',           # Orchestrator's investigation plan
    'findings',       # Append-only list of all findings
    'result_repository',     # Repository Intelligence output
    'result_code_understanding',  # Code Understanding output
    'result_relationship',  # Relationship Intelligence output
    'result_data_flow',     # Data Flow Intelligence output
    'result_runtime',       # Runtime Intelligence output
    'result_debugging',     # Debugging Intelligence output
    'result_security',      # Security and Quality output
    'result_software_eng',  # Software Engineering output
    'result_testing',       # Testing and Verification output
    'result_visualization', # Visualization output
    'task_log',       # History of tasks and their status
]

PER_TURN_KEYS = [
    # Keys cleared each turn
    'result_repository', 'result_code_understanding', 'result_relationship',
    'result_data_flow', 'result_runtime', 'result_debugging',
    'result_security', 'result_software_eng', 'result_testing',
    'result_visualization'
]
```

### 1.7 Create `server/ai_agents/evals/` Structure
```
evals/
├── golden_tasks/
│   ├── repository/
│   ├── code_understanding/
│   ├── relationship/
│   ├── data_flow/
│   ├── runtime/
│   ├── debugging/
│   ├── security/
│   ├── software_engineering/
│   ├── testing/
│   ├── visualization/
│   └── orchestrator/
├── runner.py
└── metrics.py
```

**Exit Gate for Phase 1**:
- ✅ Dummy specialist can be created from spec
- ✅ Dummy specialist calls one tool
- ✅ Dummy specialist records a finding with evidence
- ✅ Dummy specialist is blocked from tool above its permission ceiling
- ✅ Registry lists agents
- ✅ Evals directory structure exists

---

## Phase 2: First Vertical Slice

**Goal**: Build end-to-end flow with 7 agents.

### Agents to Build:
1. **Orchestrator** (Agent 1)
2. **Repository Intelligence** (Agent 3)
3. **Code Understanding** (Agent 4)
4. **Relationship Intelligence** (Agent 5)
5. **Visualization and Spatial Intelligence** (Agent 12)
6. **Conversational JARVIS** (Agent 2)
7. **Evidence Critic** (existing, adapt to new findings format)

### 2.1 Build Repository Intelligence Agent
**File**: `server/ai_agents/agents/repository_intelligence.py`

**Tools** (19):
- `index_repository`, `incremental_index_repository`
- `detect_languages`, `detect_frameworks`, `detect_build_system`, `detect_project_type`, `detect_package_manager`
- `analyze_repository_structure`, `analyze_monorepo`
- `identify_entry_points`, `identify_external_services`, `identify_generated_files`
- `detect_repository_changes`, `analyze_dependencies_manifest`
- `list_files`, `read_file`, `search_code`
- `get_repository_metadata`, `get_changed_files`

**Instruction Template**:
```
You are the Repository Intelligence specialist. You understand the codebase structure,
languages, frameworks, build system, and what changed.

Context:
- Repository path: {repo_path}
- Active task: {active_task}

Process:
1. Detect languages, frameworks, build system
2. Analyze repository structure and entry points
3. Identify external services and generated files
4. Detect recent changes if relevant

Rules:
- Report only what tools return
- Mark inferred information as inferred
- Use record_finding for all structural claims

Return to state['result_repository']
```

**Output Key**: `result_repository`

### 2.2 Build Code Understanding Agent
**File**: `server/ai_agents/agents/code_understanding.py`

**Tools** (22):
- `get_symbol_definition`, `get_symbol_references`, `get_symbol_hover_info`
- `get_type_hierarchy`, `get_imports`, `get_exports`, `get_scope_information`
- `parse_source_code`, `extract_symbols`, `resolve_types`
- `explain_function`, `explain_class`, `explain_module`, `explain_condition`
- `extract_function_contract`, `identify_side_effects`, `identify_hidden_assumptions`
- `infer_code_intent`, `trace_function_logic`, `analyze_control_flow`
- `extract_docstrings`, `read_file_range`

**Instruction Template**:
```
You are the Code Understanding specialist. You explain what symbols are, what they do,
their contracts, side effects, and failure conditions.

Context:
- Selected node: {selection}
- Active task: {active_task}

Process:
1. Get symbol definition and references
2. Parse source code and extract symbols
3. Explain function/class/module behavior
4. Identify side effects and hidden assumptions
5. Extract function contract

Rules:
- Every statement must cite file and line range from tool result
- Use record_finding for all behavioral claims
- If you cannot find evidence, say so plainly

Return to state['result_code_understanding']
```

**Output Key**: `result_code_understanding`

### 2.3 Build Relationship Intelligence Agent
**File**: `server/ai_agents/agents/relationship_intelligence.py`

**Tools** (17):
- `find_callers`, `find_callees`, `find_indirect_callers`, `trace_call_chain`
- `build_call_graph`, `build_dependency_graph`, `find_dependents`
- `find_all_paths_between_symbols`, `find_circular_dependencies`
- `analyze_architecture_boundaries`, `calculate_change_impact`
- `find_interface_implementations`
- `trace_cross_module_relationships`, `trace_cross_service_relationships`
- `discover_api_endpoints`, `map_api_to_database`, `trace_request_lifecycle`

**Instruction Template**:
```
You are the Relationship Intelligence specialist. You understand callers, callees,
dependencies, architecture, API-to-database paths, and change impact.

Context:
- Selected node: {selection}
- Active task: {active_task}

Process:
1. Find callers and callees
2. Build call and dependency graphs
3. Trace relationships across modules and services
4. Calculate change impact if relevant
5. Map API endpoints to database

Rules:
- Report unresolved edges (dynamic dispatch, callbacks) explicitly with confidence
- Use record_finding for all relationship claims
- Mark inferred relationships as inferred

Return to state['result_relationship']
```

**Output Key**: `result_relationship`

### 2.4 Build Visualization Agent
**File**: `server/ai_agents/agents/visualization.py`

**Tools** (20):
- `highlight_vr_path`, `dim_unrelated`, `focus_camera`, `open_code_panel`, `set_edge_style`
- `show_ghost_diff`, `show_test_badges`
- `create_graph`, `visualize_call_graph`, `visualize_change_impact`, `visualize_data_flow`
- `visualize_test_coverage`
- `expand_graph_node`, `collapse_graph_node`, `isolate_subgraph`, `filter_graph`
- `calculate_graph_clusters`, `summarize_graph`
- `get_current_selection`, `verify_citations`

**Instruction Template**:
```
You are the Visualization and Spatial Intelligence specialist. You turn verified
findings into scene commands and graphs.

Context:
- Findings from other agents: {findings}
- Current selection: {selection}

Process:
1. Review verified findings from critic
2. Generate scene commands to highlight relevant nodes
3. Create graphs for relationships, data flow, or impact
4. Apply visualization filters and layouts

Rules:
- Only draw nodes and edges that exist in verified findings
- Never fabricate graph elements
- Rendering is done by Unity, not by you

Return to state['result_visualization']
```

**Output Key**: `result_visualization`

### 2.5 Build Conversational Agent
**File**: `server/ai_agents/agents/conversational.py`

**Tools** (8):
- `answer_code_question`, `explain_visualization`, `summarize_investigation`
- `retrieve_conversation_context`, `retrieve_investigation_context`
- `ask_clarifying_question`, `compare_code_elements`, `manage_conversation_preferences`

**Instruction Template**:
```
You are the Conversational JARVIS. You talk to the developer, explain verified findings,
and ask one clarifying question when needed.

Context:
- Verified findings: {verified_answer}
- Conversation history: {conversation_context}

Process:
1. Read only critic-verified findings
2. Explain the result in at most two sentences
3. If request is unclear, ask one short clarifying question
4. Use retrieve_conversation_context for context

Rules:
- Spoken reply is at most two sentences
- Never fabricate information
- Ask only one clarifying question at a time

Return to state['result_conversational']
```

**Output Key**: `result_conversational`

### 2.6 Build Orchestrator Agent
**File**: `server/ai_agents/agents/orchestrator.py`

**Tools**:
- `classify_request`, `understand_user_intent`, `create_investigation_plan`
- `check_task_completion`, `merge_agent_results`, `resolve_conflicting_findings`
- `request_more_evidence`, `request_approval`
- Other specialists as `AgentTool`s

**Instruction Template**:
```
You are the Orchestrator. You plan, delegate, merge results, and decide what to ask next.

Context:
- User request: {user_request}
- Current selection: {selection}
- Available agents: {available_agents}

Process:
1. Classify the request type
2. Create investigation plan
3. Delegate to appropriate specialists (parallel when independent)
4. Merge agent results
5. Resolve conflicting findings
6. Check task completion

Rules:
- Never answer a code question from your own knowledge
- Always delegate to specialists
- Use AgentTool for delegation
- Store plan in state['plan']

Return to state['result_orchestrator']
```

**Output Key**: `result_orchestrator`

### 2.7 Adapt Evidence Critic
Update `critic.py` to work with new findings format:

```python
TEMPLATE = '''
You are the Grounding Critic. You check findings against evidence.

Findings to review: {findings}
Evidence: {evidence}

Process:
1. Collect every claim with its node ids
2. Call verify_citations on all node ids
3. Remove or downgrade unsupported claims
4. A claim marked confirmed may rely only on confirmed edges
5. Add no new claims

Return findings with verdict (pass, downgraded, rejected)
'''
```

### 2.8 Wire the Pipeline
Create new pipeline in `agent.py`:

```python
from .agents.orchestrator import orchestrator
from .agents.repository_intelligence import repository_agent
from .agents.code_understanding import code_understanding_agent
from .agents.relationship_intelligence import relationship_agent
from .agents.visualization import visualization_agent
from .agents.conversational import conversational_agent
from .agents.critic import make_critic

# Build Phase 2 pipeline
phase2_specialists = ParallelAgent(
    name='phase2_specialists',
    description='Run Repository, Code Understanding, and Relationship in parallel',
    sub_agents=[repository_agent, code_understanding_agent, relationship_agent]
)

phase2_pipeline = SequentialAgent(
    name='phase2_pipeline',
    description='First vertical slice: explain function and show connections',
    sub_agents=[
        orchestrator,
        phase2_specialists,
        make_critic('phase2_critic', 'findings'),
        visualization_agent,
        conversational_agent
    ]
)
```

### 2.9 Write Golden Tasks
Create YAML golden tasks in `evals/golden_tasks/`:

**Example**: `evals/golden_tasks/code_understanding/explain_function.yaml`
```yaml
test_id: AGENT-CU-001
agent: code_understanding
fixture: simple-python
request: Explain what the target() function does
expected_tools_include: [get_symbol_definition, explain_function, parse_source_code]
expected_findings:
  - claim_contains: returns
  - claim_contains: parameters
must_not:
  - fabricated_symbol
  - uncited_claim
metrics: [tool_selection, evidence_accuracy, hallucination_rate, latency_ms]
```

**Fixtures**:
- `simple-python`: Basic Python project
- `spring-boot`: Java Spring Boot application

### 2.10 Run Golden Tasks
Implement `evals/runner.py` to execute golden tasks and measure:
- Tool selection accuracy
- Evidence accuracy
- Hallucination rate
- Latency

**Exit Gate for Phase 2**:
- ✅ Golden tasks pass on `simple-python` and `spring-boot`
- ✅ Zero uncited claims
- ✅ Every scene command refers to a node that exists
- ✅ p95 latency under 60 seconds for complex request
- ✅ Orchestrator successfully delegates to specialists
- ✅ Specialist results merge correctly
- ✅ Critic catches hallucinations

---

## Phase 3: Data Flow and Security and Quality

**Goal**: Add agents for data flow tracing and security/quality analysis.

### 3.1 Build Data Flow Intelligence Agent
**File**: `server/ai_agents/agents/data_flow.py`

**Tools** (16):
- `trace_variable_origin`, `trace_variable_usage`, `trace_variable_modifications`
- `trace_parameter_flow`, `trace_return_value_flow`, `trace_taint_flow`
- `trace_transformations`, `trace_cross_function_flow`, `trace_cross_service_flow`
- `trace_database_reads`, `trace_database_writes`, `trace_api_data_flow`
- `trace_file_operations`, `trace_state_changes`, `build_data_flow_graph`
- `identify_data_leaks`, `identify_data_sinks`, `identify_data_sources`, `identify_validation_gaps`

**Instruction Template**:
```
You are the Data Flow Intelligence specialist. You trace where data comes from,
how it changes, and where it ends up.

Context:
- Selected node: {selection}
- Active task: {active_task}

Process:
1. Trace variable origin and usage
2. Trace parameter and return value flow
3. Trace transformations across functions
4. Identify data sources, sinks, and leaks
5. Trace database and API data flow

Rules:
- Report only what tools return
- Mark inferred paths as inferred
- Use record_finding for all data flow claims

Return to state['result_data_flow']
```

### 3.2 Build Security and Quality Agent
**File**: `server/ai_agents/agents/security_quality.py`

**Tools** (16):
- `scan_secrets`, `scan_vulnerabilities`, `scan_security_vulnerabilities`, `scan_dependency_vulnerabilities`
- `analyze_authentication`, `analyze_authorization`, `analyze_permissions`, `analyze_input_validation`
- `analyze_injection_risks`, `analyze_cryptography`, `trace_sensitive_data`, `analyze_attack_surface`
- `calculate_complexity`, `calculate_cognitive_complexity`, `detect_code_smells`, `detect_duplicates`
- `detect_anti_patterns`, `analyze_maintainability`, `analyze_testability`, `analyze_violations`
- `identify_technical_debt`, `generate_security_report`, `generate_quality_report`

**Instruction Template**:
```
You are the Security and Quality specialist. You find vulnerabilities, secrets,
injection risks, authorization gaps, complexity, duplication, and debt.

Context:
- Repository path: {repo_path}
- Active task: {active_task}

Process:
1. Scan for secrets and vulnerabilities
2. Analyze authentication, authorization, input validation
3. Analyze injection risks and attack surface
4. Calculate complexity and detect code smells
5. Identify technical debt

Rules:
- A security finding must name source, path, and sink
- Mark inferred findings as inferred
- Use record_finding for all security/quality claims

Return to state['result_security']
```

### 3.3 Create Security Challenge Fixture
Create test fixture `jarvis-tests/fixtures/repositories/security-challenge/` with:
- Planted vulnerabilities (SQL injection, XSS, command injection)
- Hardcoded secrets
- Authorization bypasses
- Input validation gaps

### 3.4 Write Golden Tasks
Create golden tasks for security-challenge fixture:
```yaml
test_id: AGENT-SEC-001
agent: security_quality
fixture: security-challenge
request: Find all security vulnerabilities
expected_findings:
  - claim_contains: SQL injection
  - claim_contains: hardcoded secret
  - claim_contains: source
  - claim_contains: path
  - claim_contains: sink
must_not:
  - false_positive
  - missing_source_path_sink
metrics: [vulnerability_detection_rate, false_positive_rate, latency_ms]
```

### 3.5 Run Golden Tasks
**Exit Gate for Phase 3**:
- ✅ Every planted vulnerability found with source, path, and sink
- ✅ Every planted secret found
- ✅ False-positive rate recorded and acceptable (< 20%)
- ✅ Complexity metrics accurate
- ✅ Code smells correctly identified

---

## Phase 4: Runtime and Debugging

**Goal**: Add agents for runtime analysis and debugging.

### 4.1 Build Runtime Intelligence Agent
**File**: `server/ai_agents/agents/runtime.py`

**Tools** (13):
- `start_application`, `stop_application`, `attach_runtime_profiler`, `attach_debugger`
- `collect_execution_trace`, `record_function_calls`, `record_function_arguments`, `record_function_returns`
- `record_execution_timing`, `record_variable_state`, `record_memory_usage`, `record_cpu_usage`
- `record_network_activity`, `record_database_activity`, `record_async_tasks`, `record_thread_activity`
- `capture_application_logs`, `capture_runtime_events`, `compare_execution_traces`, `replay_execution_trace`

**Instruction Template**:
```
You are the Runtime Intelligence specialist. You understand what actually happened
when the code ran.

Context:
- Sandbox worktree: {worktree}
- Active task: {active_task}

Process:
1. Start application in sandbox
2. Collect execution trace
3. Record function calls, timing, memory, CPU
4. Capture application logs
5. Compare execution traces if needed

Rules:
- Separate measured results from estimates
- Never run outside sandbox worktree
- Use record_finding for all runtime claims

Return to state['result_runtime']
```

**Permission Ceiling**: execute (sandbox only)

### 4.2 Build Debugging Intelligence Agent
**File**: `server/ai_agents/agents/debugging.py`

**Tools** (11):
- `capture_exception`, `analyze_stack_trace`, `find_error_origin`, `trace_error_propagation`
- `identify_failure_path`, `set_breakpoint`, `remove_breakpoint`, `step_into`, `step_over`, `step_out`
- `inspect_variables`, `evaluate_debug_expression`, `inspect_call_stack`, `watch_expression`
- `reproduce_bug`, `compare_success_failure`, `identify_root_cause`, `suggest_debugging_actions`

**Instruction Template**:
```
You are the Debugging Intelligence specialist. You find the root cause of errors
and unexpected behavior.

Context:
- Error or stack trace: {error_context}
- Sandbox worktree: {worktree}
- Active task: {active_task}

Process:
1. Analyze stack trace
2. Find error origin and trace propagation
3. Identify failure path
4. Reproduce bug if possible
5. Compare success vs failure execution
6. Identify root cause

Rules:
- Root cause is stated as hypothesis with evidence for and against
- Until reproduction confirms, mark as hypothesis
- Use record_finding for all debugging claims

Return to state['result_debugging']
```

**Permission Ceiling**: execute (sandbox only)

### 4.3 Create Intermittent Bug Fixture
Create test fixture with known intermittent bug:
- Race condition
- Timing-dependent error
- State-dependent failure

### 4.4 Write Golden Tasks
```yaml
test_id: AGENT-DBG-001
agent: debugging
fixture: intermittent-bug
request: Why does this fail sometimes?
expected_findings:
  - claim_contains: race condition
  - claim_contains: timing
  - status: hypothesis  # until reproduction confirms
must_not:
  - certain_root_cause_without_reproduction
metrics: [root_cause_identification, evidence_quality, latency_ms]
```

### 4.5 Implement Sandbox Service
Ensure `create_sandbox`, `execute_in_sandbox`, `destroy_sandbox` from `infrastructure_services.py` work correctly.

**Exit Gate for Phase 4**:
- ✅ Agents reach known root cause on intermittent bug fixture
- ✅ Agents state what remains uncertain
- ✅ Runtime measurements accurate
- ✅ Sandbox isolation works
- ✅ No execution outside sandbox

---

## Phase 5: Software Engineering and Testing and Verification

**Goal**: Add agents for code changes and independent verification.

### 5.1 Build Software Engineering Agent
**File**: `server/ai_agents/agents/software_engineering.py`

**Tools** (15):
- `create_worktree`, `apply_patch_to_worktree`, `get_worktree_diff`
- `edit_file`, `apply_patch`, `search_and_replace`, `rename_symbol`
- `extract_function`, `organize_imports`
- `generate_function`, `generate_class`, `format_code`
- `git_diff`, `read_file`, `search_code`

**Instruction Template**:
```
You are the Software Engineering specialist. You write and change code.

Context:
- Sandbox worktree: {worktree}
- Change request: {change_request}
- Impact analysis: {impact_context}

Process:
1. Create or use existing worktree
2. Apply change in worktree
3. Generate diff
4. Format code and organize imports

Rules:
- Only edit in sandbox worktree
- Do not run tests (that's Testing agent's job)
- Do not decide whether change is correct
- Return diff for verification

Return to state['result_software_eng']
```

**Permission Ceiling**: write (worktree only)

### 5.2 Build Testing and Verification Agent
**File**: `server/ai_agents/agents/testing_verification.py`

**Tools** (14):
- `discover_tests`, `map_tests_to_functions`, `identify_untested_paths`
- `run_unit_tests`, `run_regression_tests`, `measure_test_coverage`
- `verify_compilation`, `verify_lint`, `verify_types`, `verify_security`
- `compare_before_after`, `run_tests`, `run_typecheck`, `read_test_results`

**Instruction Template**:
```
You are the Testing and Verification specialist. You find tests, run them,
measure coverage, and verify changes.

Context:
- Sandbox worktree: {worktree}
- Proposed patch: {proposed_patch}
- Active task: {active_task}

Process:
1. Discover tests and map to functions
2. Run tests in worktree
3. Measure coverage
4. Verify compilation, lint, types, security
5. Compare before and after

Rules:
- Cannot edit files
- Label results as live, cached, or simulated
- Report 'passed' only when check really ran
- Use record_finding for all verification claims

Return to state['result_testing']
```

**Permission Ceiling**: execute (sandbox only)

### 5.3 Rebuild Fix Pipeline
Update `fix.py` to use new agents:

```python
from .software_engineering import software_engineering_agent
from .testing_verification import testing_verification_agent
from .debugging import debugging_agent

# New fix pipeline using new agents
new_fix_pipeline = SequentialAgent(
    name='new_fix_pipeline',
    description='Proposes change, verifies independently, shows reviewable diff',
    sub_agents=[
        debugging_agent,  # or security_agent for security fixes
        software_engineering_agent,
        testing_verification_agent,
        make_critic('new_fix_critic', 'findings'),
        scene_director
    ]
)
```

### 5.4 Write Golden Tasks
```yaml
test_id: AGENT-SE-001
agent: software_engineering
fixture: simple-python
request: Add error handling to target()
expected_tools_include: [edit_file, generate_function]
must_not:
  - edit_outside_worktree
  - run_tests

test_id: AGENT-TV-001
agent: testing_verification
fixture: simple-python
request: Verify the patch
expected_tools_include: [run_tests, measure_test_coverage]
must_not:
  - edit_files
  - claim_passed_without_running
```

### 5.5 Implement Server `/approve` Endpoint
Add endpoint to `jarvis_server.py`:
```python
@app.post("/approve")
async def approve_change(approval: ApprovalRequest):
    """Approve a worktree change after 2-second pinch hold"""
    # Validate approval
    # Commit worktree if approved
    # Return status
```

### 5.6 Create Deliberately Wrong Patch Test
Test that verifier rejects wrong patch:
```yaml
test_id: AGENT-TV-002
agent: testing_verification
fixture: simple-python
request: Verify this deliberately wrong patch
expected_result: rejected
expected_findings:
  - claim_contains: test failed
```

**Exit Gate for Phase 5**:
- ✅ Patch applied in worktree
- ✅ Tests run live (not cached)
- ✅ Verifier rejects deliberately wrong patch
- ✅ Nothing committed without `/approve`
- ✅ Independent verification working
- ✅ Software Engineering agent never runs tests
- ✅ Testing agent never edits files

---

## Phase 6: Coordination Hardening

**Goal**: Add parallel fan-out, timeouts, retry, cancellation, duplicate prevention, conflict resolution, investigation memory.

### 6.1 Parallel Fan-Out
Enhance Orchestrator to run independent specialists in parallel:

```python
def select_parallel_agents(request: str) -> List[str]:
    """Select agents that can run in parallel for this request"""
    if request_type == "explain":
        return ["code_understanding", "relationship", "data_flow"]
    elif request_type == "security_review":
        return ["repository", "data_flow", "security"]
    # ... other cases
```

### 6.2 Timeouts and Retry
Add per-agent timeout configuration:

```python
AGENT_TIMEOUTS = {
    "repository_intelligence": 30,
    "code_understanding": 45,
    "relationship_intelligence": 60,
    # ...
}

MAX_RETRIES = {
    "runtime_intelligence": 3,
    "debugging": 2,
    # ...
}
```

Implement retry logic in callbacks:
```python
def after_tool_callback(callback_context, tool_result):
    if tool_result.get('status') == 'timeout':
        retries = callback_context.state.get('retries', 0)
        agent = callback_context.state.get('calling_agent')
        if retries < MAX_RETRIES.get(agent, 1):
            callback_context.state['retries'] = retries + 1
            return {'retry': True}
    return None
```

### 6.3 Cancellation
Implement cancellation in orchestrator:
```python
def cancel_agent_task(agent_name: str, task_id: str):
    """Cancel a running agent task"""
    agent = get_agent(agent_name)
    # ADK cancellation API
```

### 6.4 Duplicate Task Prevention
Add task deduplication:

```python
class TaskDeduplicator:
    def __init__(self):
        self.running_tasks = {}

    def is_duplicate(self, task: Dict) -> bool:
        key = self._task_key(task)
        return key in self.running_tasks

    def register(self, task: Dict):
        key = self._task_key(task)
        self.running_tasks[key] = task

    def unregister(self, task: Dict):
        key = self._task_key(task)
        self.running_tasks.pop(key, None)
```

### 6.5 Conflict Resolution
Enhance orchestrator's `resolve_conflicting_findings`:

```python
def resolve_conflicting_findings(findings: List[Finding]) -> List[Finding]:
    """Resolve contradictions between agent findings"""
    # Group by claim subject
    # Detect contradictions
    # Call tools to verify
    # Mark lower-confidence finding as inferred
    # Keep both if evidence insufficient
```

### 6.6 Investigation Memory
Add persistent investigation memory:

```python
class InvestigationMemory:
    def save_investigation(self, investigation_id: str, findings: List[Finding]):
        """Save investigation to disk"""

    def load_investigation(self, investigation_id: str) -> List[Finding]:
        """Load previous investigation"""

    def search_investigations(self, query: str) -> List[Finding]:
        """Search across investigations"""
```

### 6.7 Write Failure Injection Tests
Create test scenarios in `evals/failure_injection/`:
```yaml
# agent_timeout.yaml
test_id: FAIL-001
scenario: agent_timeout
agent: code_understanding
inject: timeout_at_tool_call
expected: retry_succeeds

# agent_failure.yaml
test_id: FAIL-002
scenario: agent_failure
agent: relationship_intelligence
inject: tool_returns_error
expected: graceful_degradation

# duplicate_task.yaml
test_id: FAIL-003
scenario: duplicate_task
agents: [code_understanding, relationship]
inject: parallel_same_task
expected: one_runs_one_skipped

# conflict.yaml
test_id: FAIL-004
scenario: conflicting_findings
agents: [code_understanding, relationship]
inject: contradictory_claims
expected: resolution_attempted
```

**Exit Gate for Phase 6**:
- ✅ Failure injection scenarios pass
- ✅ Parallel fan-out works correctly
- ✅ Timeouts enforced
- ✅ Retry logic works
- ✅ Cancellation works
- ✅ Duplicate tasks prevented
- ✅ Conflicts resolved
- ✅ Investigation memory persists

---

## Phase 7: Server and VR Integration

**Goal**: Add streaming progress, new endpoints, Unity panels, load testing.

### 7.1 Streaming Progress from `/ask`
Currently `/ask` is one blocking call with 110-second timeout.

Change to streaming:
```python
@app.post("/ask")
async def ask_stream(request: AskRequest):
    """Stream agent progress as Server-Sent Events"""
    async def event_generator():
        yield {"type": "started", "agent": "orchestrator"}
        # ... stream each agent step
        yield {"type": "progress", "agent": "code_understanding", "step": "parsing"}
        yield {"type": "progress", "agent": "code_understanding", "step": "analyzing"}
        # ...
        yield {"type": "completed", "result": final_result}

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 7.2 Add New Endpoints
```python
@app.get("/plan")
async def get_plan(session_id: str):
    """Get current investigation plan"""

@app.get("/state")
async def get_state(session_id: str):
    """Get current agent state"""

@app.get("/agents")
async def list_agents():
    """List available agents"""

@app.get("/agents/{name}/status")
async def get_agent_status(name: str):
    """Get agent status"""

@app.post("/agents/{name}/cancel")
async def cancel_agent(name: str, task_id: str):
    """Cancel agent task"""
```

### 7.3 Unity Panels
Implement Unity UI panels (design already exists):
- **Plan Panel**: Shows investigation plan from `/plan` endpoint
- **Agent Activity Panel**: Shows real-time agent status from `/state` endpoint
- **Findings Panel**: Shows verified findings

### 7.4 Concurrent-Session Load Test
Implement load test:
```python
# tests/load/concurrent_sessions.py
async def test_concurrent_sessions():
    """Test 10 concurrent users asking questions"""
    tasks = [ask_question(session_id, question) for session_id in range(10)]
    results = await asyncio.gather(*tasks)
    # Verify all complete correctly
    # Verify no state leakage between sessions
```

### 7.5 Full Demo Run
Create demo script that runs through full flow:
1. User opens project
2. User selects function
3. User asks "explain this and show everything connected"
4. System displays plan
5. System shows agent activity
6. System shows findings
7. System displays visualization

**Exit Gate for Phase 7**:
- ✅ Streaming progress works from `/ask`
- ✅ New endpoints return correct data
- ✅ Unity panels display correctly
- ✅ Concurrent sessions work without state leakage
- ✅ Full demo run on Quest or simulator with no manual steps

---

## The Twelve Agents (Detailed Tool Lists)

### Agent 1: Orchestrator
**Tools**:
- `classify_request`, `understand_user_intent`, `create_investigation_plan`
- `check_task_completion`, `merge_agent_results`, `resolve_conflicting_findings`
- `request_more_evidence`, `request_approval`
- Other specialists as `AgentTool`s

**Output Key**: `plan`

**Permission Ceiling**: read

### Agent 2: Conversational JARVIS
**Tools** (8):
- `answer_code_question`, `explain_visualization`, `summarize_investigation`
- `retrieve_conversation_context`, `retrieve_investigation_context`
- `ask_clarifying_question`, `compare_code_elements`, `manage_conversation_preferences`

**Output Key**: `result_conversational`

**Permission Ceiling**: read

### Agent 3: Repository Intelligence
**Tools** (19):
- `index_repository`, `incremental_index_repository`
- `detect_languages`, `detect_frameworks`, `detect_build_system`, `detect_project_type`, `detect_package_manager`
- `analyze_repository_structure`, `analyze_monorepo`
- `identify_entry_points`, `identify_external_services`, `identify_generated_files`
- `detect_repository_changes`, `analyze_dependencies_manifest`
- `list_files`, `read_file`, `search_code`
- `get_repository_metadata`, `get_changed_files`

**Output Key**: `result_repository`

**Permission Ceiling**: read

### Agent 4: Code Understanding
**Tools** (22):
- `get_symbol_definition`, `get_symbol_references`, `get_symbol_hover_info`
- `get_type_hierarchy`, `get_imports`, `get_exports`, `get_scope_information`
- `parse_source_code`, `extract_symbols`, `resolve_types`
- `explain_function`, `explain_class`, `explain_module`, `explain_condition`
- `extract_function_contract`, `identify_side_effects`, `identify_hidden_assumptions`
- `infer_code_intent`, `trace_function_logic`, `analyze_control_flow`
- `extract_docstrings`, `read_file_range`

**Output Key**: `result_code_understanding`

**Permission Ceiling**: read

### Agent 5: Relationship Intelligence
**Tools** (17):
- `find_callers`, `find_callees`, `find_indirect_callers`, `trace_call_chain`
- `build_call_graph`, `build_dependency_graph`, `find_dependents`
- `find_all_paths_between_symbols`, `find_circular_dependencies`
- `analyze_architecture_boundaries`, `calculate_change_impact`
- `find_interface_implementations`
- `trace_cross_module_relationships`, `trace_cross_service_relationships`
- `discover_api_endpoints`, `map_api_to_database`, `trace_request_lifecycle`

**Output Key**: `result_relationship`

**Permission Ceiling**: read

### Agent 6: Data Flow Intelligence
**Tools** (16):
- `trace_variable_origin`, `trace_variable_usage`, `trace_variable_modifications`
- `trace_parameter_flow`, `trace_return_value_flow`, `trace_taint_flow`
- `trace_transformations`, `trace_cross_function_flow`, `trace_cross_service_flow`
- `trace_database_reads`, `trace_database_writes`, `trace_api_data_flow`
- `trace_file_operations`, `trace_state_changes`, `build_data_flow_graph`
- `identify_data_leaks`, `identify_data_sinks`, `identify_data_sources`, `identify_validation_gaps`

**Output Key**: `result_data_flow`

**Permission Ceiling**: read

### Agent 7: Runtime Intelligence
**Tools** (13):
- `start_application`, `stop_application`, `attach_runtime_profiler`, `attach_debugger`
- `collect_execution_trace`, `record_function_calls`, `record_function_arguments`, `record_function_returns`
- `record_execution_timing`, `record_variable_state`, `record_memory_usage`, `record_cpu_usage`
- `record_network_activity`, `record_database_activity`, `record_async_tasks`, `record_thread_activity`
- `capture_application_logs`, `capture_runtime_events`, `compare_execution_traces`, `replay_execution_trace`

**Output Key**: `result_runtime`

**Permission Ceiling**: execute (sandbox only)

### Agent 8: Debugging Intelligence
**Tools** (11):
- `capture_exception`, `analyze_stack_trace`, `find_error_origin`, `trace_error_propagation`
- `identify_failure_path`, `set_breakpoint`, `remove_breakpoint`, `step_into`, `step_over`, `step_out`
- `inspect_variables`, `evaluate_debug_expression`, `inspect_call_stack`, `watch_expression`
- `reproduce_bug`, `compare_success_failure`, `identify_root_cause`, `suggest_debugging_actions`

**Output Key**: `result_debugging`

**Permission Ceiling**: execute (sandbox only)

### Agent 9: Security and Quality
**Tools** (16):
- `scan_secrets`, `scan_vulnerabilities`, `scan_security_vulnerabilities`, `scan_dependency_vulnerabilities`
- `analyze_authentication`, `analyze_authorization`, `analyze_permissions`, `analyze_input_validation`
- `analyze_injection_risks`, `analyze_cryptography`, `trace_sensitive_data`, `analyze_attack_surface`
- `calculate_complexity`, `calculate_cognitive_complexity`, `detect_code_smells`, `detect_duplicates`
- `detect_anti_patterns`, `analyze_maintainability`, `analyze_testability`, `analyze_violations`
- `identify_technical_debt`, `generate_security_report`, `generate_quality_report`

**Output Key**: `result_security`

**Permission Ceiling**: read

### Agent 10: Software Engineering
**Tools** (15):
- `create_worktree`, `apply_patch_to_worktree`, `get_worktree_diff`
- `edit_file`, `apply_patch`, `search_and_replace`, `rename_symbol`
- `extract_function`, `organize_imports`
- `generate_function`, `generate_class`, `format_code`
- `git_diff`, `read_file`, `search_code`

**Output Key**: `result_software_eng`

**Permission Ceiling**: write (worktree only)

### Agent 11: Testing and Verification
**Tools** (14):
- `discover_tests`, `map_tests_to_functions`, `identify_untested_paths`
- `run_unit_tests`, `run_regression_tests`, `measure_test_coverage`
- `verify_compilation`, `verify_lint`, `verify_types`, `verify_security`
- `compare_before_after`, `run_tests`, `run_typecheck`, `read_test_results`

**Output Key**: `result_testing`

**Permission Ceiling**: execute (sandbox only)

### Agent 12: Visualization and Spatial Intelligence
**Tools** (20):
- `highlight_vr_path`, `dim_unrelated`, `focus_camera`, `open_code_panel`, `set_edge_style`
- `show_ghost_diff`, `show_test_badges`
- `create_graph`, `visualize_call_graph`, `visualize_change_impact`, `visualize_data_flow`
- `visualize_test_coverage`
- `expand_graph_node`, `collapse_graph_node`, `isolate_subgraph`, `filter_graph`
- `calculate_graph_clusters`, `summarize_graph`
- `get_current_selection`, `verify_citations`

**Output Key**: `result_visualization`

**Permission Ceiling**: read

---

## Request to Agent Mapping

| Request | Agents (parallel in brackets) |
|---------|------------------------------|
| Explain this function | Code Understanding, [Relationship, Data Flow], Critic, Visualization, Conversational |
| What breaks if I change this | Relationship, [Testing (map tests), Security], Critic, Visualization |
| Trace this request to the database | Repository, Relationship, Data Flow, Critic, Visualization |
| Why does this fail sometimes | Code Understanding, Runtime, Debugging, [Security], Critic, Conversational |
| Fix this | Debugging or Security, Software Engineering, Testing and Verification, Critic, human approval |
| Security review | Repository, [Data Flow, Security and Quality], Critic, Visualization |
| Opening briefing | Repository (changes), [Testing, Security and Quality], Conversational |

---

## Risks and Mitigations

### Risk 1: Tool Quality
**Risk**: If a tool returns canned or keyword-matched data, the answer sounds right but is wrong.

**Mitigation**:
- Phase 0 exists for this reason
- Every tool must pass real-input test before being added to agent
- Mark experimental tools as such in agent prompts
- Continuous monitoring of tool accuracy

### Risk 2: Model and Cost
**Risk**: Multi-agent turns make many model calls, cost is high, default model `gemini-3.5-flash` is unverified.

**Mitigation**:
- Decide model per agent (smaller models for narrow specialists)
- Set per-turn call budget per agent
- Consider caching for repeated analyses
- Monitor cost per request

### Risk 3: Latency
**Risk**: VR user waits for whole turn, streaming is required before more agents.

**Mitigation**:
- Phase 7 adds streaming progress
- Parallel execution where independent
- Timeout and cancellation
- Progress indicators

### Risk 4: Two Delegation Systems
**Risk**: `delegate_task` from `orchestrator_tools.py` and ADK `AgentTool` will drift apart.

**Mitigation**:
- Decision D2: pick ADK `AgentTool` before writing agents
- Retire or convert simulated helpers
- Single source of truth for delegation

### Risk 5: Language Coverage
**Risk**: Analysis tools strongest on Python, other languages less supported.

**Mitigation**:
- Record language support in `tool_completion_status.json`
- Language compatibility matrix per tool
- Agent prompts state supported languages
- Progressive language support expansion

---

## First Fifteen Tasks (In Order)

1. Fix test runner (`tool_context`, `must_not`, placeholder handling)
2. Run suite and record real pass/fail counts per tool
3. Resolve 17 duplicate tool names
4. Add import check and `toolsets.py` validation test
5. Write real-input tests with known answers for 176 curated tools (start with agents 3, 4, 5)
6. Populate `tool_completion_status.json` from run
7. Build `base.py`, `findings.py`, `registry.py`
8. Add evidence-collecting and permission callbacks
9. Build Code Understanding, Relationship, and Repository agents
10. Build Visualization and Conversational, connect to existing scene commands
11. Build Orchestrator with `AgentTool` delegation
12. Write golden tasks for Phase 2 slice and run them
13. Add streaming progress to server
14. Demo the slice in simulator
15. Start Phase 3 (Data Flow and Security)

---

## Testing Strategy

### Per-Agent Testing
Each agent gets 5-10 golden tasks in YAML format:
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

### Per-Agent Edge Cases
Each agent tested for:
- Tool that returns error
- Tool that returns partial data
- Tool that returns contradictory data
- Repository file with instructions (prompt injection)
- Tool above permission ceiling (must be blocked)
- Timeouts and cancellation

### Multi-Agent Testing
- Correct delegation order
- Parallel where independent
- No overwritten findings
- Retry after one agent fails
- Contradiction between two agents reaching orchestrator

### Fixture Repositories
- `simple-python`: Basic Python project
- `spring-boot`: Java Spring Boot application
- `security-challenge`: Planted vulnerabilities and secrets
- `intermittent-bug`: Race condition and timing issues
- `polyglot-monorepo`: Multiple languages and frameworks

---

## Success Metrics

### Phase 0
- 176 curated tools each have real-input test
- Test suite runs without errors
- `tool_completion_status.json` populated

### Phase 1
- Agent factory creates agents from specs
- Toolsets validate at import
- Findings schema in place
- Registry lists agents

### Phase 2
- Golden tasks pass on 2 fixtures
- Zero uncited claims
- p95 latency < 60s
- Scene commands verified

### Phase 3
- All planted vulnerabilities found
- False-positive rate < 20%
- Source/path/sink in every security finding

### Phase 4
- Intermittent bug root cause identified
- Runtime measurements accurate
- Sandbox isolation verified

### Phase 5
- Patch applied in worktree
- Verifier rejects wrong patch
- No commit without `/approve`
- Separation of concerns verified

### Phase 6
- Failure injection scenarios pass
- Parallel execution works
- Timeouts enforced
- Conflicts resolved

### Phase 7
- Streaming progress works
- New endpoints functional
- Unity panels display correctly
- Concurrent sessions work
- Full demo runs without manual steps

---

## Appendix: File Structure

```
server/ai_agents/
├── __init__.py
├── agent.py                          # Existing pipelines + new Phase 2 pipeline
├── config.py                        # Existing
├── state.py                         # Extended with new keys
├── callbacks.py                     # Extended with evidence/permission callbacks
├── repository.py                    # Existing
├── agents/
│   ├── __init__.py
│   ├── base.py                       # NEW: make_specialist factory
│   ├── toolsets.py                   # NEW: curated tool mappings
│   ├── findings.py                   # NEW: findings schema and record_finding
│   ├── registry.py                   # NEW: agent registry
│   ├── briefing.py                   # Existing
│   ├── critic.py                     # Updated for new findings format
│   ├── fix.py                        # Existing
│   ├── impact.py                     # Existing
│   ├── investigator.py               # Existing
│   ├── scene_director.py             # Existing
│   ├── orchestrator.py               # NEW
│   ├── conversational.py             # NEW
│   ├── repository_intelligence.py   # NEW
│   ├── code_understanding.py         # NEW
│   ├── relationship_intelligence.py  # NEW
│   ├── data_flow.py                  # NEW
│   ├── runtime.py                    # NEW
│   ├── debugging.py                  # NEW
│   ├── security_quality.py           # NEW
│   ├── software_engineering.py       # NEW
│   └── testing_verification.py       # NEW
├── tools/
│   ├── __init__.py                   # Existing, 533 tools
│   ├── _common.py                    # Existing
│   ├── _safe.py                      # Existing
│   ├── [all tool files]              # Existing
├── evals/
│   ├── __init__.py
│   ├── golden_tasks/
│   │   ├── repository/
│   │   ├── code_understanding/
│   │   ├── relationship/
│   │   ├── data_flow/
│   │   ├── runtime/
│   │   ├── debugging/
│   │   ├── security/
│   │   ├── software_engineering/
│   │   ├── testing/
│   │   ├── visualization/
│   │   └── orchestrator/
│   ├── failure_injection/
│   │   ├── agent_timeout.yaml
│   │   ├── agent_failure.yaml
│   │   ├── duplicate_task.yaml
│   │   └── conflict.yaml
│   ├── runner.py                     # NEW
│   └── metrics.py                    # NEW
└── data/
    ├── index/                        # Existing
    ├── tool_completion_status.json  # NEW
    └── investigation_memory/         # NEW
```

---

## Next Steps

1. Review this plan with stakeholders
2. Approve design decisions (D1-D7)
3. Begin Phase 0 (Tool Trustworthiness)
4. Track progress with scoreboard
5. Adjust plan based on findings

---

**Document Version**: 1.0
**Last Updated**: 2026-11-01
**Author**: Generated from JARVIS plan
