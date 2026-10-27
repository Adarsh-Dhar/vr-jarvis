# Testing the JARVIS agents

Drop these files into the repo root (next to `ai_agents/` and `ui/`):

```
pip install -r requirements-test.txt
python -m pytest tests -q          # fast, offline, no API key needed
```

The suite imports your package through `tests/harness/pkg.py` (default `ai_agents`; override with `JARVIS_PKG`).
Written and run against google-adk 2.12.0. ADK class and argument names move between releases, so if something
fails to import, check the harness files first (`harness/runner.py`, `harness/scripted_llm.py`).

## What is in it

| Layer | Folder | Needs a model? | What it proves |
|---|---|---|---|
| 1. Tools | `tests/unit` | no | Every graph tool matches an independent networkx oracle (depths, cycles, parallel edges, inferred edges, unknown ids), plus property tests on random graphs; git sandbox, test runner, scene commands, guard, memory; security (path escape, symlinks, patch paths); output limits; static checks on the agent tree |
| 3. Pipelines | `tests/pipelines` | no (scripted model) | The real agent tree, real tools and real ADK run end to end: routing, order, parallel step, state hand-off, verify loop (pass first time, fail then pass, never passes), escalation, approval, multi-turn, per-turn state |
| 4. Demo path | `tests/e2e` | scripted always, real model optional | The five-step demo, with latency budgets for the real-model run |
| 5. Stress | `tests/stress` | no, except `*_llm.py` | 5k/20k/50k-node scale, threads and 24 parallel sessions, injected faults (model errors, empty/garbage output, hung model, runaway loop, tool exceptions), injection guard, soak |
| 2. Agents | `tests/agents` | yes | Router accuracy (44 utterances), investigator vs oracle, impact agents vs oracle, critic red-team (9 seeded cases), scene director, patch agent, verifier |

How the scripted model works: `harness/scripted_llm.py` replaces only the model call. Each agent is scripted as a few tool
calls and a final text. Tools, state, callbacks, transfers, loops and parallel agents are the real code. This proves wiring,
not model quality.

## Running

| Command | What runs |
|---|---|
| `make test` | everything offline (about 30 s) |
| `make soak` | long loops: memory growth, worktree pile-up, prompt growth |
| `make llm` | real-model suites. Needs credentials. `JARVIS_TRIALS` sets repeats per case (default 5) |
| `make dry` | the real-model tests against the scripted model, to check the test code itself |

Knobs: `STRESS_SCALE` (graph sizes and session counts), `STRESS_LATENCY_FACTOR` (loosen timing on slow machines),
`JARVIS_LLM_CONCURRENCY`, `DEMO_TRIALS`, `JARVIS_SOAK_ITERATIONS`.

## Results on your current `ai_agents`

`21 failed, 582 passed, 44 skipped` (skipped = real-model and soak tests). Soak: 2 of 3 fail.
These are defects in the code, not in the tests:

| # | Finding | Failing tests |
|---|---|---|
| 1 | `get_source` follows `../`, absolute paths and symlinks out of the repo | 3 in `test_security` |
| 2 | `get_source` crashes on a missing file | 1 |
| 3 | `run_tests` crashes on a missing or corrupt cached-results file; `load_project_memory` crashes on a corrupt file | 3 |
| 4 | A live run that executes zero tests is reported as `passed` | 1 |
| 5 | Tool output is unbounded: a hub node with 2,000 dependents returns 352,000 characters (about 90k tokens) | 5 in `test_limits`, 3 in `test_scale` |
| 6 | `state['evidence']` grows without limit | 1 |
| 7 | Any exception inside a tool kills the whole turn, including a missing `graph.json` | 2 in `test_fault_injection` |
| 8 | Concurrent `save_finding` calls lose writes or corrupt `project_memory.json` | 1 |
| 9 | Scene director and others see the previous turn's `impact_report`, patch and test results | 1 |
| 10 | Prompt size grows about 8x over 40 turns, because the root agent replays every old tool result | soak |
| 11 | Sandbox worktrees pile up on disk | soak |

What already works: routing and order for all four pipelines, the parallel impact step, the verify loop (exit on pass, three
rounds then stop, repair then pass), escalation not ending the pipeline, the approval flow, the Tier 2 guard even when the model
obeys an injected instruction, 24 concurrent sessions with no state bleed, call-cap on a runaway loop, and recovery after a
model failure or a hung model. Patches that try to write outside the worktree were already refused by `git apply` itself.

## The hardening overlay

`hardening/ai_agents/` holds the changed files, based on your current code. Commit first, then `make harden` and diff.
With it applied: `606 passed, 41 skipped`, soak `3 passed`. What changed:

- `tools/_safe.py` (new): a decorator that turns tool exceptions into `{'status': 'error'}`. Applied to all graph, git, exec and memory tools.
- `graph_tools.py`: `MAX_RESULTS=200` and `MAX_SOURCE_LINES=400` with `total` and `truncated` flags; `get_source` confined to the repo.
- `_common.py`: evidence capped at `MAX_EVIDENCE=500`.
- `exec_tools.py`: zero executed tests is an error, not a pass.
- `git_tools.py`: patch paths validated, worktree creation serialized, oldest sandboxes pruned past `MAX_WORKTREES=10`.
- `memory_tools.py`: lock and atomic write.
- `callbacks.py`, `state.py`, `agents/fix.py`: per-turn results are cleared each turn; the last impact report is kept as `impact_context` for the patch agent; `trim_history` shrinks old turns for the root agent.
- `agent.py` and every file in `agents/`: sub-agents use `include_contents='none'`, so they work from state plus the current request. The root keeps a short text history through `trim_history`.

Two trade-offs to know about: sub-agents no longer see earlier conversation text (they get everything from state), and a worktree
older than the newest ten can be removed while a very old session still points at it.

## Not covered

- The 38 real-model tests were run only in dry mode, so their mechanics work but agent quality is unmeasured. Run `make llm` and read the failures: they are your real accuracy numbers.
- The Unity client is not tested. The contract with it is the scene-command schema in `harness/schemas.py`, so the C# side can be tested against the same list.
- Timing budgets depend on the machine. Loosen them with `STRESS_LATENCY_FACTOR` instead of editing tests.
- Live Jest and `tsc` runs are tested with stubbed subprocess output, not against a real Node project.
