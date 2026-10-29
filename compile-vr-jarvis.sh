#!/usr/bin/env bash
# Run Unity's script compilation for the VR JARVIS project and save full + filtered logs.
# Usage: ./compile-vr-jarvis.sh [path/to/vr-jarvis-main]
#   If no path is provided, defaults to the current directory.
# Optional: UNITY_BIN=/full/path/to/Unity UNITY_TARGET=Android ./compile-vr-jarvis.sh
# Optional: FORCE_KILL_UNITY=true ./compile-vr-jarvis.sh  (auto-kill running Unity instances)
set -uo pipefail

ROOT="${1:-$(pwd)}"
ROOT="$(cd "$ROOT" 2>/dev/null && pwd)" || {
  echo "ERROR: project root does not exist: ${1}" >&2
  exit 66
}
PROJECT="$ROOT/ui"
VERSION_FILE="$PROJECT/ProjectSettings/ProjectVersion.txt"
if [[ ! -f "$VERSION_FILE" || ! -f "$PROJECT/Packages/manifest.json" ]]; then
  echo "ERROR: '$ROOT' does not look like this repository root (expected ui/ProjectSettings and ui/Packages)." >&2
  exit 66
fi

EXPECTED_VERSION="$(sed -n 's/^m_EditorVersion: //p' "$VERSION_FILE" | head -n 1 | tr -d '\r')"
DEFAULT_UNITY="/Applications/Unity/Hub/Editor/${EXPECTED_VERSION}/Unity.app/Contents/MacOS/Unity"
UNITY_BIN="${UNITY_BIN:-$DEFAULT_UNITY}"
UNITY_TARGET="${UNITY_TARGET:-OSXUniversal}"

if [[ ! -x "$UNITY_BIN" ]]; then
  echo "ERROR: Unity Editor executable not found or not executable:" >&2
  echo "  $UNITY_BIN" >&2
  echo "Project requires Unity ${EXPECTED_VERSION}. Install it in Unity Hub or set UNITY_BIN to its executable." >&2
  echo "Installed editors found:" >&2
  find /Applications/Unity/Hub/Editor -maxdepth 4 -path '*/Unity.app/Contents/MacOS/Unity' -type f -print 2>/dev/null | sort >&2 || true
  exit 127
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
FULL_LOG="$LOG_DIR/unity-compile-${STAMP}.log"
ERROR_LOG="$LOG_DIR/unity-errors-${STAMP}.txt"

printf 'Project:       %s\n' "$PROJECT"
printf 'Required Unity: %s\n' "$EXPECTED_VERSION"
printf 'Unity binary:  %s\n' "$UNITY_BIN"
printf 'Compile target: %s\n' "$UNITY_TARGET"
printf 'Full log:      %s\n' "$FULL_LOG"
printf 'Error summary: %s\n\n' "$ERROR_LOG"

# Check for running Unity instances
UNITY_PIDS=$(pgrep -i "Unity" || true)
if [[ -n "$UNITY_PIDS" ]]; then
  echo "WARNING: Unity is currently running (PIDs: $UNITY_PIDS)"
  echo "Unity cannot compile if another instance has the project open."
  if [[ "${FORCE_KILL_UNITY:-}" == "true" ]]; then
    echo "FORCE_KILL_UNITY is set. Killing Unity instances..."
    pkill -9 -i "Unity" || true
    sleep 2
  else
    echo "Please close Unity manually, or run with FORCE_KILL_UNITY=true to auto-kill:"
    echo "  FORCE_KILL_UNITY=true ./compile-vr-jarvis.sh"
    exit 1
  fi
fi

# -quit opens/imports the project and waits for Unity's script compilation cycle to finish.
set +e
"$UNITY_BIN" -batchmode -accept-apiupdate -nographics -projectPath "$PROJECT" -buildTarget "$UNITY_TARGET" -logFile "$FULL_LOG" -quit
UNITY_STATUS=$?
set -e

# Keep compiler/package-resolution diagnostics in a small file; the full log above is authoritative.
# Filter out non-critical SDK warnings like Android build target checks
grep -n -C 2 -Ei \
  'error CS[0-9]+|error BC[0-9]+|scripts have compiler errors|script compilation failed|compilation failed|failed to resolve packages|package manager.*(error|fail)|error while compiling' \
  "$FULL_LOG" > "$ERROR_LOG" || true
# Remove Android build target warnings (non-critical)
sed -i '' '/Build target directory for AndroidPlayer does not exist/d' "$ERROR_LOG" 2>/dev/null || true

if grep -qEi 'error CS[0-9]+|error BC[0-9]+|scripts have compiler errors|script compilation failed|compilation failed' "$FULL_LOG"; then
  echo "RESULT: Unity compilation reported errors. See: $ERROR_LOG"
  echo "Full editor log: $FULL_LOG"
  echo
  cat "$ERROR_LOG"
  exit 1
fi

# Check if Unity completed batchmode successfully (even if it crashed during cleanup)
if grep -qi "Exiting batchmode successfully" "$FULL_LOG"; then
  echo "RESULT: No C# compiler errors were detected in the captured Unity startup/import log."
  echo "Unity batchmode completed successfully (cleanup crash may be ignored)."
  echo "This is not the same as a successful Android APK build. Full editor log: $FULL_LOG"
  exit 0
fi

if [[ "$UNITY_STATUS" -ne 0 ]]; then
  echo "RESULT: Unity exited with status $UNITY_STATUS. Inspect the full log for package/import/editor startup failures: $FULL_LOG" >&2
  [[ -s "$ERROR_LOG" ]] && cat "$ERROR_LOG"
  exit "$UNITY_STATUS"
fi

echo "RESULT: No C# compiler errors were detected in the captured Unity startup/import log."
echo "This is not the same as a successful Android APK build. Full editor log: $FULL_LOG"
