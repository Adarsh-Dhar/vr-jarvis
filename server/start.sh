#!/usr/bin/env bash
# Simple JARVIS server startup
# Usage: ./start.sh or ./start.sh <google-api-key>

set -e

cd "$(dirname "$0")/.."

# Load from .env if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set defaults
export GOOGLE_API_KEY="${GOOGLE_API_KEY:-$1}"
export JARVIS_TOKEN="${JARVIS_TOKEN:-dev-token}"
export JARVIS_ASK_TIMEOUT="${JARVIS_ASK_TIMEOUT:-170}"
export JARVIS_CACHED_TESTS="${JARVIS_CACHED_TESTS:-0}"

# Check for API key
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "Error: GOOGLE_API_KEY is required"
    echo "Usage: ./start.sh <your-google-api-key>"
    echo "Or set it in .env file: GOOGLE_API_KEY=your-key"
    exit 1
fi

# Ensure demo repo exists
[ -d repository/demo-account-service/.git ] || python3 scripts/make_demo_repo.py
# Optional: install npm deps if npm is available
if command -v npm &> /dev/null; then
    [ -d repository/demo-account-service/node_modules ] || (cd repository/demo-account-service && npm install --silent)
else
    echo "Warning: npm not found - demo repo tests may not work"
fi

echo "Starting JARVIS server on http://localhost:8000"
echo "Token: $JARVIS_TOKEN"
exec /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m uvicorn jarvis_server:app --app-dir server --host 0.0.0.0 --port 8000
