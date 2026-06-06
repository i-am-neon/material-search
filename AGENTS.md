# AGENTS.md

Project-local instructions for agents working in this repo.

## Project Context

This repo is a fresh rewrite seed for a Material Bank interview project. Do not port the old `sam3-learning` implementation directly. Treat the architecture docs as the source of truth:

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
- Start with a few hand-authored evals later; future product signals should create eval candidates, not automatic ground truth.

## Git Ownership

- The agent should manage git end to end for repo work: inspect status, create branches when appropriate, stage intentional changes, commit with clear messages, and prepare pushes/PRs when the user asks for publication.
- Never revert user changes or use destructive git commands unless the user explicitly requests that exact operation.
