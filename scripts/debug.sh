#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
AUTOPILOT_DEBUG=1 uv run ap "$@" 2>&1 | tee logs/debug.log
