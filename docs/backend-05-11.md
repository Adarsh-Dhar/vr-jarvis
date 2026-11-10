# JARVIS backend: MVP architecture

This document describes the current MVP backend in `server/`. It replaces the
older feature catalogue, which described toolkits and agents that have since
been removed. For the authoritative tool list, query `GET /tools` or inspect
`server/ai_agents/agents/toolsets.py`.

## 1. Server endpoints (21)

All endpoints require a bearer token (`Authorization: Bearer $JARVIS_TOKEN`)
except `GET /health`, which is public.

| Endpoint | What it does | Used by Unity? |
|---|---|---|
| `POST /transcribe` | Speech-to-text for the VR client (base64 audio in, transcript out) | yes |
| `POST /session` | Create a conversation session | yes |
| `GET /health` | Public status: repo, branch, changed files, cached-test flag | yes |
| `GET /graph` | Code graph of the active repository (nodes, edges) | yes |
| `GET /repos`, `POST /repos/select` | List repositories and switch the active one | yes |
| `GET /repos/{name}/tree`, `GET /repos/{name}/file` | Browse folders and read files, confined to the repository | yes |
| `GET /source/{node_id}` | Source code for one graph node | yes |
| `GET /skills`, `GET /skills/{id}`, `POST /skills/{id}/run` | List, inspect and run repository-analysis skills | no |
| `POST /ask` | Ask JARVIS a question; returns reply, scene commands, evidence, test results, pending approval | yes |
| `POST /ask/stream` | Same as `/ask` but streams progress as Server-Sent Events | no |
| `POST /approve` | Approve or reject a pending action | yes |
| `GET /task/{session_id}` | Current task state for a session | no |
| `GET /agents`, `GET /agents/{name}` | Status of all agents or one agent | no |
| `GET /progress/{session_id}` | Which agents have run so far, for a progress display | yes |
| `GET /tools` | Every tool with its level, owning agents and parameters | no |
| `POST /actions/{action_name}` | Run a quick action without a model (small allowlist) | no |
| `POST /tools/{tool_name}` | Run a read-level tool directly (disabled unless `JARVIS_ENABLE_DIRECT_TOOLS=1`, allowlist only) | no |

The Unity frontend uses 12 of the 21 endpoints.

## 2. Agents

Nine agent roles are registered (`server/ai_agents/agents/registry.py`), each
with a curated toolset and a permission ceiling in
`server/ai_agents/agents/toolsets.py`:

| Agent | Ceiling | Responsibility |
|---|---|---|
| `orchestrator` | read | Classify requests, plan investigations, delegate to specialists, merge results |
| `repository_intelligence` | read | Index repositories, detect languages/frameworks/build systems, analyze structure and dependencies |
| `code_understanding` | read | Explain functions, classes, modules, conditions and algorithms; extract contracts, side effects, intent |
| `relationship_intelligence` | read | Call graphs, callers/callees, dependency graphs, dependents, circular dependencies, change impact |
| `data_flow_intelligence` | read | Trace variables, parameters, return values, state changes and file operations; build data-flow graphs |
| `software_engineering` | write | Edit files, apply patches, rename/extract symbols, generate code, work in git worktrees |
| `testing_verification` | execute | Discover and map tests, run tests/typecheck/lint, measure coverage, verify compilation |
| `visualization_spatial` | read | Build graph visualizations and drive the VR scene |
| `conversational` | read | Answer questions, summarize investigations, manage conversation context |

Pipelines (investigate, impact, fix, briefing) are composed from these agents;
critic and scene-director agents check evidence and emit scene commands.

## 3. Tools

- 161 tools are exported from `server/ai_agents/tools/__init__.py`; every one
  has a permission level (`read`, `execute`, `write`) in `TOOL_LEVELS` and a
  curated assignment in `TOOLSETS`.
- Agents can only call tools in their own toolset; unlisted tools are blocked.
- `POST /tools/{name}` fails closed: the tool must be in `TOOL_LEVELS`, have
  level `read`, be in `DIRECT_TOOL_ALLOWLIST`, and the feature flag
  `JARVIS_ENABLE_DIRECT_TOOLS=1` must be set.
