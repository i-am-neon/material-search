#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

if [[ ! -f backend/.env ]]; then
  echo "backend/.env is required" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source backend/.env
set +a

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required in backend/.env" >&2
  exit 1
fi

psql "$DATABASE_URL" -Atc "
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'catalog_items',
    'catalog_embedding_models',
    'catalog_item_embeddings'
  )
order by table_name;

select id
from storage.buckets
where id in ('catalog-images', 'uploaded-images', 'generated-artifacts')
order by id;
"

