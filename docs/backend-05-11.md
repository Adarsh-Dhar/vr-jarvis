# JARVIS backend: complete feature catalog

Generated from the code in `vr-jarvis-main__1__1.zip` (server, agents, tools, Unity bridge). Section 1 to 8 describe what the backend does; section 9 lists every exported tool with its permission level, owning agents and parameters.

## 1. Server endpoints (18)

| Endpoint | What it does | Used by Unity? |
|---|---|---|
| `POST /session` | Create a conversation session | yes |
| `GET /health` | Public status: repo, branch, changed files, whether test results are cached | yes |
| `GET /graph` | Code graph of the active repository (nodes, edges, clusters) | yes |
| `GET /repos`, `POST /repos/select` | List repositories and switch the active one | yes |
| `GET /repos/{name}/tree`, `GET /repos/{name}/file` | Browse folders and read files, confined to the repository | yes |
| `GET /source/{node_id}` | Source code for one graph node | yes |
| `POST /ask` | Ask JARVIS a question; returns reply, scene commands, evidence, test results, pending approval | yes |
| `POST /approve` | Approve or reject a pending action; an approved commit goes to a sandbox branch | yes |
| `GET /progress/{session_id}` | Which agents have run so far, for a progress display | yes |
| `POST /ask/stream` | Same as `/ask` but streams progress as Server-Sent Events | no |
| `POST /request_approval` | Get a single-use, session-bound, 5-minute approval token for a protected tool | no |
| `GET /task/{session_id}` | Current task state for a session | no |
| `GET /agents`, `GET /agents/{name}` | Status of all agents or one agent | no |
| `GET /tools` | Every tool with its level, owning agents and parameters | no |
| `POST /tools/{name}` | Run a read-level tool directly, without a model | no |

The Unity frontend uses 11 of the 18 endpoints.

## 2. Agents

One root agent (`jarvis_orchestrator`) routes each request to a pipeline. The tree has 50 agents, 36 of them LLM agents.

- **Pipelines:** general (`phase2_pipeline`: orchestrator, three parallel specialists, critic, visualization, conversational), investigate, impact, fix (patch, verify loop of up to 3 repairs, critic), briefing.
- **The 12 specialist agents:** orchestrator, conversational, repository intelligence, code understanding, relationship intelligence, data flow, runtime, debugging, security and quality, software engineering, testing and verification, visualization and spatial. Each has its own toolset and a permission ceiling (`read`, `execute` or `write`).
- **Critic and scene agents:** each pipeline ends with a critic that checks evidence and a scene agent that turns the result into commands for the VR scene.

## 3. What a user can ask the backend to do (through the agents)

- Explain code, functions, classes, modules, conditions and algorithms with source references.
- Show callers, callees, dependents, call chains, cycles and change impact for any node.
- Trace data flow: variable origins, taint, database reads and writes, API data, state changes.
- Investigate a problem or give a briefing on what changed on the branch.
- Map changed code to tests, read coverage, run tests and type checks (real or cached results).
- Propose a fix as a patch, apply it in an isolated git worktree, verify it, repair it, and commit to a sandbox branch after tests pass and the user approves.
- Security and quality scans, debugging help, runtime and profiling analysis, documentation generation.
- Drive the VR scene: select, expand, collapse, filter, group, annotate, bookmark, compare, highlight paths, dim unrelated nodes, move the camera, open code panels, show a ghost diff, show test badges, ask for approval.

## 4. Scene commands the backend can send to Unity (19)

`select_node`, `expand_node`, `collapse_node`, `set_depth`, `set_scope`, `set_filters`, `create_group`, `annotate`, `bookmark`, `compare`, `show_graph`, `highlight_path`, `dim_unrelated`, `open_code_panel`, `focus_camera`, `set_edge_style`, `show_ghost_diff`, `show_test_badges`, `show_approval_prompt`.

## 5. Repositories and the code graph

- Multiple repositories under one folder, switchable at runtime, each indexed to its own graph file.
- The indexer reads Python (`.py`) and JavaScript or TypeScript (`.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`). It builds symbols, imports, clusters and detects test files.
- File browser with folder tree and file reading, confined to the repository.

## 6. Safety and control features

- Bearer-token authentication with constant-time comparison; startup refuses the token `dev-token`; network binding requires a token; only `/health` is public.
- Per-agent permission ceilings; unlisted tools are blocked for read-only agents.
- Per-session tool budgets and a monthly budget setting.
- Single-use approval tokens tied to session, tool, exact parameters and a 5-minute expiry.
- Commits only after tests pass and the user approves; main branch untouched.
- Audit log (`logs/audit.jsonl`) with secrets redacted from arguments.
- Evidence collection and citation checking; history trimming; per-turn state reset.
- Session limits (default 50) and idle expiry (default 1 hour); one request at a time per session.
- Model resilience from `llm.py`: retries on 503, 429, 500 and 504 with backoff, optional requests-per-minute pacing and concurrency cap, optional cheaper model for critics and scene agents, a call counter.

## 7. Settings (environment variables)

`JARVIS_TOKEN`, `JARVIS_HOST`, `JARVIS_REPOSITORY_DIR`, `JARVIS_REPO`, `JARVIS_MODEL`, `JARVIS_MODEL_LITE`, `JARVIS_ASK_TIMEOUT`, `JARVIS_MAX_SESSIONS`, `JARVIS_SESSION_IDLE_TIMEOUT`, `JARVIS_MONTHLY_BUDGET`, `JARVIS_CACHED_TESTS`, `JARVIS_LLM_ATTEMPTS`, `JARVIS_LLM_RETRY_DELAY`, `JARVIS_LLM_RPM`, `JARVIS_LLM_CONCURRENCY`.

## 8. Things to know (limits and risks)

- **Direct tool endpoint gap.** `POST /tools/{name}` blocks only tools whose level is `write` or `execute`. 329 of the 559 exported names (two of them are helper functions, not tools) have no declared level and are treated as `read`. That includes tools that do real work: `git_revert`, `git_stash`, `git_create_branch` (git commands), `execute_in_sandbox` and `cloud_execute_command` (subprocess), `database_execute` (SQLite). I confirmed that a call to these reaches the function; it failed only on missing arguments. Anyone with the token could call them. Fix: give every tool a level, and make the endpoint refuse any tool that has none.
- **Unreachable tools.** 332 tools are not attached to any agent, so a model cannot call them. They are reachable only through `/tools`.
- **In-memory stores.** The infrastructure tools keep their data in Python dictionaries, and sessions are in memory, so everything is lost on restart.
- **Indexer languages.** The graph is built for Python and JavaScript or TypeScript only, even though 20 language adapter tools exist.
- **Frontend coverage.** Unity does not use `/ask/stream`, `/request_approval`, `/task`, `/agents` or `/tools`.
- **Cost per question.** One question can cost 8 or more model calls (more with tool rounds).

## 9. Every exported tool


