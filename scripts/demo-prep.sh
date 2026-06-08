#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec "$ROOT_DIR/scripts/warm-modal-services.sh" \
  --service all \
  --repeat 2 \
  --interval-seconds 5 \
  --embedding-concurrency 3 \
  --timeout-seconds 300 \
  "$@"
