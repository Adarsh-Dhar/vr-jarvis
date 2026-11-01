# vr-jarvis

JARVIS is a VR-native code intelligence system with 12 specialist agents for repository analysis, security, testing, and spatial visualization.

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

### 3. Start the Server

```bash
# From project root
cd /Users/adarsh/Documents/vr-agent
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

### Agent Specialists (12)

1. **Orchestrator** - Routes requests to specialists
2. **Conversational** - Q&A and explanation
3. **Repository Intelligence** - Project structure and metadata
4. **Code Understanding** - Symbol analysis and navigation
5. **Relationship Intelligence** - Call graphs and dependencies
6. **Data Flow Intelligence** - Variable tracing
7. **Runtime Intelligence** - Process monitoring (sandboxed)
8. **Debugging Intelligence** - Breakpoint debugging (sandboxed)
9. **Security & Quality** - Vulnerability scanning
10. **Software Engineering** - Code editing (worktree only)
11. **Testing & Verification** - Test execution (sandboxed)
12. **Visualization & Spatial** - VR scene commands

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
- ⏳ Phase D: Server improvements (partial - session persistence pending)
- ⏳ Phase E: Unity integration (requires Unity Editor)
- ⏳ Phase F: Verification (requires Gemini and headset)

## Mock UI Mode

Choose **JARVIS → Use mock data** in Unity to test without the backend.
