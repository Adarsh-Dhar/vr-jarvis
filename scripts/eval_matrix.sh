#!/usr/bin/env bash
# Model-evaluation helpers. Two modes:
#
#   scripts/eval_matrix.sh serve <full-model> <lite-model> <port>
#       (Re)start a JARVIS server on <port> with the given models and wait for
#       /health. The server keeps running after this script exits.
#
#   scripts/eval_matrix.sh run <tag> <port> <full-model> <lite-model> [http_runner args...]
#       Run the HTTP benchmark against the server on <port>.
#
# Example (two configs in parallel):
#   scripts/eval_matrix.sh serve gemini-3.5-flash-lite gemini-3.5-flash-lite 8000
#   scripts/eval_matrix.sh serve gemini-3.8-flash    gemini-3.5-flash-lite 8001
#   scripts/eval_matrix.sh run baseline-3.5 8000 --benchmark ... --shard 0/2 &
#   scripts/eval_matrix.sh run cand-3.8    8001 --benchmark ... --shard 0/2 &
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:?serve|run}"; shift
# Eval token: JARVIS_EVAL_TOKEN, else JARVIS_TOKEN from .env (never hard-code it here).
TOKEN="${JARVIS_EVAL_TOKEN:-$(grep '^JARVIS_TOKEN=' .env 2>/dev/null | head -1 | cut -d= -f2-)}"
[ -n "$TOKEN" ] || { echo "set JARVIS_EVAL_TOKEN or JARVIS_TOKEN in .env" >&2; exit 2; }

if [ "$MODE" = serve ]; then
    FULL="${1:?full model}"; LITE="${2:?lite model}"; PORT="${3:?port}"
    OLD=$(lsof -tiTCP:$PORT -sTCP:LISTEN || true)
    [ -n "$OLD" ] && kill $OLD && sleep 2

    # Pass EVERY key to the server so it can rotate: GOOGLE_API_KEY, GOOGLE_API_KEY_1, ..., JARVIS_API_KEYS.
    # (Keys already set in the shell win over .env.)
    while IFS='=' read -r k v; do
        [ -n "${!k:-}" ] && continue
        v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
        export "$k=$v"
    done < <(grep -E '^(GOOGLE_API_KEY(_[0-9]+)?|JARVIS_API_KEYS)=' .env 2>/dev/null || true)
    # The per-IP and daily ask limits are for the public build; a benchmark would hit them at once.
    export JARVIS_RATE_PER_MIN=100000 JARVIS_DAILY_ASK_CAP=1000000
    export JARVIS_TOKEN="$TOKEN"
    export JARVIS_ASK_TIMEOUT=170 JARVIS_CACHED_TESTS=0 JARVIS_HOST=127.0.0.1
    # /ask enforces TURN_TIMEOUT (default 120s); slower full models need more
    # headroom for a 15-25-call turn. Baseline never hit 120s, so this does
    # not advantage candidates. Kept under the runner's 300s client timeout.
    export JARVIS_TURN_TIMEOUT=280
    # In-memory sessions: parallel eval servers must not share the sqlite file.
    export JARVIS_SESSION_BACKEND=memory
    # Each benchmark case creates its own session; the 50-session default plus
    # the 1h idle timeout fills up mid-run and /ask starts returning 429
    # CAPACITY_EXCEEDED (counted as infra errors, not model failures).
    export JARVIS_MAX_SESSIONS=20000 JARVIS_SESSION_IDLE_TIMEOUT=120
    export JARVIS_LLM_ATTEMPTS=5 JARVIS_LLM_RETRY_DELAY=5 JARVIS_LLM_MAX_DELAY=60 JARVIS_LLM_RPM=0
    export JARVIS_MODEL="$FULL" JARVIS_MODEL_LITE="$LITE"

    nohup python3 -m uvicorn jarvis_server:app --app-dir server \
        --host 127.0.0.1 --port "$PORT" > "logs/server-$PORT.log" 2>&1 &
    disown

    for i in $(seq 1 60); do
        curl -s -m 2 "http://127.0.0.1:$PORT/health" >/dev/null && break
        sleep 2
    done
    curl -s "http://127.0.0.1:$PORT/health" | grep -q '"ok":true' || {
        echo "server on $PORT failed to start"; tail -20 "logs/server-$PORT.log"; exit 1; }
    echo "server on $PORT ready: full=$FULL lite=$LITE"
    exit 0
fi

if [ "$MODE" = run ]; then
    TAG="${1:?tag}"; PORT="${2:?port}"; FULL="${3:?full model}"; LITE="${4:?lite model}"; shift 4
    export JARVIS_TOKEN="$TOKEN" JARVIS_MODEL="$FULL" JARVIS_MODEL_LITE="$LITE" \
        JARVIS_LLM_ATTEMPTS=5 JARVIS_LLM_RPM=0
    exec python3 jarvis-agent-evaluation/runner/http_runner.py \
        --base-url "http://127.0.0.1:$PORT" --tag "$TAG" "$@"
fi

echo "unknown mode: $MODE" >&2; exit 2