## visualization_spatial_tools (67 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `add_graph_edge` | unclassified | none | graph_id, source_id, target_id, edge_data | Add an edge to the graph. |
| `add_graph_node` | unclassified | none | graph_id, node_id, node_data | Add a node to the graph. |
| `annotate_code_element` | unclassified | none | element_id, annotation | Attach an explanation or note to a code element. Emits annotate command. |
| `annotate_visualization` | read | visualization_spatial | node_id, text | Alias for annotate_code_element. |
| `bookmark_investigation` | read | visualization_spatial | node_id, label | Alias for create_spatial_bookmark. |
| `calculate_graph_centrality` | unclassified | none | graph_id, centrality_type | Calculate graph centrality metrics. |
| `calculate_graph_clusters` | read | visualization_spatial | graph_id, algorithm | Calculate graph clusters. |
| `calculate_graph_depth` | unclassified | none | graph_id, root_node | Calculate graph depth from root. |
| `calculate_graph_layout` | unclassified | none | graph_id, layout_algorithm | Calculate graph layout. |
| `change_visualization_depth` | unclassified | none | visualization_id, depth | Expand or reduce graph depth. Emits set_depth command. |
| `change_visualization_scope` | unclassified | none | visualization_id, scope | Switch between local, direct, extended and runtime scopes. Emits set_scope command. |
| `collapse_graph_node` | read | visualization_spatial | graph_id, node_id | Collapse a node to hide its connections. Emits collapse_node command. |
| `compare_code_regions` | unclassified | none | region1_id, region2_id | Compare multiple selected code elements. Emits compare command. |
| `compare_graphs` | unclassified | none | graph1_id, graph2_id | Compare two graphs. |
| `compare_spatial_objects` | read | visualization_spatial | node_id1, node_id2 | Alias for compare_code_regions. |
| `create_graph` | read | visualization_spatial | graph_id, graph_type | Create a new graph. |
| `create_spatial_bookmark` | unclassified | none | bookmark_id, description | Bookmark a location in the code intelligence environment. Emits bookmark command. |
| `create_spatial_group` | read | visualization_spatial | graph_id, group_id, node_ids | Alias for create_graph with group semantics. |
| `expand_graph_node` | read | visualization_spatial | graph_id, node_id, depth | Expand a node to show its connections. Emits expand_node command. |
| `expand_relationships` | unclassified | none | object_id, relationship_type | Reveal connected code elements. |
| `filter_graph` | read | visualization_spatial | graph_id, filters | Filter graph by criteria. Emits set_filters command. |
| `focus_on_code_element` | read | visualization_spatial | node_id | Alias for focus_on_object. |
| `focus_on_graph_node` | read | visualization_spatial | graph_id, node_id, depth | Alias for expand_graph_node. |
| `focus_on_object` | unclassified | none | object_id | Bring an object into focus. |
| `get_current_selection` | read | visualization_spatial | - | Identify the currently selected code element or graph node. |
| `get_current_spatial_context` | read | visualization_spatial | - | Alias for get_spatial_selection_context. |
| `get_selected_node_details` | read | visualization_spatial | object_id | Alias for get_spatial_object_details. |
| `get_spatial_object_details` | unclassified | none | object_id | Retrieve information about a selected spatial object. |
| `get_spatial_selection_context` | unclassified | none | - | Understand the selected object's surrounding relationships. |
| `get_visualization_state` | unclassified | none | visualization_id | Understand what is currently being visualized. |
| `highlight_dependencies` | unclassified | none | graph_id, node_id, depth | Highlight dependencies of a node. |
| `highlight_path` | unclassified | none | graph_id, path | Highlight a path in the graph. |
| `isolate_relationship_path` | unclassified | none | path | Show only a particular investigation path. |
| `isolate_subgraph` | read | visualization_spatial | graph_id, node_ids | Show only a selected subgraph. |
| `navigate_to_code_element` | read | visualization_spatial | node_id | Alias for select_code_element. |
| `navigate_to_relationship` | read | visualization_spatial | node_id | Alias for trace_relationship_path. |
| `pin_investigation` | unclassified | none | investigation_id | Preserve an investigation for later. |
| `remove_graph_edge` | unclassified | none | graph_id, source_id, target_id | Remove an edge from the graph. |
| `remove_graph_node` | unclassified | none | graph_id, node_id | Remove a node from the graph. |
| `request_visualization` | unclassified | none | visualization_type, parameters | Request a particular visualization. |
| `restore_investigation` | unclassified | none | investigation_id | Restore a previous investigation. |
| `search_graph` | unclassified | none | graph_id, query | Search for nodes in the graph. |
| `select_code_element` | unclassified | none | element_id | Select a function, class, file or other code element. Emits select_node command. |
| `set_graph_depth` | read | visualization_spatial | visualization_id, depth | Alias for change_visualization_depth. |
| `set_visualization_filters` | read | visualization_spatial | graph_id, filters | Alias for filter_graph. |
| `set_visualization_scope` | read | visualization_spatial | visualization_id, scope | Alias for change_visualization_scope. |
| `summarize_graph` | read | visualization_spatial | graph_id | Summarize graph statistics. |
| `synchronize_graphs` | unclassified | none | graph_ids | Keep related visualizations synchronized. |
| `synchronize_visualizations` | read | visualization_spatial | viz_id1, viz_id2 | Alias for synchronize_graphs. |
| `trace_relationship_path` | unclassified | none | from_id, to_id | Follow a selected relationship through the graph. |
| `transition_visualization` | read | visualization_spatial | visualization_id, target_type | Alias for request_visualization. |
| `visualize_api_relationships` | unclassified | none | endpoint | Visualize API relationships. |
| `visualize_architecture` | unclassified | none | scope | Visualize architecture. |
| `visualize_call_graph` | read | visualization_spatial | function_id, scope | Visualize call graph. |
| `visualize_change_impact` | read | visualization_spatial | element_id | Visualize change impact. |
| `visualize_class_hierarchy` | unclassified | none | class_id | Visualize class hierarchy. |
| `visualize_control_flow` | unclassified | none | function_id | Visualize control flow. |
| `visualize_data_flow` | read | visualization_spatial | variable_id | Visualize data flow. |
| `visualize_database_relationships` | unclassified | none | table_name | Visualize database relationships. |
| `visualize_dependency_graph` | unclassified | none | component_id, scope | Visualize dependency graph. |
| `visualize_event_flow` | unclassified | none | event_source | Visualize event flow. |
| `visualize_execution_flow` | unclassified | none | trace_id | Visualize execution flow. |
| `visualize_git_history` | unclassified | none | repository_path, branch | Visualize git history. |
| `visualize_memory_usage` | unclassified | none | application_id | Visualize memory usage. |
| `visualize_performance` | unclassified | none | application_id, metric | Visualize performance metrics. |
| `visualize_security_flow` | unclassified | none | component_id | Visualize security flow. |
| `visualize_test_coverage` | read | visualization_spatial | repository_path | Visualize test coverage. |

## analysis_tools (15 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `analyze_annotations` | unclassified | none | file_path | Inspect decorators, attributes and annotations. |
| `analyze_code_complexity` | unclassified | none | file_path | Calculate complexity metrics. |
| `analyze_control_flow` | read | code_understanding | function_name | Generate control-flow information. |
| `analyze_data_flow` | unclassified | none | variable_name | Track data propagation. |
| `analyze_dependencies` | unclassified | none | file_path | Identify dependency relationships. |
| `analyze_exceptions` | unclassified | none | file_path | Identify exception paths and propagation. |
| `analyze_generated_code` | unclassified | none | file_path | Connect generated code to its source or generator. |
| `analyze_macros` | unclassified | none | file_path | Inspect macro usage where supported. |
| `detect_code_duplication` | unclassified | none | directory | Identify duplicate or similar code (repeated lines) inside one repository. |
| `detect_dead_code` | unclassified | none | file_path | Find potentially unused code. |
| `extract_ast` | unclassified | none | file_path | Extract abstract syntax trees. |
| `extract_symbols` | read | code_understanding | file_path | Extract functions, classes, methods, fields and variables. |
| `parse_source_code` | read | code_understanding | file_path | Parse source code into syntax trees. |
| `resolve_references` | unclassified | none | file_path | Resolve references between code elements. |
| `resolve_types` | read | code_understanding | file_path | Resolve types and type relationships. |

