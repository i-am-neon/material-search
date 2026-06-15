# Material Search Backend

FastAPI and Dramatiq services for the catalog and vector-enrichment slice.

## Local setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
uv pip install --python .venv/bin/python -e ".[dev]"
```

Create `backend/.env`. In this project, local development and prod
use the same real service values to keep the demo path simple. Use the Supabase
pooler connection string for `DATABASE_URL`; the direct database host can be
IPv6-only and is less reliable from local machines and CI:

```dotenv
DATABASE_URL=postgresql://postgres.project-ref:password@aws-0-region.pooler.supabase.com:6543/postgres
REDIS_URL=redis://default:password@host:6379
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:6006,http://localhost:6006,https://i-am-neon.github.io
EMBEDDING_SERVICE_URL=https://modal-embedding-service.example.com
SAM3_SERVICE_URL=https://modal-sam3-service.example.com
EMBEDDING_MODEL_ID=google/siglip2-so400m-patch14-384
EMBEDDING_DIMENSIONS=1152
GEMINI_API_KEY=
SUPABASE_PROJECT_REF=project-ref
SUPABASE_URL=https://project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=
CATALOG_IMAGE_BUCKET=catalog-images
UPLOADED_IMAGE_BUCKET=uploaded-images
GENERATED_ARTIFACT_BUCKET=generated-artifacts
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
`DATABASE_URL`, `EMBEDDING_SERVICE_URL`, and `SAM3_SERVICE_URL` values from
`backend/.env` in Render.
Current Render API URL: `https://material-search-api.onrender.com`.
Current Modal embedding URL:
`https://tommy-4187--material-search-siglip-embeddings-fastapi-app.modal.run`.
Current Modal SAM3 URL: deploy `../modal_services/sam3_segmentation_service.py`
and set `SAM3_SERVICE_URL` to the resulting `fastapi_app.modal.run` endpoint.

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
- `SAM3_SERVICE_URL`

The Gemini planning path also needs:

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
  SAM3_SERVICE_URL="$SAM3_SERVICE_URL" \
  EMBEDDING_MODEL_ID="$EMBEDDING_MODEL_ID" \
  EMBEDDING_DIMENSIONS="$EMBEDDING_DIMENSIONS" \
  CATALOG_IMAGE_BUCKET="$CATALOG_IMAGE_BUCKET" \
  -a material-search-api
flyctl deploy
```

## Run

Run the full local development stack from the repo root:

```bash
scripts/dev.sh
```

This starts FastAPI, the Dramatiq worker, and the Vite frontend. The backend
loads `backend/.env`, so the local stack still talks to the deployed Supabase,
Modal, Gemini, and Redis services configured there.

Use `scripts/dev.sh --no-worker` only for API/frontend routes that do not depend
on queued `/search/runs` jobs.

To run processes manually:

```bash
uvicorn app.main:app --reload
dramatiq app.workers.catalog_indexing app.workers.search_runs
```

## Test

From the repo root, use the wrapper so commands always resolve the backend
virtualenv correctly:

```bash
scripts/test-backend.sh
scripts/test-backend.sh tests/test_region_matching.py
```

The backend virtualenv lives at `backend/.venv`; avoid relying on bare `pytest`
being available on the shell PATH.

## SAM3 segmentation service

The SAM3 service is a Modal GPU FastAPI app in
`../modal_services/sam3_segmentation_service.py`. It uses the official
`facebookresearch/sam3` package and downloads the gated `facebook/sam3`
checkpoint from Hugging Face, so the Modal secret must include a token that has
accepted access to the model repo:

```bash
.tools/modal-venv/bin/modal secret create material-search-sam3-env \
  HF_TOKEN="$HF_TOKEN" \
  SUPABASE_URL="$SUPABASE_URL" \
  SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
  SAM3_IMAGE_BUCKET=uploaded-images
