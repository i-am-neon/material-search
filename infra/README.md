# Infrastructure

This repo manages as much production infrastructure as practical in code.
Provider accounts, billing state, and secret values still live outside git.

## Managed In Code

- **Supabase schema:** `supabase/migrations/*.sql`
- **Supabase local/link config:** `supabase/config.toml`
- **Render API service:** `render.yaml`
- **Modal embedding service:** `modal_services/siglip_embedding_service.py`
- **GitHub Pages UI deploy:** `.github/workflows/deploy-ui.yml`
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
GEMINI_API_KEY=...
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

Programmatic validation requires:

- a logged-in Render CLI, or
- `RENDER_API_KEY` plus `RENDER_OWNER_ID`

Sync Render service environment variables from `backend/.env`:

```bash
scripts/infra/sync-render-env.sh
render deploys create srv-d8i45j58nd3s73e1u29g --wait --confirm
```

`RENDER_OWNER_ID` is the workspace ID from Render workspace settings. You can
also list it after setting `RENDER_API_KEY`:

```bash
curl -fsSL https://api.render.com/v1/owners \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Accept: application/json"
```

## Current External Inputs

- `RENDER_API_KEY` is required only for GitHub Actions to validate Render
  resources long-term. Local validation works with `render login`.