## api_database_toolkit (28 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `analyze_api_contract` | unclassified | none | endpoint | Analyze API contract (request/response). |
| `analyze_api_security` | unclassified | none | endpoint | Analyze API security (auth, rate limiting, etc.). |
| `analyze_database_performance` | unclassified | none | connection_string | Analyze database performance. |
| `analyze_database_queries` | unclassified | none | repository_path | Analyze database queries. |
| `discover_api_endpoints` | read | relationship_intelligence | repository_path | Find application endpoints. |
| `discover_database_schema` | unclassified | none | repository_path | Discover database schema. |
| `explain_query_plan` | unclassified | none | query, connection_string | Explain query execution plan. |
| `inspect_api_schema` | unclassified | none | schema_path, schema_type | Read OpenAPI, GraphQL and other API schemas. |
| `inspect_authentication` | unclassified | none | repository_path | Inspect authentication. |
| `inspect_authorization` | unclassified | none | repository_path | Inspect authorization. |
| `inspect_columns` | unclassified | none | connection_string, table | Inspect table columns. |
| `inspect_database_connection` | unclassified | none | connection_string | Inspect database connection configuration. |
| `inspect_database_schema` | unclassified | none | connection_string | Inspect database schema. |
| `inspect_foreign_keys` | unclassified | none | connection_string, table | Inspect foreign keys. |
| `inspect_http_routes` | unclassified | none | repository_path | Inspect HTTP routes. |
| `inspect_indexes` | unclassified | none | connection_string, table | Inspect table indexes. |
| `inspect_middleware` | unclassified | none | repository_path | Inspect middleware. |
| `inspect_orm_models` | unclassified | none | repository_path | Inspect ORM models. |
| `inspect_orm_relationships` | unclassified | none | repository_path | Inspect ORM relationships. |
| `inspect_sql_queries` | unclassified | none | repository_path | Inspect SQL queries. |
| `inspect_tables` | unclassified | none | connection_string | Inspect database tables. |
| `map_api_to_database` | read | relationship_intelligence | repository_path | Map API endpoints to database operations. |
| `trace_api_call` | unclassified | none | endpoint | Trace an API call through the application. |
| `trace_database_operation` | unclassified | none | query_id | Trace a database operation. |
| `trace_migrations` | unclassified | none | repository_path | Trace database migrations. |
| `trace_request_lifecycle` | read | relationship_intelligence | endpoint | Trace request lifecycle. |
| `trace_transaction` | unclassified | none | transaction_id | Trace database transaction. |
| `visualize_database_schema` | unclassified | none | connection_string | Visualize database schema. |

## relationship_intelligence_tools (17 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `analyze_architecture_boundaries` | read | relationship_intelligence | scope | Identify architectural boundaries. |
| `build_call_graph` | read | relationship_intelligence | scope | Construct function call graphs. |
| `build_class_relationship_graph` | unclassified | none | scope | Map inheritance and composition. |
| `build_dependency_graph` | read | relationship_intelligence | repository_path | Build module dependency graphs from repository analysis. |
| `build_reference_graph` | unclassified | none | scope | Construct reference relationships. |
| `calculate_change_impact` | read | relationship_intelligence | element_id | Estimate which components are affected by a change. |
| `find_all_paths_between_symbols` | read | relationship_intelligence | from_id, to_id | Find paths connecting two code elements. |
| `find_callees` | read | relationship_intelligence | function_id | Find functions called by a selected function. |
| `find_callers` | read | relationship_intelligence | function_id, depth | Find functions calling a selected function. |
| `find_circular_dependencies` | read | relationship_intelligence | scope | Detect dependency cycles. |
| `find_dependents` | read | relationship_intelligence | component_id | Find components depending on a selected component. |
| `find_indirect_callers` | read | relationship_intelligence | function_id | Find functions indirectly calling a selected function. |
| `find_interface_implementations` | read | relationship_intelligence | interface_id | Find implementations of an interface. |
| `find_shared_dependencies` | unclassified | none | module_ids | Find dependencies shared by multiple modules. |
| `trace_call_chain` | read | relationship_intelligence | function_id, depth | Trace the complete call chain. |
| `trace_cross_module_relationships` | read | relationship_intelligence | module_id | Follow relationships between modules. |
| `trace_cross_service_relationships` | read | relationship_intelligence | service_id | Follow relationships between services. |

## security_quality_tools (26 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `analyze_attack_surface` | read | security_quality | repository_path | Analyze potential attack vectors. |
| `analyze_authentication` | read | security_quality | repository_path | Analyze authentication mechanisms. |
| `analyze_authorization` | read | security_quality | repository_path | Analyze authorization mechanisms. |
| `analyze_boundaries` | unclassified | none | repository_path | Analyze trust boundaries. |
| `analyze_cryptography` | read | security_quality | repository_path | Analyze cryptographic practices. |
| `analyze_injection_risks` | read | security_quality | repository_path | Analyze SQL injection, XSS, etc. |
| `analyze_input_validation` | read | security_quality | repository_path | Analyze input validation practices. |
| `analyze_maintainability` | read | security_quality | repository_path | Analyze code maintainability. |
| `analyze_permissions` | read | security_quality | repository_path | Analyze permission models. |
| `analyze_testability` | unclassified | none | repository_path | Analyze code testability. |
| `analyze_violations` | unclassified | none | repository_path | Analyze style violations. |
| `calculate_cognitive_complexity` | read | security_quality | file_path | Calculate cognitive complexity. |
| `calculate_complexity` | read | security_quality | file_path | Calculate cyclomatic complexity. |
| `check_advisories` | unclassified | none | repository_path | Check security advisories. |
| `check_code_quality` | unclassified | none | repository_path | Check code quality metrics. |
| `detect_anti_patterns` | read | security_quality | repository_path | Detect anti-patterns. |
| `detect_code_smells` | read | security_quality | repository_path | Detect code smells. |
| `detect_duplicates` | read | security_quality | repository_path | Detect duplicate code. |
| `generate_quality_report` | read | security_quality | repository_path | Generate quality report. |
| `generate_security_report` | read | security_quality | repository_path | Generate security report. |
| `identify_technical_debt` | read | security_quality | repository_path | Identify technical debt. |
| `scan_dependency_vulnerabilities` | read | security_quality | repository_path | Scan for vulnerable dependencies. |
| `scan_secrets` | read | security_quality | repository_path | Scan for hardcoded secrets. |
| `scan_security_vulnerabilities` | read | security_quality | repository_path | Scan for security vulnerabilities. |
| `scan_vulnerabilities` | read | security_quality | repository_path | Scan for security vulnerabilities. |
| `trace_sensitive_data` | read | security_quality | repository_path | Trace sensitive data flow. |

## repository_intelligence_tools (18 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `analyze_build_configuration` | unclassified | none | repository_path | Analyze build configuration. |
| `analyze_dependencies_manifest` | read | repository_intelligence | repository_path | Extract declared dependencies from pom.xml, package.json, requirements.txt or Cargo.toml. |
| `analyze_environment_configuration` | unclassified | none | repository_path | Analyze environment configuration. |
| `analyze_monorepo` | read | repository_intelligence | repository_path | Analyze monorepo structure. |
| `analyze_project_configuration` | unclassified | none | repository_path | Analyze project configuration. |
| `analyze_repository_structure` | read | repository_intelligence | repository_path | Analyze repository structure. |
| `detect_build_system` | read | repository_intelligence | repository_path | Detect build system. |
| `detect_frameworks` | read | repository_intelligence | repository_path | Identify frameworks and libraries. |
| `detect_languages` | read | repository_intelligence | repository_path | Identify all programming languages. |
| `detect_package_manager` | read | repository_intelligence | repository_path | Detect package manager. |
| `detect_project_type` | read | repository_intelligence | repository_path | Detect project type. |
| `detect_repository_changes` | read | repository_intelligence | repository_path | Detect repository changes. |
| `identify_entry_points` | read | repository_intelligence | repository_path | Identify application entry points. |
| `identify_external_services` | read | repository_intelligence | repository_path | Identify external services. |
| `identify_generated_files` | read | repository_intelligence | repository_path | Identify generated files. |
| `incremental_index_repository` | read | repository_intelligence | repository_path | Re-index the repository (full rebuild until true incremental indexing exists). |
| `index_repository` | read | repository_intelligence | repository_path | Index repository: build its code graph and make it the active repository. |
| `resolve_dependency_versions` | unclassified | none | repository_path | Resolve dependency versions. |

