# Model Evals TODO

Use this as the expansion list after the first demo-grade piece tests are in place.

## Planner Quality

- Added hand-authored prompt/image cases for vague intent, such as "materials with this warm hospitality feel".
- Added negative constraint cases, such as "like the floor but less glossy", and assert constraints are preserved in `plan.avoid`.
- Added a non-material intent eval, such as "match the lamp shape", using the unsupported-intent planner response shape.
- Added over-segmentation guard cases that verify the planner respects `max_regions`.
- Added prompt-quality assertions that `sam3_prompt` values are short, visual, and segmentable.
- Added stable target-id checks for repeated or overlapping labels.

## Model-Service Smoke Evals

- Added deterministic high-level assertions for a representative obvious material target.
- Added region score and crop dimension invariants.
- Added retrieval metrics for expected broad material-family hits and empty-match rate.

Remaining live-service expansion:

- Add a small real-image fixture set with expected high-level assertions, not exact boxes.
- Assert SAM3 returns at least one region above threshold for obvious material targets using the live service.
- Assert crop dimensions are non-trivial and bounded by the source image using live SAM3 regions.
- Assert top catalog matches include an expected broad material family where the catalog supports it.
- Avoid exact top-match assertions unless the fixture and catalog entry are controlled.

## Retrieval Quality

- Added top-k family hit-rate and empty-match-rate metric coverage.

Remaining live-service expansion:

- Add a curated catalog/query pair for textile, stone/tile, and wood.
- Preserve model version and catalog snapshot metadata with each eval run.
