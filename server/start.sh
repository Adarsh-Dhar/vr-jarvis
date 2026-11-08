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
export JARVIS_ASK_TIMEOUT="${JARVIS_ASK_TIMEOUT:-170}"
export JARVIS_CACHED_TESTS="${JARVIS_CACHED_TESTS:-0}"

# Check for API key
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "Error: GOOGLE_API_KEY is required"
    echo "Usage: ./start.sh <your-google-api-key>"
    echo "Or set it in .env file: GOOGLE_API_KEY=your-key"
    exit 1
fi

# Check for JARVIS_TOKEN (required for network access)
if [ -z "$JARVIS_TOKEN" ]; then
    echo "Error: JARVIS_TOKEN is required for secure operation"
    echo "Set it in .env file: JARVIS_TOKEN=your-secure-random-token"
    echo "For local development only, you can run with: JARVIS_TOKEN='' ./start.sh <api-key>"
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

# Set bind address and environment variable for security validation
export JARVIS_HOST="${JARVIS_HOST:-127.0.0.1}"

# If binding to 0.0.0.0 (network-exposed), require secure configuration
if [ "$JARVIS_HOST" = "0.0.0.0" ]; then
    if [ -z "$JARVIS_TOKEN" ] || [ "$JARVIS_TOKEN" = "dev-token" ]; then
        echo "Error: Binding to 0.0.0.0 requires a secure JARVIS_TOKEN"
        echo "Set JARVIS_TOKEN to a secure random value in .env or environment"
        exit 1
    fi
fi

echo "Starting JARVIS server on http://$JARVIS_HOST:8000"
echo "Token: $JARVIS_TOKEN"
exec /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m uvicorn jarvis_server:app --app-dir server --host "$JARVIS_HOST" --port 8000
