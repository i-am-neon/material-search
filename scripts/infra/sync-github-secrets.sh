#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

REPO="${GITHUB_REPOSITORY:-i-am-neon/material-search}"

if [[ ! -f backend/.env ]]; then
  echo "backend/.env is required" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source backend/.env
set +a

set_secret() {
  local key="$1"
  local value="${!key:-}"
  if [[ -z "$value" ]]; then
    echo "Skipping $key: not set"
    return
  fi
  printf "%s" "$value" | gh secret set "$key" --repo "$REPO"
  echo "Set GitHub secret $key"
}

set_secret DATABASE_URL
set_secret EMBEDDING_SERVICE_URL
set_secret SAM3_SERVICE_URL
set_secret GEMINI_API_KEY

gh secret list --repo "$REPO"
