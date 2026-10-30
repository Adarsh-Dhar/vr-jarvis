#!/usr/bin/env bash
# Run from the repo root. Needs GOOGLE_API_KEY (or Vertex env) for the Gemini model.
set -e
cd "$(dirname "$0")/.."
[ -d repository/demo-account-service/.git ] || python3 scripts/make_demo_repo.py
[ -d repository/demo-account-service/node_modules ] || (cd repository/demo-account-service && npm install --silent)
export JARVIS_CACHED_TESTS="${JARVIS_CACHED_TESTS:-0}"   # 0 = really run jest in the sandbox worktree
exec uvicorn server.jarvis_server:app --host 0.0.0.0 --port 8000
