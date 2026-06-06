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
use the same service values to keep deployment simple:

```dotenv
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
REDIS_URL=redis://localhost:6379/0
EMBEDDING_SERVICE_URL=http://localhost:8081
EMBEDDING_MODEL_ID=google/siglip2-so400m-patch14-384
EMBEDDING_DIMENSIONS=1152
```

Apply the Supabase migration in `../supabase/migrations/0001_catalog_vector_enrichment.sql`.

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
