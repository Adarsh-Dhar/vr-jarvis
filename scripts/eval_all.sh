#!/usr/bin/env bash
# One full evaluation of one model configuration on both benchmark repos.
#   scripts/eval_all.sh <tag> <full-model> <lite-model> [repeats]
#   SPLIT=dev|test|all (default dev)   PORT=8100
# Starts a server with that config, runs demo-account-service and rp, prints the summary table.
set -euo pipefail
cd "$(dirname "$0")/.."
TAG="${1:?tag}"; FULL="${2:?full model}"; LITE="${3:?lite model}"; REPEATS="${4:-3}"
PORT="${PORT:-8100}"; SPLIT="${SPLIT:-dev}"
scripts/eval_matrix.sh serve "$FULL" "$LITE" "$PORT"
for R in demo-account-service rp; do
    scripts/eval_matrix.sh run "$TAG-$R" "$PORT" "$FULL" "$LITE" \
        --benchmark "jarvis-agent-evaluation/benchmarks/benchmark_$R.yaml" \
        --graph "server/ai_agents/data/index/$R.json" \
        --repo "$R" --split "$SPLIT" --repeats "$REPEATS"
done
python3 scripts/eval_report.py
