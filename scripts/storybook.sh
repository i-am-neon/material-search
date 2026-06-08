#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
frontend_dir="$repo_root/frontend"

if [[ ! -d "$frontend_dir/node_modules" ]]; then
  cat >&2 <<EOF
Missing frontend/node_modules.

Install frontend dependencies with:
  cd frontend
  npm install
EOF
  exit 1
fi

cd "$frontend_dir"
exec npm run storybook -- "$@"
