#!/usr/bin/env bash
# Wait for the gemini-3.5-flash-lite daily quota to reset, then run a clean
# baseline benchmark (repeats 1) on port 8000.
set -uo pipefail
cd "$(dirname "$0")/.."
KEY=$(grep '^GOOGLE_API_KEY=' .env | cut -d= -f2)
DEADLINE=$(( $(date +%s) + 4*3600 ))

probe() {
  # Require 3 successful calls: a single call can slip through while the
  # daily quota is still effectively exhausted.
  local ok=0 i
  for i in 1 2 3; do
    curl -s -m 30 "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key=$KEY" \
      -H 'Content-Type: application/json' \
      -d '{"contents":[{"parts":[{"text":"Say OK"}]}]}' | grep -q '"candidates"' && ok=$((ok+1))
  done
  [ "$ok" -eq 3 ]
}

echo "$(date) waiting for gemini-3.5-flash-lite quota..."
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  if probe; then echo "$(date) quota OK"; break; fi
  sleep 300
done
probe || { echo "$(date) quota still dead after deadline"; exit 1; }

scripts/eval_matrix.sh serve gemini-3.5-flash-lite gemini-3.5-flash-lite 8000
scripts/eval_matrix.sh run baseline-3.5-clean-r1 8000 gemini-3.5-flash-lite gemini-3.5-flash-lite \
  --benchmark jarvis-agent-evaluation/benchmarks/benchmark_demo-account-service.yaml \
  --graph server/ai_agents/data/index/demo-account-service.json \
  --repo demo-account-service --split all --repeats 1
echo "$(date) baseline run finished"
