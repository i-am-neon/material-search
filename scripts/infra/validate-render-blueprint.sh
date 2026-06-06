#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

if command -v render >/dev/null 2>&1 && render workspace current >/dev/null 2>&1; then
  render blueprints validate render.yaml --output json
  exit 0
fi

if [[ -z "${RENDER_API_KEY:-}" ]]; then
  echo "RENDER_API_KEY is required when Render CLI is not logged in" >&2
  exit 1
fi

if [[ -z "${RENDER_OWNER_ID:-}" ]]; then
  echo "RENDER_OWNER_ID is required when Render CLI is not logged in" >&2
  echo "List owners with: curl -H \"Authorization: Bearer \\$RENDER_API_KEY\" https://api.render.com/v1/owners" >&2
  exit 1
fi

response="$(
  curl -fsSL https://api.render.com/v1/blueprints/validate \
    -H "Authorization: Bearer $RENDER_API_KEY" \
    -H "Accept: application/json" \
    -F "ownerId=$RENDER_OWNER_ID" \
    -F "file=@render.yaml"
)"

printf "%s" "$response" | node -e '
let input = "";
process.stdin.on("data", (chunk) => input += chunk);
process.stdin.on("end", () => {
  const result = JSON.parse(input);
  console.log(JSON.stringify(result, null, 2));
  if (!result.valid) process.exit(1);
});
'