## git_history_toolkit (3 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `analyze_commit_impact` | unclassified | none | commit_hash, repository_path | Analyze the impact of a commit. |
| `find_introducing_commit` | unclassified | none | symbol_id, repository_path | Find the commit that introduced a behavior. |
| `trace_file_history` | unclassified | none | file_path, repository_path | Trace the history of a file. |

## language_adapters (20 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `analyze_framework_component_relationships` | unclassified | none | repository_path, framework | Analyze framework-specific component and state relationships. |
| `analyze_framework_configuration` | unclassified | none | repository_path, framework | Analyze framework-specific configuration. |
| `analyze_framework_dependency_injection` | unclassified | none | repository_path, framework | Analyze framework-specific dependency injection. |
| `analyze_framework_event_handling` | unclassified | none | repository_path, framework | Analyze framework-specific event handling. |
| `analyze_framework_lifecycle` | unclassified | none | repository_path, framework | Analyze framework-specific lifecycle and execution model. |
| `analyze_framework_orm_integration` | unclassified | none | repository_path, framework | Analyze framework-specific ORM and database integration. |
| `analyze_framework_runtime_instrumentation` | unclassified | none | repository_path, framework | Analyze framework-specific runtime instrumentation. |
| `analyze_language_specific_features` | unclassified | none | file_path, language | Analyze language-specific features (decorators, async, etc.). |
| `discover_framework_components` | unclassified | none | repository_path, framework | Discover framework-specific components. |
| `discover_framework_middleware` | unclassified | none | repository_path, framework | Discover framework-specific middleware/plugins. |
| `discover_framework_routes` | unclassified | none | repository_path, framework | Discover framework-specific routes/endpoints. |
| `extract_language_symbols` | unclassified | none | file_path, language | Extract symbols using language-specific adapter. |
| `get_framework_adapter` | unclassified | none | framework, language | Get adapter for a specific framework. |
| `get_language_adapter` | unclassified | none | language | Get adapter for a specific language. |
| `list_supported_frameworks` | unclassified | none | language | List all supported frameworks. |
| `list_supported_languages` | unclassified | none | - | List all supported languages. |
| `parse_language_ast` | unclassified | none | file_path, language | Parse source code using language-specific parser (Tree-sitter based). |
| `register_framework_adapter` | unclassified | none | framework, language, adapter_config | Register a framework adapter. |
| `register_language_adapter` | unclassified | none | language, adapter_config | Register a language adapter. |
| `resolve_language_types` | unclassified | none | file_path, language | Resolve types using language-specific type checker. |

## debugging_intelligence_tools (18 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `analyze_stack_trace` | read | debugging_intelligence | stack_trace | Interpret stack traces. |
| `capture_exception` | read | debugging_intelligence | application_id | Capture exceptions. |
| `compare_success_failure` | read | debugging_intelligence | success_trace_id, failure_trace_id | Compare successful and failed executions. |
| `evaluate_debug_expression` | read | debugging_intelligence | expression | Evaluate a safe debugging expression. |
| `find_error_origin` | read | debugging_intelligence | stack_trace | Identify the likely source of an error. |
| `identify_failure_path` | read | debugging_intelligence | error_id | Reconstruct the failure path. |
| `identify_root_cause` | read | debugging_intelligence | error_id | Rank and explain possible root causes. |
| `inspect_call_stack` | read | debugging_intelligence | - | Inspect the current call stack. |
| `inspect_variables` | read | debugging_intelligence | scope | Inspect runtime variables. |
| `remove_breakpoint` | execute | debugging_intelligence | breakpoint_id | Remove a breakpoint. |
| `reproduce_bug` | execute | debugging_intelligence | bug_report | Attempt to reproduce a failure. |
| `set_breakpoint` | execute | debugging_intelligence | file_path, line, condition | Set a debugger breakpoint. |
| `step_into` | execute | debugging_intelligence | - | Step into a function. |
| `step_out` | execute | debugging_intelligence | - | Exit the current function. |
| `step_over` | execute | debugging_intelligence | - | Step over an operation. |
| `suggest_debugging_actions` | read | debugging_intelligence | error_id | Suggest next investigative steps. |
| `trace_error_propagation` | read | debugging_intelligence | error_id | Follow how errors propagate. |
| `watch_expression` | read | debugging_intelligence | expression | Monitor an expression. |

## conversational_tools (16 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `answer_code_question` | read | conversational | question, context | Answer questions using verified code intelligence. |
| `ask_clarifying_question` | read | conversational | context | Ask for missing information. |
| `compare_code_elements` | read | conversational | element1_id, element2_id | Explain differences between two code elements. |
| `detect_speaker_intent` | unclassified | none | text | Determine whether you're asking, commanding or interrupting. |
| `detect_voice_activity` | unclassified | none | audio_data | Identify when you start and stop speaking. |
| `explain_code_element` | unclassified | none | element_id, level | Explain a selected code element. |
| `explain_visualization` | read | conversational | visualization_id | Explain the current visualization. |
| `interrupt_current_response` | unclassified | none | - | Stop speaking when you interrupt. |
| `manage_conversation` | unclassified | none | user_message, context | Maintain conversational state. |
| `manage_conversation_preferences` | read | conversational | preferences | Manage verbosity and communication preferences. |
| `retrieve_conversation_context` | read | conversational | conversation_id, turn_range | Retrieve relevant previous conversation. |
| `retrieve_investigation_context` | read | conversational | investigation_id | Retrieve findings from previous investigations. |
| `speech_to_text` | unclassified | none | audio_data | Convert your voice into text. |
| `stream_voice_response` | unclassified | none | text | Speak responses as they are generated. |
| `summarize_investigation` | read | conversational | investigation_id, format | Summarize an investigation. |
| `text_to_speech` | unclassified | none | text | Speak JARVIS's response. |

