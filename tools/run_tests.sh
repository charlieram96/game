#!/usr/bin/env bash
# Runs the Godot test suite headless. Refreshes the import/class cache first so
# newly added class_name scripts are visible.
#   tools/run_tests.sh            # all tests
#   tools/run_tests.sh dash       # only tests whose "file.method" contains "dash"
set -euo pipefail
GODOT="${GODOT:-godot}"
cd "$(dirname "$0")/.."
"$GODOT" --headless --import --path . >/dev/null 2>&1 || true
ARGS=()
if [[ $# -gt 0 ]]; then ARGS=(-- "--filter=$1"); fi
"$GODOT" --headless --path . res://tests/run_tests.tscn "${ARGS[@]}"
