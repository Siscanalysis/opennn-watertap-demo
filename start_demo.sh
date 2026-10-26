#!/usr/bin/env bash
# Starts the WaterTAP simulator on http://127.0.0.1:8765/ and opens the demo page in the browser.
# Run ./setup.sh once first. Options go to the service, e.g. --no-browser. Ctrl+C stops it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-}"
if [ -z "$PY" ] && [ -f "$ROOT/to_show/simulator/python_path_posix.txt" ]; then
  PY="$(head -n 1 "$ROOT/to_show/simulator/python_path_posix.txt")"
fi
if [ -z "$PY" ] && [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
fi
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
  echo "The WaterTAP environment is not set up yet: run ./setup.sh first."
  exit 1
fi
# shellcheck source=/dev/null
. "$ROOT/to_show/simulator/system_libs.sh"
exec "$PY" -B "$ROOT/to_show/simulator/server.py" 8765 "$@"
