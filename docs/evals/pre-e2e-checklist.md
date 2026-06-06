# Pre-E2E Checklist

Use this checklist before treating a full upload-to-results smoke as meaningful.

1. Unit tests pass for pure code: crop math, mask handling, schema validation, and ranking behavior.
2. HTTP contract tests pass with mocked Gemini, SAM3, SigLIP, Supabase Storage, and pgvector boundaries.
3. Real service smoke tests pass independently for Gemini planning, SAM3 segmentation, SigLIP embeddings, Supabase Storage, and pgvector search.
4. Narrow integration tests pass for planner to SAM3, SAM3 to crop artifact, and crop embedding to pgvector search.
5. Search-run persistence is idempotent across retries and can reconstruct completed results.
6. Worker retry behavior does not duplicate regions or matches.
7. A small full upload-to-run-to-results smoke passes only after the above checks are green.