.tools/modal-venv/bin/modal deploy ../modal_services/sam3_segmentation_service.py
```

`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SAM3_IMAGE_BUCKET` are only
needed when segmenting storage object keys. Direct `image_url` requests do not
need Supabase credentials.

Run a real smoke test against the configured Modal endpoint:

```bash
cd backend
set -a && source .env && set +a
sam3-smoke-test
```

The default smoke uses Meta's public SAM3 example image with the prompt `shoe`
and fails unless the configured endpoint returns at least one region. The manual
`Smoke SAM3` GitHub Action runs the same command using the `SAM3_SERVICE_URL`
repository secret.

## Demo Modal warmup

Warm both Modal model services shortly before recording a demo:

```bash
scripts/demo-prep.sh
```

The demo prep script makes real, minimal inference requests to SAM3 and SigLIP,
then fans out three concurrent SigLIP requests so the likely parallel embedding
containers are warm before the app needs them. Use the lower-level warmup script
directly if you want a longer keepalive window while setting up the screen
recorder:

```bash
scripts/warm-modal-services.sh --repeat 3 --interval-seconds 45
```

## Production segment-match smoke

After the catalog has at least one indexed embedding, run the combined real
smoke against Supabase Storage, Postgres/pgvector, Modal SAM3, and Modal SigLIP:

```bash
cd backend
set -a && source .env && set +a
production-smoke-test
```

The command creates and completes a real `material_search_runs` row, uploads a
generated crop under `generated-artifacts/runs/...`, signs that crop for SigLIP,
and requires at least one pgvector match. It prints a compact JSON summary with
the persisted `run_id` and top match, but omits signed crop URLs.

## Catalog flow

1. `POST /catalog/items` stores product metadata and image object keys.
2. `POST /catalog/embeddings:index` queues missing catalog items for embedding.
3. The `catalog-indexing` Dramatiq actor calls the embedding service and upserts a
   `{ catalog_item_id, model_id, dimensions, embedding }` row.
4. `POST /catalog/vector-search` runs nearest-neighbor search through pgvector.

## Segment-to-catalog flow

`POST /search/uploads` accepts a multipart `image` file, validates it as JPEG,
PNG, or WebP, and stores it in the `uploaded-images` bucket. The response
contains the `image_object_key` to pass into `POST /search/segment-matches`.

`POST /search/runs` takes an uploaded image object key or direct image URL plus a
material prompt. The API creates a queued run row, enqueues a `search-runs`
Dramatiq job, and returns a `run_id` immediately. The client polls
`GET /search/runs/{run_id}` until the worker marks the run completed or failed.

The worker runs the LangGraph material-search graph: it asks Gemini to turn the
image and natural-language request into material targets and SAM3 prompts, stores
those planned targets, asks SAM3 for regions per target, crops each returned
region, uploads the crop to the generated-artifacts bucket, signs the crop URL,
embeds that crop with SigLIP, stores run/target/region/match rows in Postgres,
and persists ranked catalog matches from pgvector.

`POST /search/segment-matches` remains available as a synchronous compatibility
endpoint, but new UI flows should use the durable run API.

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

## Material Bank demo catalog import

For the larger demo catalog, use the public Material Bank sitemap and the
category scope in `../data/catalog/material-bank-demo-categories.json`. The
current scope targets kitchen, bathroom, living-room, and mood-board surfaces:
tile, paints, surfaces, flooring, textiles, wallcovering, masonry/stone,
leather, paneling, bathroom, kitchen, hardware, lighting, and furniture.

Generate a manifest with up to 50 matched products per category:

```bash
cd backend
catalog-import-materialbank --per-category 50
```

Filter out broken image rows and paint/product-can photos:

```bash
cd backend
catalog-filter-manifest
```

Build a review gallery from the generated manifest:

```bash
cd backend
catalog-build-gallery \
  --manifest ../data/catalog/material-bank-public-demo-curated-seed.json \
  --output ../data/catalog/material-bank-public-demo-curated-gallery.html
open ../data/catalog/material-bank-public-demo-curated-gallery.html
```

Smoke-test the importer without writing the manifest:

```bash
cd backend
catalog-import-materialbank --max-sitemaps 1 --dry-run
```

Load the generated manifest and index it:

```bash
cd backend
set -a && source .env && set +a
catalog-load-seed --manifest ../data/catalog/material-bank-public-demo-curated-seed.json
catalog-index-missing --batch-size 25 --max-items 1
catalog-index-missing --batch-size 25 --max-items 0
```
