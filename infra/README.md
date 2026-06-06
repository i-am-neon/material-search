# Infrastructure

This repo manages as much production infrastructure as practical in code.
Provider accounts, billing state, and secret values still live outside git.

## Managed In Code

- **Supabase schema:** `supabase/migrations/*.sql`
- **Supabase local/link config:** `supabase/config.toml`
- **Render API service:** `render.yaml`
- **Modal embedding service:** `modal_services/siglip_embedding_service.py`
- **Modal SAM3 service:** `modal_services/sam3_segmentation_service.py`
- **GitHub Pages UI deploy:** `.github/workflows/deploy-ui.yml`
- **Render API deploy:** `.github/workflows/deploy-api.yml`
- **Modal service deploys:** `.github/workflows/deploy-modal-services.yml`
- **Supabase migration deploys:** `.github/workflows/deploy-supabase-migrations.yml`
- **Catalog vector indexing job:** `.github/workflows/index-catalog.yml`
- **Fly fallback API config:** `backend/fly.toml`

## Provider Setup Scripts

Run these from the repo root:

```bash
scripts/infra/check-supabase-prod.sh
scripts/infra/sync-github-secrets.sh
scripts/infra/sync-render-env.sh
scripts/infra/validate-render-blueprint.sh
```

## Required Local Secret Files

`backend/.env` is ignored by git and should contain the production values used by
local commands and secret-sync scripts:

```dotenv
DATABASE_URL=postgresql://...
EMBEDDING_SERVICE_URL=https://...
SAM3_SERVICE_URL=https://...
GEMINI_API_KEY=...
RENDER_API_KEY=...
```

## Render

Render's recommended IaC path is a Blueprint backed by `render.yaml`. The
Blueprint defines the free API web service and prompts for secret values marked
with `sync: false`.

Current Render resources:

- Workspace: `Tommy's workspace`
- Workspace ID: `tea-d51hqoali9vc73e1h3vg`
- API service: `material-search-api`
- Service ID: `srv-d8i45j58nd3s73e1u29g`
- URL: `https://material-search-api.onrender.com`

Every push to `main` redeploys the API through
`.github/workflows/deploy-api.yml`. The workflow triggers a Render deploy for
the pushed commit, waits for the deploy to become live, and then checks
`/healthz`.

Required GitHub configuration:

- Secret: `RENDER_API_KEY`
- Variable: `RENDER_SERVICE_ID` (`srv-d8i45j58nd3s73e1u29g`)

## Modal Embedding Service

Current Modal resources:

- App: `material-search-siglip-embeddings`
- Endpoint: `https://tommy-4187--material-search-siglip-embeddings-fastapi-app.modal.run`
- Secret: `material-search-embedding-env`

The endpoint implements:

- `GET /healthz`
- `POST /embed-image`

Deploy after changing the service:

```bash
.tools/modal-venv/bin/modal deploy modal_services/siglip_embedding_service.py
```

Every push to `main` redeploys this service through
`.github/workflows/deploy-modal-services.yml`.

## Modal SAM3 Service

Current Modal resources:

- App: `material-search-sam3-segmentation`
- Secret: `material-search-sam3-env`

The endpoint implements:

- `GET /healthz`
- `POST /segment-image`

The secret must include `HF_TOKEN` with accepted access to the gated
`facebook/sam3` Hugging Face repo. Add Supabase storage values to the same
secret when requests use `image_object_key` instead of direct `image_url`:

```bash
.tools/modal-venv/bin/modal secret create material-search-sam3-env \
  HF_TOKEN="$HF_TOKEN" \
  SUPABASE_URL="$SUPABASE_URL" \
  SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
  SAM3_IMAGE_BUCKET=uploaded-images
.tools/modal-venv/bin/modal deploy modal_services/sam3_segmentation_service.py
```

The same Modal deploy workflow also redeploys SAM3. It requires these GitHub
secrets:

- `MODAL_TOKEN_ID`
- `MODAL_TOKEN_SECRET`

After deploy, set `SAM3_SERVICE_URL` in `backend/.env`, Render, and GitHub
Actions secrets. Validate the real endpoint with:

```bash
cd backend
set -a && source .env && set +a
sam3-smoke-test
```

Programmatic validation requires:

- a logged-in Render CLI, or
- `RENDER_API_KEY` plus `RENDER_OWNER_ID`

Sync Render service environment variables from `backend/.env`:

```bash
scripts/infra/sync-render-env.sh
render deploys create srv-d8i45j58nd3s73e1u29g --wait --confirm
```

## Supabase Migrations

Every push to `main` applies migrations through
`.github/workflows/deploy-supabase-migrations.yml`. The workflow applies each
migration with `psql -v ON_ERROR_STOP=1`, so migrations must stay idempotent.

Required GitHub secret:

- `DATABASE_URL`

## UI Deploy

Pushes to `main` always redeploy the GitHub Pages UI through
`.github/workflows/deploy-ui.yml`, using the Render API URL as
`VITE_API_BASE_URL`.

## Async Search Runs

The durable `/search/runs` path still needs a cloud Redis URL and a running
Dramatiq worker service. The current Render account has only the free web API
service; Render background workers require a paid worker plan. Until Redis and a
worker are provisioned, `/search/segment-matches` is the deployed synchronous
demo path and `/search/runs` should be expected to return queue unavailable.

`RENDER_OWNER_ID` is the workspace ID from Render workspace settings. You can
also list it after setting `RENDER_API_KEY`:

```bash
curl -fsSL https://api.render.com/v1/owners \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Accept: application/json"
```

## Current External Inputs

- `RENDER_API_KEY` is required for GitHub Actions to validate Render resources
  and redeploy the API. Local validation works with `render login`.