- `POST /actions/{name}` is restricted to `QUICK_ACTIONS_ALLOWLIST`
  (`find_callers`, `find_callees`, `get_symbol_definition`,
  `calculate_change_impact`).

## 4. Scene commands (24)

Defined in `server/ai_agents/scene_commands.json` and consumed by the Unity
client: `select_node`, `expand_node`, `collapse_node`, `show_graph`,
`highlight_path`, `dim_unrelated`, `open_code_panel`, `focus_camera`,
`set_edge_style`, `show_ghost_diff`, `show_test_badges`, `set_mode`,
`show_approval_prompt`, `open_repo`, `browse_folder`, `open_file`,
`move_graph`, `zoom_graph`, `move_panel`, `scale_panel`, `panel_state`,
`highlight_callers`, `recenter`, `reset_layout`.

## 5. Repository index and code graph

- Multiple repositories under one folder (`JARVIS_REPOSITORY_DIR`), switchable
  at runtime; each is indexed to its own graph under
  `server/ai_agents/intelligence/graph_engine/`.
- Language detection is centralized in `intelligence/languages.py`. Indexed
  extensions: Python, JavaScript/TypeScript (`.js .jsx .mjs .cjs .ts .tsx`),
  Go, Rust, Java, C#, and C/C++ (`.c .h .cpp .cc .cxx .hpp`). Parser support
  varies by language; Python has the deepest AST-based analysis.
- The indexer builds symbols, imports/exports, clusters, call and dependency
  graphs, control-flow and data-flow graphs, and detects test files.
- File browser endpoints are confined to the active repository root.

## 6. Safety and control

- Bearer-token auth with constant-time comparison; startup refuses
  `JARVIS_TOKEN=dev-token`; binding to a non-localhost `JARVIS_HOST` requires a
  token; only `/health` is public.
- Per-agent permission ceilings and per-agent tool budgets
  (`DEFAULT_AGENT_CONFIG` in `agents/registry.py`).
- Per-session tool budgets and a monthly budget setting
  (`JARVIS_MONTHLY_BUDGET`).
- Code changes go through git worktrees; commits require passing tests and
  user approval via `/approve`; the main branch is untouched.
- Audit log (`logs/audit.jsonl`) records agent, tool, redacted arguments,
  outcome and duration for direct tool calls and quick actions.
- Session limits (`JARVIS_MAX_SESSIONS`, default 50) and idle expiry
  (`JARVIS_SESSION_IDLE_TIMEOUT`, default 1 hour); one request at a time per
  session.
- Model resilience in `ai_agents/llm.py`: retries on 503/429/500/504 with
  backoff, optional requests-per-minute pacing and concurrency cap, optional
  cheaper model (`JARVIS_MODEL_LITE`) for routine agents, call counter.

## 7. Settings (environment variables)

`JARVIS_TOKEN`, `JARVIS_HOST`, `JARVIS_REPOSITORY_DIR`, `JARVIS_REPO`,
`JARVIS_MODEL`, `JARVIS_MODEL_LITE`, `JARVIS_ASK_TIMEOUT`,
`JARVIS_MAX_SESSIONS`, `JARVIS_SESSION_IDLE_TIMEOUT`, `JARVIS_MONTHLY_BUDGET`,
`JARVIS_CACHED_TESTS`, `JARVIS_ENABLE_DIRECT_TOOLS`, `JARVIS_STT_MODEL`,
`JARVIS_MAX_AUDIO_BYTES`, `JARVIS_LLM_ATTEMPTS`, `JARVIS_LLM_RETRY_DELAY`,
`JARVIS_LLM_RPM`, `JARVIS_LLM_CONCURRENCY`.

## 8. Known limits

- **In-memory state.** Sessions and per-session task state live in memory;
  everything is lost on restart.
- **Parser depth.** Python has the richest analysis (AST, CFG, DFG); other
  indexed languages get shallower tree-sitter-based extraction.
- **Frontend coverage.** Unity does not use `/ask/stream`, `/task`, `/agents`,
  `/tools`, `/actions` or `/skills`.
- **Cost per question.** One question can cost many model calls (orchestrator
  plus specialist agents plus verification).
- **Direct tool surface.** Direct tool calls are off by default and limited to
  a 15-tool read-only allowlist.
