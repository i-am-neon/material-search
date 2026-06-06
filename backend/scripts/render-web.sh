#!/usr/bin/env bash
set -euo pipefail

worker_pid=""
api_pid=""

shutdown() {
  if [[ -n "$worker_pid" ]] && kill -0 "$worker_pid" 2>/dev/null; then
    kill "$worker_pid" 2>/dev/null || true
  fi
  if [[ -n "$api_pid" ]] && kill -0 "$api_pid" 2>/dev/null; then
    kill "$api_pid" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}

trap shutdown INT TERM

if [[ -n "${REDIS_URL:-}" ]]; then
  dramatiq app.workers.catalog_indexing app.workers.search_runs --processes 1 --threads 1 &
  worker_pid="$!"
  echo "Started Dramatiq worker in web service process: $worker_pid"
else
  echo "REDIS_URL is not set; starting API without embedded Dramatiq worker"
fi

uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" &
api_pid="$!"
echo "Started API process: $api_pid"

if [[ -n "$worker_pid" ]]; then
  wait -n "$worker_pid" "$api_pid"
else
  wait "$api_pid"
fi
status="$?"

shutdown
exit "$status"
