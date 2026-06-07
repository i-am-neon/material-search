#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
PYTHON="$BACKEND_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Backend virtualenv not found at $PYTHON" >&2
  echo 'Refresh it with: cd backend && uv pip install --python .venv/bin/python -e ".[dev]"' >&2
  exit 1
fi

cd "$BACKEND_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

exec "$PYTHON" -m app.model_services.warmup "$@"