## software_engineering_tools (47 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `apply_architecture_change` | unclassified | none | change_description, affected_components | Apply architecture change. |
| `apply_patch` | write | software_engineering | patch_content | Apply code patches in the worktree. Requires create_worktree to be called first. |
| `create_directory` | write | none | directory_path | Create directories in the worktree. Requires create_worktree to be called first. |
| `create_file` | write | none | file_path, content | Create new files in the worktree. Requires create_worktree to be called first. |
| `delete_file` | write | none | file_path | Delete files in the worktree. Requires create_worktree to be called first. |
| `edit_file` | write | software_engineering | file_path, old_content, new_content | Modify existing files in the worktree. Requires create_worktree to be called first. |
| `execute_command` | execute | none | command, working_directory | Execute commands in terminal. |
| `execute_script` | execute | none | script_path, arguments | Execute scripts. |
| `extract_function` | write | software_engineering | code_range, function_name | Extract function in the worktree. Requires create_worktree to be called first. |
| `format_code` | write | software_engineering | file_path, formatter | Format source code in the worktree. Requires create_worktree to be called first. |
| `generate_api` | unclassified | none | description, endpoints | Generate API. |
| `generate_class` | write | software_engineering | description, class_name | Generate class template in the worktree. Requires create_worktree to be called first. |
| `generate_component` | unclassified | none | description, component_type | Generate component. |
| `generate_database_model` | unclassified | none | description, schema | Generate database model. |
| `generate_documentation` | unclassified | none | element_id, format | Generate documentation. |
| `generate_function` | write | software_engineering | description, signature | Generate function template in the worktree. Requires create_worktree to be called first. |
| `generate_module` | unclassified | none | description, module_name | Generate module. |
| `git_blame` | unclassified | none | repository_path, file_path, line | Get git blame. |
| `git_branch` | unclassified | none | repository_path | List branches. |
| `git_commit` | write | none | repository_path, message | Commit changes. |
| `git_create_branch` | unclassified | none | repository_path, branch_name | Create branch. |
| `git_create_checkpoint` | unclassified | none | repository_path, label | Create checkpoint. |
| `git_diff` | read | software_engineering | repository_path, file_path | Get git diff. |
| `git_log` | unclassified | none | repository_path, limit | Get git log. |
| `git_revert` | unclassified | none | repository_path, commit_hash | Revert commit. |
| `git_show` | unclassified | none | repository_path, commit_hash | Show commit details. |
| `git_stash` | unclassified | none | repository_path | Stash changes. |
| `git_status` | unclassified | none | repository_path | Get git status. |
| `implement_interface` | unclassified | none | interface_id, class_name | Implement interface. |
| `inspect_command_output` | unclassified | none | command_id | Inspect command output. |
| `inspect_environment` | unclassified | none | - | Inspect environment. |
| `install_dependency` | execute | none | package_name, package_manager | Install dependencies. |
| `manage_environment_variables` | unclassified | none | action, variables | Manage environment variables. |
| `manage_processes` | unclassified | none | action, process_id | Manage processes. |
| `move_file` | write | none | source, destination | Move files in the worktree. Requires create_worktree to be called first. |
| `organize_imports` | write | software_engineering | file_path | Organize imports in the worktree. Requires create_worktree to be called first. |
| `refactor_function` | unclassified | none | function_id, refactoring_type | Refactor function. |
| `remove_dependency` | execute | none | package_name, package_manager | Remove dependencies. |
| `rename_file` | write | none | old_path, new_path | Rename files in the worktree. Requires create_worktree to be called first. |
| `rename_symbol` | write | software_engineering | old_name, new_name, scope | Rename symbol in the worktree. Requires create_worktree to be called first. |
| `run_build` | execute | none | build_config | Run build. |
| `run_compiler` | execute | none | source_files, compiler | Run compiler. |
| `run_formatter` | unclassified | none | file_path, formatter | Run formatter. |
| `run_linter` | execute | none | file_path, linter | Run linter. |
| `run_type_checker` | unclassified | none | file_path, type_checker | Run type checker. |
| `search_and_replace` | write | software_engineering | file_pattern, search, replace | Perform controlled replacements in the worktree. Requires create_worktree to be called first. |
| `update_references` | unclassified | none | symbol_id, new_location | Update references. |

## git_tools (7 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `apply_patch_to_worktree` | write | software_engineering | diff | Apply a unified diff inside the sandbox worktree. Fails if no worktree exists. |
| `commit_worktree` | unclassified | none | worktree, message | Called only by the /approve endpoint after a human pinch-hold. Commits on the sandbox branch. |
| `create_worktree` | write | software_engineering | branch_name | Create an isolated git worktree for a proposed patch. Never touches the main checkout. |
| `get_branch_info` | unclassified | none | - | Return branch, base branch and commit message of the change under review. |
| `get_diff` | unclassified | none | - | Return the unified diff of the change under review, with its branch name. |
| `get_worktree_diff` | read | software_engineering | - | Return the cumulative git diff of the sandbox worktree, including new files. |
| `list_changed_nodes` | unclassified | none | - | List graph node ids touched by the change under review. |

## runtime_intelligence_tools (20 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `attach_debugger` | execute | runtime_intelligence | application_id | Attach a debugger. |
| `attach_runtime_profiler` | execute | runtime_intelligence | application_id | Attach a profiler. |
| `capture_application_logs` | read | runtime_intelligence | application_id, since | Collect application logs. |
| `capture_runtime_events` | read | runtime_intelligence | application_id, event_types | Collect runtime events. |
| `collect_execution_trace` | read | runtime_intelligence | application_id, duration | Collect execution traces. |
| `compare_execution_traces` | read | runtime_intelligence | trace1_id, trace2_id | Compare different executions. |
| `record_async_tasks` | read | runtime_intelligence | application_id | Observe asynchronous tasks. |
| `record_cpu_usage` | read | runtime_intelligence | application_id | Monitor CPU utilization. |
| `record_database_activity` | read | runtime_intelligence | application_id | Observe database operations. |
| `record_execution_timing` | read | runtime_intelligence | application_id | Record execution duration. |
| `record_function_arguments` | read | runtime_intelligence | application_id, function_id | Record permitted argument information. |
| `record_function_calls` | read | runtime_intelligence | application_id, function_names | Record actual function calls. |
| `record_function_returns` | read | runtime_intelligence | application_id, function_id | Record return values. |
| `record_memory_usage` | read | runtime_intelligence | application_id | Monitor memory consumption. |
| `record_network_activity` | read | runtime_intelligence | application_id | Observe network operations. |
| `record_thread_activity` | read | runtime_intelligence | application_id | Observe threads. |
| `record_variable_state` | read | runtime_intelligence | application_id, variable_id | Observe selected runtime variables. |
| `replay_execution_trace` | read | runtime_intelligence | trace_id | Replay a captured execution where supported. |
| `start_application` | execute | runtime_intelligence | application_id, environment | Launch an application in an authorized environment. |
| `stop_application` | execute | runtime_intelligence | application_id | Stop an application. |

## data_flow_intelligence_tools (19 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `build_data_flow_graph` | read | data_flow_intelligence | scope | Build data flow graphs. |
| `identify_data_leaks` | read | data_flow_intelligence | data_id | Identify potential data exposure. |
| `identify_data_sinks` | read | data_flow_intelligence | variable_id | Identify where data ends up (database, API, file, etc.). |
| `identify_data_sources` | read | data_flow_intelligence | variable_id | Identify where data comes from (user input, database, API, etc.). |
| `identify_validation_gaps` | read | data_flow_intelligence | data_id | Identify missing input validation. |
| `trace_api_data_flow` | read | data_flow_intelligence | endpoint | Track data through API calls. |
| `trace_cross_function_flow` | read | data_flow_intelligence | variable_id | Track data across function boundaries. |
| `trace_cross_service_flow` | read | data_flow_intelligence | data_id | Track data across service boundaries. |
| `trace_database_reads` | read | data_flow_intelligence | query_id | Track data from database reads. |
| `trace_database_writes` | read | data_flow_intelligence | query_id | Track data to database writes. |
| `trace_file_operations` | read | data_flow_intelligence | file_path | Track data through file operations. |
| `trace_parameter_flow` | read | data_flow_intelligence | function_id, parameter | Track how a parameter flows through a function. |
| `trace_return_value_flow` | read | data_flow_intelligence | function_id | Track where return values flow. |
| `trace_state_changes` | read | data_flow_intelligence | component_id | Track state mutations. |
| `trace_taint_flow` | read | data_flow_intelligence | source | Track tainted data (security analysis). |
| `trace_transformations` | read | data_flow_intelligence | variable_id | Track data transformations. |
| `trace_variable_modifications` | read | data_flow_intelligence | variable_id | Track where a variable is modified. |
| `trace_variable_origin` | read | data_flow_intelligence | variable_id | Find where a variable's value originates. |
| `trace_variable_usage` | read | data_flow_intelligence | variable_id | Find where it is used. |

