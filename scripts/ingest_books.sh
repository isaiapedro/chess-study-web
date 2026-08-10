#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="${LOG:-/tmp/full_ingest.log}"
PIDFILE="${PIDFILE:-/tmp/full_ingest.pid}"
# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONUNBUFFERED=1
echo "Logging to $LOG"
setsid python -m chess_coach ingest data/books "$@" >>"$LOG" 2>&1 < /dev/null &
echo $! >"$PIDFILE"
echo "Started ingest PID=$(cat "$PIDFILE")"
echo "Watch: tail -f $LOG"
