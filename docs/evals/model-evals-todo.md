# Model Evals TODO

Use this as the later expansion list after the first demo-grade piece tests are in place.

## Planner Quality

- Add hand-authored prompt/image cases for vague intent, such as "materials with this warm hospitality feel".
- Add negative constraint cases, such as "like the floor but less glossy", and assert constraints are preserved in `plan.avoid`.
- Add non-material intent cases, such as "match the lamp shape", and assert the planner avoids unsupported material retrieval targets.
- Add over-segmentation guard cases that verify the planner respects `max_regions`.
- Add prompt-quality assertions that `sam3_prompt` values are short, visual, and segmentable.
- Add stable target-id checks for repeated or overlapping labels.

## Model-Service Smoke Evals

- Add a small real-image fixture set with expected high-level assertions, not exact boxes.
- Assert SAM3 returns at least one region above threshold for obvious material targets.
- Assert crop dimensions are non-trivial and bounded by the source image.
- Assert top catalog matches include an expected broad material family where the catalog supports it.
- Avoid exact top-match assertions unless the fixture and catalog entry are controlled.

## Retrieval Quality

- Add a curated catalog/query pair for textile, stone/tile, and wood.
- Track top-k family hit rate for each target family.
- Track empty-match rate separately from ranking quality.
- Preserve model version and catalog snapshot metadata with each eval run.
