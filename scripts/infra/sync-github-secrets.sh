#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

REPO="${GITHUB_REPOSITORY:-i-am-neon/material-search}"

if [[ -f backend/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source backend/.env
  set +a
else
  echo "backend/.env not found; only environment-backed and provider-backed secrets will be synced"
fi

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
set_secret RENDER_API_KEY
set_secret LOGFIRE_TOKEN

if [[ -f "$HOME/.modal.toml" ]]; then
  python3 - "$REPO" <<'PY'
import subprocess
import sys
import tomllib
from pathlib import Path

repo = sys.argv[1]
modal_config = Path.home() / ".modal.toml"
data = tomllib.loads(modal_config.read_text(encoding="utf-8"))
profile = next(
    (
        values
        for values in data.values()
        if isinstance(values, dict) and values.get("active")
    ),
    None,
)
if not profile:
    print("Skipping Modal GitHub secrets: no active ~/.modal.toml profile")
    raise SystemExit(0)

for secret_name, modal_key in (
    ("MODAL_TOKEN_ID", "token_id"),
    ("MODAL_TOKEN_SECRET", "token_secret"),
):
    value = profile.get(modal_key)
    if not value:
        print(f"Skipping {secret_name}: active Modal profile has no {modal_key}")
        continue
    subprocess.run(
        ["gh", "secret", "set", secret_name, "--repo", repo],
        input=value.encode(),
        check=True,
    )
    print(f"Set GitHub secret {secret_name}")
PY
else
  echo "Skipping Modal GitHub secrets: ~/.modal.toml not found"
fi

gh secret list --repo "$REPO"
