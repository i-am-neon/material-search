#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

SERVICE_ID="${RENDER_SERVICE_ID:-srv-d8i45j58nd3s73e1u29g}"

if [[ ! -f backend/.env ]]; then
  echo "backend/.env is required" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source backend/.env
set +a

render_api_key() {
  if [[ -n "${RENDER_API_KEY:-}" ]]; then
    printf "%s" "$RENDER_API_KEY"
    return
  fi

  local config_file="${HOME}/.render/cli.yaml"
  if [[ -f "$config_file" ]]; then
    awk -F': ' '/^[[:space:]]+key:/ { print $2; exit }' "$config_file"
    return
  fi
}

TOKEN="$(render_api_key)"
if [[ -z "$TOKEN" ]]; then
  echo "RENDER_API_KEY or a logged-in Render CLI is required" >&2
  exit 1
fi

set_render_env() {
  local key="$1"
  local value="${!key:-}"

  if [[ -z "$value" ]]; then
    echo "Skipping $key: not set"
    return
  fi

  node - "$SERVICE_ID" "$key" "$value" "$TOKEN" <<'NODE'
const https = require("https");

const [serviceId, key, value, token] = process.argv.slice(2);
const body = JSON.stringify({ value });

const req = https.request({
  method: "PUT",
  hostname: "api.render.com",
  path: `/v1/services/${serviceId}/env-vars/${encodeURIComponent(key)}`,
  headers: {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(body),
  },
}, (res) => {
  let data = "";
  res.on("data", (chunk) => data += chunk);
  res.on("end", () => {
    if (res.statusCode < 200 || res.statusCode >= 300) {
      console.error(`Render API failed for ${key}: ${res.statusCode}`);
      console.error(data);
      process.exit(1);
    }
    console.log(`Set Render env ${key}`);
  });
});

req.on("error", (error) => {
  console.error(error);
  process.exit(1);
});
req.write(body);
req.end();
NODE
}

set_render_env DATABASE_URL
set_render_env EMBEDDING_SERVICE_URL
set_render_env GEMINI_API_KEY
set_render_env EMBEDDING_MODEL_ID
set_render_env EMBEDDING_DIMENSIONS
set_render_env CATALOG_IMAGE_BUCKET

