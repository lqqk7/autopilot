#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
uv run ap "$@" 2>&1 | tee logs/autopilot.log