## orchestrator_tools (29 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `cancel_agent_task` | unclassified | none | agent | Cancel an agent's task. |
| `check_task_completion` | read | orchestrator | task | Check if a task is complete. |
| `classify_request` | read | orchestrator | request | Classify a user request into task type and required agents. |
| `create_investigation_plan` | read | orchestrator | request | Create an investigation plan for a request. |
| `decompose_task` | unclassified | none | task | Decompose a task into subtasks. |
| `delegate_task` | unclassified | none | agent, task | Delegate a task to an agent. |
| `get_agent_status` | unclassified | none | agent | Get the status of an agent. |
| `invoke_code_understanding` | unclassified | orchestrator | task | Invoke the Code Understanding agent. |
| `invoke_conversational` | unclassified | orchestrator | task | Invoke the Conversational JARVIS agent. |
| `invoke_data_flow_intelligence` | unclassified | orchestrator | task | Invoke the Data Flow Intelligence agent. |
| `invoke_debugging_intelligence` | unclassified | orchestrator | task | Invoke the Debugging Intelligence agent. |
| `invoke_relationship_intelligence` | unclassified | orchestrator | task | Invoke the Relationship Intelligence agent. |
| `invoke_repository_intelligence` | unclassified | orchestrator | task | Invoke the Repository Intelligence agent. |
| `invoke_runtime_intelligence` | unclassified | orchestrator | task | Invoke the Runtime Intelligence agent. |
| `invoke_security_quality` | unclassified | orchestrator | task | Invoke the Security and Quality agent. |
| `invoke_software_engineering` | unclassified | orchestrator | task | Invoke the Software Engineering agent. |
| `invoke_testing_verification` | unclassified | orchestrator | task | Invoke the Testing and Verification agent. |
| `invoke_visualization_spatial` | unclassified | orchestrator | task | Invoke the Visualization and Spatial Intelligence agent. |
| `manage_task_priority` | unclassified | none | task, priority | Manage task priority. |
| `merge_agent_results` | read | orchestrator | results | Merge results from multiple agents. |
| `request_more_evidence` | read | orchestrator | agent | Request more evidence from an agent. |
| `request_user_approval` | unclassified | none | action | Request user approval for an action. |
| `resolve_conflicting_findings` | read | orchestrator | findings | Resolve conflicting findings from agents. |
| `retry_agent_task` | unclassified | none | agent | Retry an agent's task. |
| `run_agents_parallel` | unclassified | none | agents, task | Run multiple agents in parallel. |
| `run_agents_sequentially` | unclassified | none | agents, task | Run multiple agents sequentially. |
| `select_agents` | unclassified | none | task | Select agents for a task. |
| `understand_user_intent` | read | orchestrator | question | Understand the user's intent from a natural language question. |
| `wait_for_agent` | unclassified | none | agent | Wait for an agent to complete. |

## external_integrations_toolkit (36 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `cancel_ci_build` | unclassified | none | pipeline_id | Cancel a CI/CD build. |
| `cloud_describe_instance` | unclassified | none | instance_id, provider | Describe cloud instance. |
| `cloud_execute_command` | unclassified | none | instance_id, command, provider | Execute command on cloud instance. |
| `cloud_get_instance_logs` | unclassified | none | instance_id, provider | Get cloud instance logs. |
| `cloud_list_instances` | unclassified | none | provider | List cloud instances. |
| `create_issue` | unclassified | none | tracker, title, description | Create an issue in the issue tracker. |
| `database_execute` | unclassified | none | connection_string, statement | Execute database statement. |
| `database_get_schema` | unclassified | none | connection_string | Get database schema. |
| `database_query` | unclassified | none | connection_string, query | Execute database query. |
| `docker_exec_command` | unclassified | none | container_id, command | Execute command in Docker container. |
| `docker_get_container_logs` | unclassified | none | container_id | Get Docker container logs. |
| `docker_inspect_container` | unclassified | none | container_id | Inspect Docker container. |
| `docker_list_containers` | unclassified | none | - | List Docker containers. |
| `error_tracking_get_error_details` | unclassified | none | error_id | Get error details. |
| `error_tracking_get_errors` | unclassified | none | service | Get errors from error tracking. |
| `error_tracking_resolve_error` | unclassified | none | error_id | Resolve an error. |
| `get_ci_logs` | unclassified | none | pipeline_id | Get CI/CD build logs. |
| `get_ci_status` | unclassified | none | pipeline_id | Get CI/CD pipeline status. |
| `get_issue` | unclassified | none | tracker, issue_id | Get issue details. |
| `github_get_commits` | unclassified | none | owner, repo, branch | Get commits from GitHub. |
| `github_get_issues` | unclassified | none | owner, repo, state | Get issues from GitHub. |
| `github_get_pull_requests` | unclassified | none | owner, repo, state | Get pull requests from GitHub. |
| `github_get_repository` | unclassified | none | owner, repo | Get repository information from GitHub. |
| `kubernetes_describe_pod` | unclassified | none | pod_name, namespace | Describe Kubernetes pod. |
| `kubernetes_exec_command` | unclassified | none | pod_name, namespace, command | Execute command in Kubernetes pod. |
| `kubernetes_get_deployments` | unclassified | none | namespace | Get Kubernetes deployments. |
| `kubernetes_get_pod_logs` | unclassified | none | pod_name, namespace | Get Kubernetes pod logs. |
| `kubernetes_list_pods` | unclassified | none | namespace | List Kubernetes pods. |
| `list_issues` | unclassified | none | tracker, filters | List issues. |
| `monitoring_create_alert` | unclassified | none | condition | Create monitoring alert. |
| `monitoring_get_metrics` | unclassified | none | service | Get monitoring metrics. |
| `monitoring_query_metrics` | unclassified | none | query | Query monitoring metrics. |
| `package_get_version` | unclassified | none | registry, package | Get package version. |
| `package_search` | unclassified | none | registry, query | Search package registry. |
| `trigger_ci_build` | unclassified | none | pipeline_id | Trigger a CI/CD build. |
| `update_issue` | unclassified | none | tracker, issue_id, updates | Update an issue. |

