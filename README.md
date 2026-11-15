# vr-jarvis

JARVIS is a VR-native code intelligence system with specialist agents for repository analysis, architecture visualization, change impact, patch proposals, and test verification.

## Quick Start

### 1. Setup Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Set your Google API key for Gemini
export GOOGLE_API_KEY="your-api-key-here"

# Set a secure token (not 'dev-token' for network exposure)
export JARVIS_TOKEN="$(openssl rand -hex 16)"

# Optional: Set repository directory (default: ./repository)
export JARVIS_REPOSITORY_DIR="/path/to/your/repositories"

# Optional: Set monthly budget limit in USD (default: 100.0)
export JARVIS_MONTHLY_BUDGET="50.0"
```

### Demo mode (judged / public build)

```bash
export JARVIS_DEMO_MODE=1                  # 404s run/debug/IDE/edit/verify routes
export JARVIS_REPOSITORY_DIR="/path/to/demo-only-repo-dir"   # ONE demo repo inside
export JARVIS_DEMO_ANSWERS="server/demo_answers.json"         # scripted Q&A cache
export JARVIS_RECORD_DEMO=1                # while recording: save real /ask replies
export JARVIS_RATE_PER_MIN=6               # per-IP burst limit on /ask
export JARVIS_DAILY_ASK_CAP=300            # global daily cap on real model turns
```

In demo mode `/health` reports `"demo_mode": true`, the VR app hides the edit
panel, scripted questions (see `docs/demo_script.md`) answer instantly from
`demo_answers.json`, and failed model calls return a "busy" fallback instead of
an error. Set a hard spending cap in Google AI billing as well — the in-code
caps only protect against bursts.

### 3. Start the Server

```bash
# From project root
cd "$(git rev-parse --show-toplevel)"   # or your checkout of vr-jarvis
uvicorn jarvis_server:app --app-dir server --host 127.0.0.1 --port 8000
```

**Security Note**: The server will refuse to start on `0.0.0.0` (network accessible) unless `JARVIS_TOKEN` is set to a non-default value.

### 4. Unity Configuration

The connection settings live in `Assets/ShowcaseSamples/JarvisVR/Resources/JarvisServerSettings.asset`
(packed into the Quest build). Use the **JARVIS > Server** menu in the Editor:

1. **Generate a new token**, then start the server with the `export JARVIS_TOKEN=...` line it prints (the token must equal `JARVIS_TOKEN`).
2. **Use this computer** (Editor / XR Simulator, `http://127.0.0.1:8000`) or **Use this computer's LAN IP** (Quest; start uvicorn with `--host 0.0.0.0`).
3. **Test connection**. The Console should print `JARVIS: CONNECTED ...`.

`/health` needs no token, but every other endpoint does. A wrong token therefore shows "server online" in the
status bar while questions fail with "Unauthorized".

## Architecture

### Agent Specialists (9)

1. **Orchestrator** - Routes requests to specialists
2. **Conversational** - Q&A and explanation
3. **Repository Intelligence** - Project structure and metadata
4. **Code Understanding** - Symbol analysis and navigation
5. **Relationship Intelligence** - Call graphs and dependencies
6. **Data Flow Intelligence** - Variable tracing
7. **Software Engineering** - Code editing (worktree only)
8. **Testing & Verification** - Test execution (sandboxed)
9. **Visualization & Spatial** - VR scene commands

### Security Model

- **Sandbox**: All writes go to a git worktree, never the main checkout
- **Permissions**: Each agent has a permission ceiling (read/execute/write)
- **Guard**: Tools are checked against agent permissions before execution
- **Approval**: Destructive actions require explicit user approval
- **Audit**: All tool calls are logged with arguments and outcomes

### Tool Audit

Run the tool audit to check all tools:

```bash
python scripts/audit_tools.py
```

Run smoke tests:

```bash
pytest server/tests/test_tools_smoke.py -v
```

## Development

### Tool Development

Tools live in `server/ai_agents/tools/`. Follow these conventions:

1. Use `repo_root()` for repository paths, never `Path.cwd()`
2. Use `resolve_in_repo(path)` to validate paths stay inside the repository
3. Write tools must check `state['worktree']` and return `blocked` if missing
4. Add tools to `TOOLSETS` in `agents/toolsets.py`
5. Add permission level to `TOOL_LEVELS` in `agents/toolsets.py`
6. Mark unavailable tools with `status: 'unavailable'` and a hint

### Adding New Agents

1. Create agent file in `server/ai_agents/agents/`
2. Define toolset in `agents/toolsets.py`
3. Set permission ceiling in `PERMISSION_CEILINGS`
4. Register in `agents/registry.py`
5. Add to orchestrator routing logic

## Status

- ✓ Phase A: Tool safety and correctness (complete)
- ⏳ Phase B: Tool gaps (partial - spatial tools need Unity integration)
- ⏳ Phase C: Agent layer (partial - needs Gemini for evaluation)
- ⏳ Phase D: Server improvements (sessions persist in SQLite across restarts, are listed/resumable/deletable via `/sessions`, and are reaped after `JARVIS_SESSION_RETENTION_DAYS`; per-user sessions via the `X-Jarvis-User` header)
- ⏳ Phase E: Unity integration (requires Unity Editor)
- ⏳ Phase F: Verification (requires Gemini and headset)

## Unity Backend

The JARVIS workspace talks to the real server only. Start it with `JARVIS_REPO=<folder> uvicorn server.jarvis_server:app --port 8000`, then use **JARVIS → Server → Test connection** in Unity to verify.
