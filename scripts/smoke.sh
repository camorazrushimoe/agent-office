#!/usr/bin/env bash
# Agent Office — foundation smoke wrapper
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/scripts/smoke.py" "$@"