## infrastructure_services (49 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `check_approval_status` | unclassified | none | approval_id | Check if approval has been granted. |
| `check_permission` | unclassified | none | tool_name, agent_id, operation | Check if an agent has permission to use a tool. |
| `clear_graph` | unclassified | none | - | Clear the entire code graph. |
| `create_sandbox` | unclassified | none | sandbox_id, configuration | Create a sandbox for code execution. |
| `create_workflow` | unclassified | none | workflow_name, steps | Create a workflow. |
| `delete_graph_edge` | unclassified | none | from_id, to_id | Delete an edge from the code graph. |
| `delete_graph_node` | unclassified | none | node_id | Delete a node from the code graph. |
| `delete_memory` | unclassified | none | key | Delete a value from memory. |
| `destroy_sandbox` | unclassified | none | sandbox_id | Destroy a sandbox. |
| `discover_tools` | unclassified | none | module_path | Discover tools in a module. |
| `execute_in_sandbox` | unclassified | none | sandbox_id, command | Execute a command in a sandbox. |
| `execute_workflow` | unclassified | none | workflow_id | Execute a workflow. |
| `get_agent_messages` | unclassified | none | agent_id | Get messages for an agent. |
| `get_agent_state` | unclassified | none | agent_id | Get agent state. |
| `get_evidence` | unclassified | none | investigation_id | Get evidence for an investigation. |
| `get_graph_node` | unclassified | none | node_id | Retrieve a node from the code graph. |
| `get_index_status` | unclassified | none | repository_path | Get indexing status. |
| `get_rendering_state` | unclassified | none | graph_id | Get the current rendering state. |
| `get_telemetry_data` | unclassified | none | collection_id, time_range | Get collected telemetry data. |
| `get_tool_definition` | unclassified | none | tool_name | Get tool definition from registry. |
| `get_workflow_status` | unclassified | none | workflow_id | Get workflow execution status. |
| `grant_permission` | unclassified | none | tool_name, agent_id, permission_level | Grant permission to an agent for a tool. |
| `list_agents` | unclassified | none | status | List agent instances. |
| `list_permissions` | unclassified | none | agent_id, tool_name | List permissions for agents or tools. |
| `list_tools` | unclassified | none | agent_id, permission_level | List available tools, optionally filtered by agent or permission level. |
| `publish_message` | unclassified | none | topic, message | Publish a message to a topic. |
| `query_graph` | unclassified | none | query | Query the code graph. |
| `register_tool` | unclassified | none | tool_name, tool_definition | Register a tool in the registry. |
| `render_graph` | unclassified | none | graph_id | Render a graph for VR display. |
| `request_sensitive_approval` | unclassified | none | operation, description | Request approval for sensitive operations. |
| `retrieve_memory` | unclassified | none | key | Retrieve a value from memory. |
| `revoke_permission` | unclassified | none | tool_name, agent_id | Revoke permission from an agent for a tool. |
| `send_message_to_agent` | unclassified | none | agent_id, message | Send a message to an agent. |
| `set_permission_level` | unclassified | none | permission_level | Set the default permission level for operations. |
| `start_agent` | unclassified | none | agent_id, agent_config | Start an agent instance. |
| `start_indexing` | unclassified | none | repository_path | Start indexing a repository. |
| `start_telemetry_collection` | unclassified | none | collection_id, metrics | Start collecting telemetry data. |
| `stop_agent` | unclassified | none | agent_id | Stop an agent instance. |
| `stop_telemetry_collection` | unclassified | none | collection_id | Stop collecting telemetry data. |
| `store_graph_edge` | unclassified | none | from_id, to_id, edge_data | Store an edge in the code graph. |
| `store_graph_node` | unclassified | none | node_id, node_data | Store a node in the code graph. |
| `store_memory` | unclassified | none | key, value | Store a value in memory. |
| `subscribe_to_topic` | unclassified | none | topic, callback | Subscribe to a topic. |
| `unregister_tool` | unclassified | none | tool_name | Unregister a tool from the registry. |
| `unsubscribe_from_topic` | unclassified | none | topic | Unsubscribe from a topic. |
| `update_index` | unclassified | none | repository_path, changed_files | Update index for changed files. |
| `update_rendering` | unclassified | none | graph_id, updates | Update the VR rendering. |
| `update_tool_definition` | unclassified | none | tool_name, tool_definition | Update tool definition in registry. |
| `verify_evidence` | unclassified | none | evidence_id | Verify that evidence is still valid. |

## testing_verification_tools (20 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `compare_before_after` | read | testing_verification | before_snapshot, after_snapshot | Compare results before and after changes. |
| `discover_tests` | read | testing_verification | repository_path, test_framework | Find existing tests. |
| `generate_edge_case_tests` | unclassified | none | function_id | Generate edge-case tests. |
| `generate_integration_tests` | unclassified | none | endpoint | Generate integration tests. |
| `generate_test_report` | unclassified | none | repository_path, format | Produce a verification report. |
| `generate_unit_tests` | unclassified | none | function_id | Generate unit tests. |
| `identify_untested_paths` | read | testing_verification | repository_path | Find paths without adequate coverage. |
| `map_tests_to_functions` | read | testing_verification | repository_path | Connect tests to functions. |
| `measure_branch_coverage` | unclassified | none | repository_path | Measure branch coverage. |
| `measure_test_coverage` | read | testing_verification | repository_path | Measure code coverage. |
| `run_end_to_end_tests` | unclassified | none | test_files | Execute end-to-end tests. |
| `run_fuzz_tests` | unclassified | none | target_function, duration | Fuzz inputs and behavior. |
| `run_integration_tests` | unclassified | none | test_files | Execute integration tests. |
| `run_property_tests` | unclassified | none | test_files | Execute property-based tests. |
| `run_regression_tests` | execute | testing_verification | test_files | Execute regression tests using pytest with JUnit XML output for reliable parsing. |
| `run_unit_tests` | execute | testing_verification | test_files | Execute unit tests using pytest with JUnit XML output for reliable parsing. |
| `verify_compilation` | read | testing_verification | repository_path | Check compilation. |
| `verify_lint` | read | testing_verification | repository_path, linter | Check lint rules. |
| `verify_security` | read | testing_verification | repository_path | Check security findings. |
| `verify_types` | read | testing_verification | repository_path | Check type correctness. |

## code_understanding_tools (16 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `compare_implementations` | unclassified | none | function1_id, function2_id | Compare multiple implementations. |
| `explain_algorithm` | unclassified | none | function_id | Explain the algorithm being used. |
| `explain_class` | read | code_understanding | class_id | Explain a class and its responsibilities. |
| `explain_condition` | read | code_understanding | condition_id | Explain conditional logic. |
| `explain_expression` | unclassified | none | expression, file_path, line | Explain an individual expression. |
| `explain_function` | read | code_understanding | function_id, level | Explain the function's purpose and behavior. |
| `explain_module` | read | code_understanding | module_path | Explain a module. |
| `explain_variable` | unclassified | none | variable_id | Explain a variable's purpose and usage. |
| `extract_function_contract` | read | code_understanding | function_id | Identify preconditions, postconditions and invariants. |
| `extract_function_signature` | unclassified | none | function_id | Extract parameters and return types. |
| `generate_code_summary` | unclassified | none | element_id | Create a concise semantic summary. |
| `identify_hidden_assumptions` | read | code_understanding | function_id | Find assumptions embedded in implementation. |
| `identify_side_effects` | read | code_understanding | function_id | Identify external effects of code execution. |
| `infer_code_intent` | read | code_understanding | function_id | Infer intended behavior from evidence. |
| `parse_function` | unclassified | none | function_id | Parse a function and its internal structure. |
| `trace_function_logic` | read | code_understanding | function_id | Explain the function's logic step by step. |

## scene_tools (8 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `dim_unrelated` | read | visualization_spatial | keep_ids | Fade every node not in keep_ids into the background. |
| `focus_camera` | read | visualization_spatial | node_id | Move the user's view toward this node. |
| `highlight_vr_path` | read | visualization_spatial | node_ids, color | Light up these nodes and the edges between them in the VR scene. |
| `open_code_panel` | read | visualization_spatial | node_id | Open a readable source panel in front of the user for this node. |
| `set_edge_style` | read | visualization_spatial | src, dst, style | Set an edge style: solid for parser-confirmed, dashed for AI-inferred, runtime for observed. |
| `show_approval_prompt` | unclassified | none | summary | Show an approve or reject panel the user answers with a pinch. |
| `show_ghost_diff` | read | visualization_spatial | node_id, diff | Show a proposed change as a translucent ghost node attached to node_id. Nothing is applied. |
| `show_test_badges` | read | visualization_spatial | passed_ids, failed_ids, not_run_ids | Attach pass, fail and not-run badges to nodes. |

## control_tools (2 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `exit_loop` | unclassified | none | - | Stop the enclosing verify loop. Call only when tests have passed. |
| `request_approval` | read | orchestrator | action_summary | Ask the user to approve a consequential action. Shows an approve or reject panel and |

