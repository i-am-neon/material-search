# Future Eval Architecture

This is not part of the first build. Start with a small hand-created eval set, then preserve a practical feedback loop that could turn real product usage into better eval coverage later.

## Starting Point

- Create a few hand-authored evals to prove the pipeline works before any product telemetry exists.
- Cover the core path: request interpretation, material concept selection, SAM3 region quality, and top catalog matches.
- Include at least one obvious success case, one ambiguous material case, and one expected failure or no-match case.

## Feedback-to-Eval Pipeline

```text
hand-created evals
  -> baseline regression tests
  -> product usage starts
  -> 
user interaction signals
  -> candidate good/bad runs
  -> human review
  -> curated eval cases
  -> regression tests for models, prompts, retrieval, and ranking
```

User behavior should flag eval candidates, not create ground truth automatically. Indirect signals are useful but noisy, so reviewed examples should be promoted into evals by a human.

## Candidate Signals

- Positive candidates: user saves a material, adds it to a project, orders a sample, shares it, accepts the match, or repeatedly engages with the returned product.
- Negative candidates: user rejects the result, immediately reformulates the search, selects a very different product, filters to a different material family, or abandons after no meaningful engagement.

## Review Labels

- Was the selected material concept correct?
- Was the SAM3 region usable?
- Was the catalog match visually/materially useful?
- If the result failed, was the issue concept planning, segmentation, embedding retrieval, ranking, metadata, or catalog coverage?

## Interview Framing

The system should not blindly evaluate from user behavior. The stronger approach is to use Material Bank-specific workflow signals to surface high-value examples for human curation. Those reviewed examples become a representative eval set for comparing prompt changes, model upgrades, segmentation thresholds, embedding models, reranking strategies, and catalog metadata quality.
