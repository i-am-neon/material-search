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
- Fly app: `material-search-api`
- Fly region: `sjc`

The Supabase migration has been applied in prod, and these private storage
buckets exist:

- `catalog-images`
- `uploaded-images`
- `generated-artifacts`

The Fly app uses one image with two process groups:

- `api`: `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- `worker`: `dramatiq app.workers.catalog_indexing`

Before running catalog indexing in prod, set:

- `REDIS_URL`: required by Dramatiq. Fly-managed Redis was blocked until billing
  is added to the Fly organization.
- `EMBEDDING_SERVICE_URL`: required by the catalog worker to create SigLIP 2
  vectors.

After both values exist, update `backend/.env`, set Fly secrets from it, deploy,
and queue indexing:

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
