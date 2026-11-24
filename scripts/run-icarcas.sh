#!/usr/bin/env bash
# Launch iCarcas on macOS / Linux from the repo root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  echo "Python 3.12+ not found. Create .venv: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
  exit 1
fi

exec "$PY" -m ios_restore "$@"
