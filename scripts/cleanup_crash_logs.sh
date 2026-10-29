#!/bin/bash
# Move Unity Mono crash logs to crash_logs directory

UI_DIR="/Users/adarsh/Documents/vr-agent/ui"
CRASH_DIR="$UI_DIR/crash_logs"

# Create crash_logs directory if it doesn't exist
mkdir -p "$CRASH_DIR"

# Move any mono_crash files from the ui directory to crash_logs
find "$UI_DIR" -maxdepth 1 -name "mono_crash*" -type f -exec mv {} "$CRASH_DIR/" \;

# Count moved files
count=$(ls -1 "$CRASH_DIR"/mono_crash* 2>/dev/null | wc -l)
echo "Crash logs organized: $count files in $CRASH_DIR"
