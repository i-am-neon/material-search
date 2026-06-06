#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_dir="$repo_root/backend"
venv_python="$backend_dir/.venv/bin/python"

if [[ ! -x "$venv_python" ]]; then
  cat >&2 <<EOF
Missing backend virtualenv at backend/.venv.

Create it with:
  cd backend
  python3 -m venv .venv
  uv pip install --python .venv/bin/python -e ".[dev]"
EOF
  exit 1
fi

cd "$backend_dir"
exec "$venv_python" -m pytest "$@"
