# AGENTS.md

Project-local instructions for agents working in this repo.

> `CLAUDE.md` in this repo is a symlink to this file (`ln -s AGENTS.md CLAUDE.md`), so the two are the same file and always match. Never replace the symlink with a real file — Claude Code reads `CLAUDE.md` and would otherwise silently drift from these instructions.

## Project Context

This repo is a fresh rewrite seed for an image-first material sourcing project. Do not port the old `sam3-learning` implementation directly. Treat the architecture docs as the source of truth:

- `docs/architecture/cloud-material-finder.md`
- `docs/architecture/future-eval-architecture.md`

Build incrementally from the target architecture, starting with project scaffolding before feature implementation.

## Chosen Stack

- Frontend: Vite + React + TypeScript.
- App API: FastAPI with Pydantic request/response schemas.
- Orchestration: LangGraph inside Python workers; Pydantic for typed graph state and structured model outputs.
- Queues: Dramatiq + Redis, with coarse-grained jobs for search runs and catalog indexing.
- Data: Supabase Postgres + pgvector for run state, catalog metadata, embeddings, and match results.
- Object storage: Supabase Storage for catalog images, uploaded images, and generated crop/mask artifacts.
- Model services: Gemini API for multimodal planning, Modal-hosted SAM3 for segmentation, and SigLIP 2 for image embeddings.

## Build Guidance

- Keep the first implementation focused on the architecture path, not full production hardening.
- Prefer clean service boundaries: web app, API, workers, model services, and Supabase data/storage.
- Use durable search runs: the API creates a `run_id`, enqueues work, and clients fetch status/results.
- Keep model trust boundaries explicit: models may choose concepts, regions, and descriptions; code owns persisted IDs, boxes, confidence scores, embeddings, nearest-neighbor search, product IDs, and similarity values.
- Do not use keyword matching to infer catalog categories or filters in LLM applications. Show the model the allowed structured category/filter options and require it to choose an explicit structured value; downstream code may validate exact allowed values, but must not derive category intent from free-text labels, prompts, or descriptions.
- Start with a few hand-authored evals later; future product signals should create eval candidates, not automatic ground truth.
- For demo simplicity, development and production share the same real service keys and infrastructure values. Do not add fake, deterministic, stubbed, or local-only model/data paths for dev convenience unless the user explicitly asks for a test-only harness. Catalog vector creation and similar workflows should use the real production model services and persisted production-style data paths.

## Test Commands

- Backend Python tooling lives in `backend/.venv`; do not assume `pytest` or `ruff` are on the shell PATH.
- Run backend tests from the repo root with `scripts/test-backend.sh`. Pass normal pytest args through that wrapper, for example `scripts/test-backend.sh tests/test_region_matching.py`.
- If backend dependencies are missing or stale, refresh the venv with `cd backend && uv pip install --python .venv/bin/python -e ".[dev]"`.
- For direct backend commands, prefer `backend/.venv/bin/python -m pytest` and `backend/.venv/bin/ruff` over bare executable names.

## Logfire Investigation

- Use `scripts/logfire-query` for Logfire investigations. It loads `backend/.env`, expects `LOGFIRE_READ_TOKEN`, and must never print or commit tokens.
- For copied Logfire trace links, start with `scripts/logfire-query investigate '<url>' --until now` to summarize the trace, recent errors, and slow spans in the linked time window.

## Frontend UI Guidance

- Whenever updating the UI, treat Storybook as a source of truth for the intended component states and user flows. Add or update stories alongside UI changes so the workbench, region review, matching, failure, and cart states remain easy to inspect independently of the app route.

## Git Ownership

- Work directly on `main` by default. Do not create or switch to a new branch unless the user explicitly asks for one.
- Manage git end to end for repo work: inspect status, stage intentional changes, commit with clear messages, and prepare pushes/PRs when the user asks for publication.
- Whenever you finish a work item, ask the user whether they want you to commit the changes and push to `main`.
- Before committing, inspect status and diffs and commit only the work you performed. Other agents may be working in the repo in parallel, so do not stage or commit unrelated modified, deleted, or untracked files.
- Never revert user changes or use destructive git commands unless the user explicitly requests that exact operation.
