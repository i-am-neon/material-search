# Infrastructure

This repo manages as much production infrastructure as practical in code.
Provider accounts, billing state, and secret values still live outside git.

## Managed In Code

- **Supabase schema:** `supabase/migrations/*.sql`
- **Supabase local/link config:** `supabase/config.toml`
- **Render API service:** `render.yaml`
- **GitHub Pages UI deploy:** `.github/workflows/deploy-ui.yml`
- **Catalog vector indexing job:** `.github/workflows/index-catalog.yml`
- **Fly fallback API config:** `backend/fly.toml`

## Provider Setup Scripts

Run these from the repo root:

```bash
scripts/infra/check-supabase-prod.sh
scripts/infra/sync-github-secrets.sh
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

Programmatic validation requires:

- `RENDER_API_KEY`
- `RENDER_OWNER_ID`

`RENDER_OWNER_ID` is the workspace ID from Render workspace settings. You can
also list it after setting `RENDER_API_KEY`:

```bash
curl -fsSL https://api.render.com/v1/owners \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Accept: application/json"
```

## Current External Inputs

- `EMBEDDING_SERVICE_URL` is still required before vector indexing can run.
- `RENDER_API_KEY` and `RENDER_OWNER_ID` are required only if we want to validate
  or create Render resources programmatically instead of through the dashboard.