## documentation_toolkit (18 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `extract_docstrings` | read | code_understanding | file_path | Extract docstrings from source code. |
| `generate_architecture_doc` | unclassified | none | repository_path | Generate architecture documentation. |
| `generate_code_documentation` | unclassified | none | element_id, format | Generate documentation for code elements. |
| `generate_dependency_documentation` | unclassified | none | repository_path | Generate dependency documentation. |
| `generate_function_documentation` | unclassified | none | function_id | Generate function documentation. |
| `generate_investigation_report` | unclassified | none | investigation_id | Generate investigation report. |
| `read_documentation` | unclassified | none | doc_path | Read documentation file. |
| `retrieve_knowledge` | unclassified | none | key | Retrieve from knowledge base. |
| `search_api_docs` | unclassified | none | api_name, query | Search API documentation. |
| `search_discussions` | unclassified | none | repository, query | Search discussions. |
| `search_documentation` | unclassified | none | repository_path, query | Search project documentation. |
| `search_external_docs` | unclassified | none | query | Search external documentation. |
| `search_framework_docs` | unclassified | none | framework, query | Search framework documentation. |
| `search_issues` | unclassified | none | repository, query | Search issues. |
| `search_library_docs` | unclassified | none | library, query | Search library documentation. |
| `search_prs` | unclassified | none | repository, query | Search pull requests. |
| `update_knowledge` | unclassified | none | key, value | Update knowledge base. |
| `verify_documentation_coverage` | unclassified | none | repository_path | Check documentation coverage. |

## navigation_tools (10 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `find_implementations` | unclassified | none | symbol_name | Find implementations of interfaces, traits and abstract methods. |
| `get_call_hierarchy` | unclassified | none | symbol_name, direction | Retrieve incoming and outgoing calls. |
| `get_exports` | read | code_understanding | file_path | Identify exported symbols. |
| `get_imports` | read | code_understanding | file_path | Identify imported modules and symbols. |
| `get_scope_information` | read | code_understanding | file_path, line | Understand local and enclosing scopes. |
| `get_symbol_definition` | read | code_understanding | symbol_name | Find where a symbol is defined. |
| `get_symbol_documentation` | unclassified | none | symbol_name | Retrieve associated documentation. |
| `get_symbol_hover_info` | read | code_understanding | symbol_name | Retrieve types, documentation and signatures. |
| `get_symbol_references` | read | code_understanding | symbol_name | Find every reference to a symbol. |
| `get_type_hierarchy` | read | code_understanding | symbol_name | Retrieve inheritance and implementation relationships. |

## graph_tools (11 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `find_tests_for_node` | unclassified | none | node_id | Return tests that cover node_id. An empty list means the node is untested. |
| `get_callees` | unclassified | none | node_id, depth | Return functions that node_id calls, up to `depth` hops away. |
| `get_callers` | unclassified | none | node_id, depth | Return functions that call node_id, up to `depth` hops away. |
| `get_cluster` | unclassified | none | cluster | List all nodes in a named cluster (for example auth, api, db). |
| `get_coverage` | unclassified | none | node_id | Return line coverage (0 to 1) for node_id, or null if unknown. |
| `get_dependents` | unclassified | none | node_id, max_depth | Return everything that transitively depends on node_id through calls or imports. |
| `get_node` | unclassified | none | node_id | Return details for one node: file, line range, cluster, complexity, churn and coverage. |
| `get_source` | unclassified | none | node_id, context_lines | Return the source text of a node from the repository, with optional extra lines around it. |
| `search_graph_symbols` | unclassified | none | query, limit | Find code symbols whose name, id or file path matches the query words. |
| `trace_path` | unclassified | none | src_id, dst_id | Find the shortest call or import path from src_id to dst_id. |
| `verify_citations` | read | visualization_spatial | node_ids | Check that each node id exists in the graph. Returns valid and invalid lists. |

## repository_tools (11 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `get_changed_files` | read | repository_intelligence | since_revision, repository_path | Identify modifications since a particular revision. |
| `get_file_metadata` | unclassified | none | file_path | Retrieve size, language, timestamps and other metadata. |
| `get_repository_metadata` | read | repository_intelligence | repository_path | Retrieve branches, remotes, languages and project information. |
| `list_files` | read | repository_intelligence | directory, recursive, pattern | Explore directory and file structures. |
| `list_repositories` | unclassified | none | - | Discover all available repositories in the workspace. |
| `open_repository` | unclassified | none | repository_path | Load a repository for analysis. |
| `read_file` | read | repository_intelligence, software_engineering | file_path | Read source files. |
| `read_file_range` | read | code_understanding | file_path, start_line, end_line | Read specific line ranges from a file. |
| `search_code` | read | repository_intelligence, software_engineering | query, file_pattern, directory | Search source code in one repository (default: the active repository). |
| `search_files` | unclassified | none | pattern, directory, file_extension | Search files by name, extension or pattern. |
| `watch_repository` | unclassified | none | repository_path | Detect file additions, deletions and modifications. |

## vr_specific_tools (17 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `get_environment_info` | unclassified | none | environment_id | Get environment information. |
| `get_hand_interaction_state` | unclassified | none | - | Get current hand interaction state. |
| `get_selected_object` | unclassified | none | - | Identify the currently selected code element or graph node. |
| `get_vr_session_state` | unclassified | none | - | Understand the current VR session. |
| `list_voice_commands` | unclassified | none | - | List registered voice commands. |
| `load_scene_state` | unclassified | none | state_id | Load a saved scene state. |
| `process_voice_command` | unclassified | none | command | Process a voice command. |
| `register_voice_command` | unclassified | none | command_text, action | Register a custom voice command. |
| `reset_camera` | unclassified | none | - | Reset camera to default position. |
| `save_scene_state` | unclassified | none | state_id | Save current scene state. |
| `set_hand_interaction_mode` | unclassified | none | mode | Set hand interaction mode. |
| `set_haptic_feedback` | unclassified | none | intensity, duration | Set haptic feedback. |
| `set_layout_algorithm` | unclassified | none | algorithm | Set graph layout algorithm. |
| `set_spatial_audio` | unclassified | none | source_id, position | Set spatial audio source. |
| `set_spatial_scaling` | unclassified | none | scale | Set spatial scaling. |
| `set_theme` | unclassified | none | theme_id | Set visualization theme. |
| `set_vr_environment` | unclassified | none | environment_id | Set VR environment. |

## findings_tools (3 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `get_findings` | read | code_understanding | status | Get findings from state, optionally filtered by status. |
| `record_finding` | read | code_understanding | claim, status, confidence, evidence, unknowns, repository_id, repository_revision | Record a finding from the current agent. |
| `verify_finding` | read | none | claim, verification_status, verification_notes | Verify a finding by an independent agent or process. |

## memory_tools (3 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `load_project_memory` | unclassified | none | - | Return saved findings, decisions and the last session summary for this project. |
| `record_decision` | unclassified | none | decision | Record a decision the user approved or rejected. |
| `save_finding` | unclassified | none | summary, node_ids | Save an investigation finding with the node ids that support it. |

## exec_tools (3 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `read_test_results` | read | testing_verification | - | Return the most recent test run from this session, or none if no tests have run. |
| `run_tests` | execute | testing_verification | test_files | Run only the given test files in the sandbox worktree and return per-test results. |
| `run_typecheck` | execute | testing_verification | - | Run the TypeScript type check in the sandbox worktree. Returns the first 40 lines of errors. |

## _common (1 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `record_evidence` | unclassified | none | node_ids | Append node ids to state['evidence'] without duplicates, keeping only the most recent MAX_EVIDENCE. |

## _safe (1 tools)

| Tool | Level | Agents | Parameters | What it does |
|---|---|---|---|---|
| `safe` | unclassified | none | fn | Turn any exception inside a tool into {'status': 'error'} so the model can recover and the turn survives. |