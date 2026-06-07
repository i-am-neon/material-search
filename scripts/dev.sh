#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_dir="$repo_root/backend"
frontend_dir="$repo_root/frontend"

api_host="127.0.0.1"
api_port="${API_PORT:-8000}"
client_host="127.0.0.1"
client_port="${CLIENT_PORT:-5173}"
client_path="${CLIENT_PATH:-/material-search/}"
run_worker=1

usage() {
  cat <<EOF
Usage: scripts/dev.sh [options]

Run the local Material Search monorepo development stack:
  - FastAPI backend on http://$api_host:<api-port>
  - Dramatiq worker for queued search runs
  - Vite frontend on http://$client_host:<client-port>$client_path

The backend uses backend/.env, so local development still talks to the deployed
Supabase, Modal, Gemini, and Redis services configured there.

Options:
  --api-port PORT       Backend port. Default: ${API_PORT:-8000}
  --client-port PORT    Frontend port. Default: ${CLIENT_PORT:-5173}
  --no-worker           Run only the API and frontend.
  -h, --help            Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-port)
      api_port="${2:-}"
      shift 2
      ;;
    --client-port)
      client_port="${2:-}"
      shift 2
      ;;
    --no-worker)
      run_worker=0
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$api_port" || -z "$client_port" ]]; then
  echo "Ports must be non-empty." >&2
  exit 2
fi

venv_dir="$backend_dir/.venv"
uvicorn_bin="$venv_dir/bin/uvicorn"
dramatiq_bin="$venv_dir/bin/dramatiq"

require_file() {
  local path="$1"
  local message="$2"
  if [[ ! -f "$path" ]]; then
    echo "$message" >&2
    exit 1
  fi
}

require_executable() {
  local path="$1"
  local message="$2"
  if [[ ! -x "$path" ]]; then
    echo "$message" >&2
    exit 1
  fi
}

require_file "$backend_dir/.env" "Missing backend/.env. Copy backend/.env.example and fill in the deployed service values."
require_executable "$uvicorn_bin" "Missing backend virtualenv. Run: cd backend && python3 -m venv .venv && uv pip install --python .venv/bin/python -e \".[dev]\""
if [[ "$run_worker" -eq 1 ]]; then
  require_executable "$dramatiq_bin" "Missing Dramatiq in backend virtualenv. Run: cd backend && uv pip install --python .venv/bin/python -e \".[dev]\""
fi
if [[ ! -d "$frontend_dir/node_modules" ]]; then
  echo "Missing frontend/node_modules. Run: cd frontend && npm install" >&2
  exit 1
fi

pids=()
names=()
shutting_down=0

prefix_output() {
  local name="$1"
  sed -u "s/^/[$name] /"
}

start_service() {
  local name="$1"
  shift
  (
    "$@"
  ) > >(prefix_output "$name") 2>&1 &
  pids+=("$!")
  names+=("$name")
}

shutdown() {
  if [[ "$shutting_down" -eq 1 ]]; then
    return
  fi
  shutting_down=1
  echo
  echo "Stopping local dev stack..."
  local pid
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}

trap shutdown INT TERM EXIT

export VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://$api_host:$api_port}"
export PYTHONUNBUFFERED=1

echo "Starting local dev stack:"
echo "  API:      http://$api_host:$api_port"
echo "  Client:   http://$client_host:$client_port$client_path"
echo "  API base: $VITE_API_BASE_URL"
if [[ "$run_worker" -eq 1 ]]; then
  echo "  Worker:   enabled"
else
  echo "  Worker:   disabled"
fi
echo

start_service api bash -lc "cd \"\$1\" && exec \"\$2\" app.main:app --reload --host \"\$3\" --port \"\$4\"" _ "$backend_dir" "$uvicorn_bin" "$api_host" "$api_port"

if [[ "$run_worker" -eq 1 ]]; then
  start_service worker bash -lc "cd \"\$1\" && exec \"\$2\" app.workers.catalog_indexing app.workers.search_runs --processes 1 --threads 1" _ "$backend_dir" "$dramatiq_bin"
fi

start_service client bash -lc "cd \"\$1\" && exec npm run dev -- --port \"\$2\"" _ "$frontend_dir" "$client_port"

while true; do
  for index in "${!pids[@]}"; do
    pid="${pids[$index]}"
    if ! kill -0 "$pid" 2>/dev/null; then
      set +e
      wait "$pid"
      status="$?"
      set -e
      echo "${names[$index]} exited with status $status" >&2
      exit "$status"
    fi
  done
  sleep 1
done
