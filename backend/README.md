# Material Search Backend

FastAPI and Dramatiq services for the catalog and vector-enrichment slice.

## Local setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Create `backend/.env`. For this interview project, local development and prod
use the same real service values to keep the demo path simple. Use the Supabase
pooler connection string for `DATABASE_URL`; the direct database host can be
IPv6-only and is less reliable from local machines and CI:

```dotenv
DATABASE_URL=postgresql://postgres.project-ref:password@aws-0-region.pooler.supabase.com:6543/postgres
REDIS_URL=redis://default:password@host:6379
EMBEDDING_SERVICE_URL=https://modal-embedding-service.example.com
EMBEDDING_MODEL_ID=google/siglip2-so400m-patch14-384
EMBEDDING_DIMENSIONS=1152
GEMINI_API_KEY=
```

Apply the Supabase migration in `../supabase/migrations/0001_catalog_vector_enrichment.sql`
to the production project. See `../infra/README.md` for infrastructure-as-code
scripts and provider setup.

## Production

Production infrastructure currently uses:

- Supabase project: `material-search-prod`
- Supabase ref: `heskjwbphpvbtdnfxcgu`

The Supabase migration has been applied in prod, and these private storage
buckets exist:

- `catalog-images`
- `uploaded-images`
- `generated-artifacts`

For the free-tier path, deploy the frontend through GitHub Pages and deploy the
API only if it needs to be publicly reachable. The repo includes a root
`render.yaml` blueprint for a Render Free web service. Set the same
`DATABASE_URL` and `EMBEDDING_SERVICE_URL` values from `backend/.env` in Render.
Current Render API URL: `https://material-search-api.onrender.com`.
Current Modal embedding URL:
`https://tommy-4187--material-search-siglip-embeddings-fastapi-app.modal.run`.

Catalog vector enrichment does not require a long-lived
queue worker. Run it as a one-off command locally or through the manual
`Index Catalog` GitHub Action:

```bash
cd backend
set -a && source .env && set +a
catalog-index-missing --batch-size 25 --max-items 0
```

Use `--max-items 1` for a production smoke test before draining the catalog.

The GitHub Action needs these repository secrets:

- `DATABASE_URL`
- `EMBEDDING_SERVICE_URL`

The future Gemini planning/orchestration path also needs:

- `GEMINI_API_KEY`

`REDIS_URL` is optional for this path. Use direct Upstash Free Redis only if the
API needs to enqueue async jobs. Upstash Free currently gives enough room for
small hobby usage, but catalog indexing should still prefer the one-off command
so queue polling does not burn through free command quota.

The previous Fly app shell still exists:

- Fly app: `material-search-api`
- Fly region: `sjc`

It can run the API and worker process groups later, but Fly-managed Redis was
blocked until billing is added to the Fly organization. For free-tier production,
prefer GitHub Pages for the UI and a free web service only if the API needs to be
publicly reachable.

If deploying the API to Fly later, set secrets from `backend/.env`:

```bash
cd backend
set -a && source .env && set +a
flyctl secrets set \
  DATABASE_URL="$DATABASE_URL" \
  REDIS_URL="$REDIS_URL" \
  EMBEDDING_SERVICE_URL="$EMBEDDING_SERVICE_URL" \
  EMBEDDING_MODEL_ID="$EMBEDDING_MODEL_ID" \
  EMBEDDING_DIMENSIONS="$EMBEDDING_DIMENSIONS" \
  CATALOG_IMAGE_BUCKET="$CATALOG_IMAGE_BUCKET" \
  -a material-search-api
flyctl deploy
```

## Run

```bash
uvicorn app.main:app --reload
dramatiq app.workers.catalog_indexing
```

## Catalog flow

1. `POST /catalog/items` stores product metadata and image object keys.
2. `POST /catalog/embeddings:index` queues missing catalog items for embedding.
3. The `catalog-indexing` Dramatiq actor calls the embedding service and upserts a
   `{ catalog_item_id, model_id, dimensions, embedding }` row.
4. `POST /catalog/vector-search` runs nearest-neighbor search through pgvector.

## One-time starter catalog load

The starter catalog lives at `../data/catalog/material-bank-style-seed.json`.
It uses flat, square material swatch images only: no room scenes, installed
application shots, product packaging, or hero images.

Validate the manifest:

```bash
cd backend
catalog-load-seed --dry-run
```

Insert the catalog rows once:

```bash
cd backend
set -a && source .env && set +a
catalog-load-seed
```

Then smoke-test and drain missing embeddings:

```bash
catalog-index-missing --batch-size 25 --max-items 1
catalog-index-missing --batch-size 25 --max-items 0
```
